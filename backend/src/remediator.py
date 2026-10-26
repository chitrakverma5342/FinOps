"""
FinOps Cost Guardian — Remediator Lambda Function
Executes safe, tag-gated auto-remediation of idle resources:
  - Strict Exclusion Guard: 'DoNotStop=true' is NEVER touched -> SKIPPED_DO_NOT_STOP
  - Opt-In Eligibility Guard: requires 'eligible-for-remediation=true'
  - Dry-Run Simulation Mode: zero AWS mutations when DRY_RUN=true
  - Actions:
      * EC2: ec2.stop_instances()
      * EBS: ec2.delete_volume()
      * EIP: ec2.release_address()
Logs outcomes to DynamoDB and sends SNS notification.
"""

import os
import logging
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

from common import (
    TABLE_NAME,
    SNS_TOPIC_ARN,
    DEFAULT_REGION,
    DRY_RUN_DEFAULT,
    TAG_ELIGIBLE,
    TAG_DO_NOT_STOP,
    STATUS_FLAGGED,
    STATUS_REMEDIATED,
    STATUS_SKIPPED_DO_NOT_STOP,
    STATUS_SKIPPED_NOT_ELIGIBLE,
    STATUS_DRY_RUN_SIMULATED,
    SCANNER_VERSION,
    parse_tags,
    is_tag_truthy,
    get_dynamodb_table,
    log_record_to_dynamodb,
    publish_sns_alert,
    format_remediation_email,
)

logger = logging.getLogger("remediator")
logger.setLevel(logging.INFO)


def fetch_live_tags_and_state(ec2_client, resource_id: str, resource_type: str) -> tuple[dict[str, str], str]:
    """Fetch real-time tags and state directly from AWS EC2 API before taking action."""
    tags = {}
    state = "unknown"

    try:
        if resource_type.upper() == "EC2":
            res = ec2_client.describe_instances(InstanceIds=[resource_id])
            for r in res.get("Reservations", []):
                for inst in r.get("Instances", []):
                    tags = parse_tags(inst.get("Tags", []))
                    state = inst.get("State", {}).get("Name", "unknown")
                    return tags, state

        elif resource_type.upper() == "EBS":
            res = ec2_client.describe_volumes(VolumeIds=[resource_id])
            for vol in res.get("Volumes", []):
                tags = parse_tags(vol.get("Tags", []))
                state = vol.get("State", "unknown")
                return tags, state

        elif resource_type.upper() == "EIP":
            # Can describe by AllocationId or PublicIp
            if resource_id.startswith("eipalloc-"):
                res = ec2_client.describe_addresses(AllocationIds=[resource_id])
            else:
                res = ec2_client.describe_addresses(PublicIps=[resource_id])
            for addr in res.get("Addresses", []):
                tags = parse_tags(addr.get("Tags", []))
                assoc = addr.get("AssociationId")
                state = "associated" if assoc else "unassociated"
                return tags, state

    except Exception as e:
        logger.warning(f"Failed to fetch live tags for {resource_type} {resource_id}: {e}")

    return tags, state


def evaluate_and_remediate_single(
    resource_id: str,
    resource_type: str,
    cached_tags: dict | None = None,
    dry_run: bool = False,
    ec2_client=None,
    dynamodb_resource=None,
    region=None,
    account_id="123456789012"
) -> dict:
    """Safely evaluate and remediate a single cloud resource."""
    current_region = region or DEFAULT_REGION
    if ec2_client is None:
        ec2_client = boto3.client("ec2", region_name=current_region)

    timestamp = datetime.now(timezone.utc).isoformat()
    resource_type_upper = resource_type.upper()

    # Step 1: Query live tags directly from AWS to ensure zero stale decisions
    live_tags, live_state = fetch_live_tags_and_state(ec2_client, resource_id, resource_type_upper)
    tags = live_tags if live_tags else (cached_tags or {})

    # Evaluate safety tags
    has_do_not_stop = is_tag_truthy(tags, TAG_DO_NOT_STOP)
    has_eligible = is_tag_truthy(tags, TAG_ELIGIBLE)

    record = {
        "resource_id": resource_id,
        "scan_timestamp": timestamp,
        "resource_type": resource_type_upper,
        "region": current_region,
        "resource_state": live_state,
        "tags": tags,
        "eligible_for_remediation": has_eligible,
        "do_not_stop": has_do_not_stop,
        "scanner_version": SCANNER_VERSION,
        "account_id": account_id,
    }

    # =========================================================================
    # RULE 1: STRICT EXCLUSION GUARD (DoNotStop=true)
    # This check ALWAYS comes first and CANNOT be bypassed by any other setting.
    # =========================================================================
    if has_do_not_stop:
        action_msg = "SKIPPED: Resource protected by DoNotStop tag"
        logger.info(f"PROTECTED: {resource_type_upper} {resource_id} has DoNotStop=true. Skipping remediation.")
        record.update({
            "status": STATUS_SKIPPED_DO_NOT_STOP,
            "action_taken": action_msg,
            "estimated_monthly_waste_usd": 0.0,
        })
        log_record_to_dynamodb(record, dynamodb_resource=dynamodb_resource)
        return record

    # =========================================================================
    # RULE 2: OPT-IN ELIGIBILITY GUARD (eligible-for-remediation=true)
    # Resources must explicitly opt in to automated remediation.
    # =========================================================================
    if not has_eligible:
        action_msg = "SKIPPED: Resource missing eligible-for-remediation=true tag"
        logger.info(f"UNELIGIBLE: {resource_type_upper} {resource_id} is missing opt-in tag.")
        record.update({
            "status": STATUS_SKIPPED_NOT_ELIGIBLE,
            "action_taken": action_msg,
            "estimated_monthly_waste_usd": 0.0,
        })
        log_record_to_dynamodb(record, dynamodb_resource=dynamodb_resource)
        return record

    # =========================================================================
    # RULE 3: DRY-RUN SIMULATION MODE
    # If dry_run is True, calculate what would happen but do NOT execute mutations.
    # =========================================================================
    if dry_run:
        action_msg = f"SIMULATED: Would remediate {resource_type_upper} ({'stop' if resource_type_upper == 'EC2' else 'delete' if resource_type_upper == 'EBS' else 'release'})"
        logger.info(f"DRY RUN: {action_msg} on {resource_id}")
        record.update({
            "status": STATUS_DRY_RUN_SIMULATED,
            "action_taken": action_msg,
            "estimated_monthly_waste_usd": 8.47 if resource_type_upper == "EC2" else 2.0 if resource_type_upper == "EBS" else 3.60,
        })
        log_record_to_dynamodb(record, dynamodb_resource=dynamodb_resource)
        return record

    # =========================================================================
    # RULE 4: LIVE REMEDIATION EXECUTION
    # Execute actual AWS resource modification and log REMEDIATED status.
    # =========================================================================
    saved_monthly = 0.0
    action_taken_desc = ""

    try:
        if resource_type_upper == "EC2":
            ec2_client.stop_instances(InstanceIds=[resource_id])
            action_taken_desc = f"Stopped EC2 instance {resource_id}"
            saved_monthly = 8.47  # estimated monthly savings for t2.micro

        elif resource_type_upper == "EBS":
            ec2_client.delete_volume(VolumeId=resource_id)
            action_taken_desc = f"Deleted unattached EBS volume {resource_id}"
            saved_monthly = 2.00  # typical estimated volume savings

        elif resource_type_upper == "EIP":
            if resource_id.startswith("eipalloc-"):
                ec2_client.release_address(AllocationId=resource_id)
            else:
                ec2_client.release_address(PublicIp=resource_id)
            action_taken_desc = f"Released unassociated Elastic IP {resource_id}"
            saved_monthly = 3.60  # $0.005/hr * 720 hrs

        record.update({
            "status": STATUS_REMEDIATED,
            "action_taken": action_taken_desc,
            "estimated_monthly_waste_usd": saved_monthly,
        })
        logger.info(f"REMEDIATED: {action_taken_desc}")

    except Exception as e:
        logger.error(f"Remediation error for {resource_type_upper} {resource_id}: {e}", exc_info=True)
        record.update({
            "status": "REMEDIATION_ERROR",
            "action_taken": f"Error: {str(e)}",
            "estimated_monthly_waste_usd": 0.0,
        })

    log_record_to_dynamodb(record, dynamodb_resource=dynamodb_resource)
    return record


def get_flagged_records_from_dynamodb(dynamodb_resource=None) -> list[dict]:
    """Retrieve active FLAGGED records from DynamoDB scan-log table."""
    try:
        table = get_dynamodb_table(dynamodb_resource=dynamodb_resource)
        response = table.scan()
        items = response.get("Items", [])
        return [i for i in items if i.get("status") == STATUS_FLAGGED]
    except Exception as e:
        logger.error(f"Failed to scan DynamoDB for FLAGGED records: {e}")
        return []


def remediate_all(
    targets: list[dict] | None = None,
    dry_run: bool | None = None,
    ec2_client=None,
    dynamodb_resource=None,
    sns_client=None,
    region=None
) -> dict:
    """Orchestrate remediation across specified targets or all FLAGGED records."""
    is_dry_run = DRY_RUN_DEFAULT if dry_run is None else bool(dry_run)
    current_region = region or DEFAULT_REGION

    if targets is None:
        flagged_items = get_flagged_records_from_dynamodb(dynamodb_resource)
    else:
        flagged_items = targets

    results = []
    for item in flagged_items:
        res_id = item.get("resource_id")
        res_type = item.get("resource_type", "EC2")
        tags = item.get("tags", {})

        if not res_id or res_id.startswith("SCAN_SUMMARY") or res_id.startswith("SCAN#"):
            continue

        outcome = evaluate_and_remediate_single(
            resource_id=res_id,
            resource_type=res_type,
            cached_tags=tags,
            dry_run=is_dry_run,
            ec2_client=ec2_client,
            dynamodb_resource=dynamodb_resource,
            region=current_region
        )
        results.append(outcome)

    # Publish remediation summary to SNS if any resources were processed
    if results and SNS_TOPIC_ARN:
        prefix = "[DRY-RUN]" if is_dry_run else "[CONFIRMATION]"
        subject = f"[FinOps Cost Guardian] {prefix} Remediated {len(results)} Resource(s)"
        body = format_remediation_email(results, dry_run=is_dry_run)
        publish_sns_alert(subject, body, sns_client=sns_client)

    return {
        "dry_run": is_dry_run,
        "processed_count": len(results),
        "remediated_count": sum(1 for r in results if r.get("status") in (STATUS_REMEDIATED, STATUS_DRY_RUN_SIMULATED)),
        "skipped_count": sum(1 for r in results if r.get("status") in (STATUS_SKIPPED_DO_NOT_STOP, STATUS_SKIPPED_NOT_ELIGIBLE)),
        "results": results
    }


def lambda_handler(event, context):
    """Entry point for Remediator Lambda invocation."""
    logger.info(f"Remediator invoked with event: {event}")
    event = event or {}

    dry_run = event.get("dry_run")
    single_id = event.get("resource_id")
    single_type = event.get("resource_type")

    if single_id and single_type:
        outcome = evaluate_and_remediate_single(
            resource_id=single_id,
            resource_type=single_type,
            cached_tags=event.get("tags"),
            dry_run=DRY_RUN_DEFAULT if dry_run is None else bool(dry_run)
        )
        return {
            "statusCode": 200,
            "body": outcome
        }

    targets = event.get("resources")
    summary = remediate_all(targets=targets, dry_run=dry_run)
    return {
        "statusCode": 200,
        "body": summary
    }
