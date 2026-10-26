"""
FinOps Cost Guardian — ResourceScanner Lambda Function
Monitors AWS account for idle EC2 instances, unattached EBS volumes, and unassociated Elastic IPs.
Logs every scan outcome (CLEAN or FLAGGED) to DynamoDB and sends SNS alerts.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

from common import (
    TABLE_NAME,
    SNS_TOPIC_ARN,
    DEFAULT_REGION,
    IDLE_THRESHOLD_HOURS,
    DEMO_FORCE_IDLE,
    SCANNER_VERSION,
    TAG_ELIGIBLE,
    TAG_DO_NOT_STOP,
    STATUS_CLEAN,
    STATUS_FLAGGED,
    parse_tags,
    is_tag_truthy,
    calculate_ec2_waste,
    calculate_ebs_waste,
    calculate_eip_waste,
    log_record_to_dynamodb,
    publish_sns_alert,
    format_scan_alert_email,
)

logger = logging.getLogger("resource_scanner")
logger.setLevel(logging.INFO)


def get_account_id(sts_client=None) -> str:
    try:
        if sts_client is None:
            sts_client = boto3.client("sts", region_name=DEFAULT_REGION)
        return sts_client.get_caller_identity().get("Account", "123456789012")
    except Exception:
        return "123456789012"


def scan_ec2_instances_impl(ec2_client, idle_threshold: float, force_idle: bool, now_utc: datetime) -> list[dict]:
    flagged = []
    paginator = ec2_client.get_paginator("describe_instances")
    pages = paginator.paginate(Filters=[{"Name": "instance-state-name", "Values": ["running"]}])

    for page in pages:
        for reservation in page.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                instance_id = instance.get("InstanceId")
                launch_time = instance.get("LaunchTime")
                instance_type = instance.get("InstanceType", "t2.micro")
                tags = parse_tags(instance.get("Tags", []))

                # Normalize launch time to UTC
                if launch_time.tzinfo is None:
                    launch_time = launch_time.replace(tzinfo=timezone.utc)
                else:
                    launch_time = launch_time.astimezone(timezone.utc)

                running_hours = (now_utc - launch_time).total_seconds() / 3600.0

                # Evaluate idle condition: force_idle flag, threshold 0, or hours exceeded
                is_idle = force_idle or idle_threshold == 0 or running_hours >= idle_threshold

                if is_idle:
                    hourly_cost, monthly_waste = calculate_ec2_waste(instance_type, running_hours)
                    eligible = is_tag_truthy(tags, TAG_ELIGIBLE)
                    do_not_stop = is_tag_truthy(tags, TAG_DO_NOT_STOP)

                    action_taken = "FLAGGED_FOR_REMEDIATION" if (eligible and not do_not_stop) else "FLAGGED_FOR_REVIEW"
                    if do_not_stop:
                        action_taken = "PROTECTED_BY_DO_NOT_STOP_TAG"

                    flagged.append({
                        "resource_id": instance_id,
                        "resource_type": "EC2",
                        "resource_state": "running",
                        "idle_duration_hours": round(running_hours, 2),
                        "estimated_hourly_cost_usd": hourly_cost,
                        "estimated_monthly_waste_usd": monthly_waste,
                        "status": STATUS_FLAGGED,
                        "eligible_for_remediation": eligible,
                        "do_not_stop": do_not_stop,
                        "action_taken": action_taken,
                        "tags": tags,
                        "metadata": {
                            "instance_type": instance_type,
                            "launch_time": launch_time.isoformat(),
                        }
                    })

    return flagged


def scan_ebs_volumes_impl(ec2_client, now_utc: datetime) -> list[dict]:
    """Scan and paginate all EBS volumes in 'available' (unattached) state."""
    flagged = []
    paginator = ec2_client.get_paginator("describe_volumes")
    pages = paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}])

    for page in pages:
        for volume in page.get("Volumes", []):
            vol_id = volume.get("VolumeId")
            size_gb = volume.get("Size", 8)
            create_time = volume.get("CreateTime")
            tags = parse_tags(volume.get("Tags", []))

            if create_time:
                if create_time.tzinfo is None:
                    create_time = create_time.replace(tzinfo=timezone.utc)
                else:
                    create_time = create_time.astimezone(timezone.utc)
                idle_hours = max((now_utc - create_time).total_seconds() / 3600.0, 0.0)
            else:
                idle_hours = 0.0

            hourly_cost, monthly_waste = calculate_ebs_waste(size_gb)
            eligible = is_tag_truthy(tags, TAG_ELIGIBLE)
            do_not_stop = is_tag_truthy(tags, TAG_DO_NOT_STOP)

            action_taken = "FLAGGED_FOR_REMEDIATION" if (eligible and not do_not_stop) else "FLAGGED_FOR_REVIEW"
            if do_not_stop:
                action_taken = "PROTECTED_BY_DO_NOT_STOP_TAG"

            flagged.append({
                "resource_id": vol_id,
                "resource_type": "EBS",
                "resource_state": "available",
                "idle_duration_hours": round(idle_hours, 2),
                "estimated_hourly_cost_usd": hourly_cost,
                "estimated_monthly_waste_usd": monthly_waste,
                "status": STATUS_FLAGGED,
                "eligible_for_remediation": eligible,
                "do_not_stop": do_not_stop,
                "action_taken": action_taken,
                "tags": tags,
                "metadata": {
                    "size_gb": size_gb,
                    "volume_type": volume.get("VolumeType", "gp2"),
                }
            })

    return flagged


def scan_elastic_ips_impl(ec2_client) -> list[dict]:
    """Scan all Elastic IPs and flag unassociated addresses."""
    flagged = []
    response = ec2_client.describe_addresses()
    addresses = response.get("Addresses", [])

    for addr in addresses:
        # Check association
        association_id = addr.get("AssociationId")
        instance_id = addr.get("InstanceId")
        network_interface_id = addr.get("NetworkInterfaceId")

        if not association_id and not instance_id and not network_interface_id:
            alloc_id = addr.get("AllocationId") or addr.get("PublicIp")
            public_ip = addr.get("PublicIp", "")
            tags = parse_tags(addr.get("Tags", []))

            hourly_cost, monthly_waste = calculate_eip_waste()
            eligible = is_tag_truthy(tags, TAG_ELIGIBLE)
            do_not_stop = is_tag_truthy(tags, TAG_DO_NOT_STOP)

            action_taken = "FLAGGED_FOR_REMEDIATION" if (eligible and not do_not_stop) else "FLAGGED_FOR_REVIEW"
            if do_not_stop:
                action_taken = "PROTECTED_BY_DO_NOT_STOP_TAG"

            flagged.append({
                "resource_id": alloc_id,
                "resource_type": "EIP",
                "resource_state": "unassociated",
                "idle_duration_hours": 0.0,
                "estimated_hourly_cost_usd": hourly_cost,
                "estimated_monthly_waste_usd": monthly_waste,
                "status": STATUS_FLAGGED,
                "eligible_for_remediation": eligible,
                "do_not_stop": do_not_stop,
                "action_taken": action_taken,
                "tags": tags,
                "metadata": {
                    "public_ip": public_ip,
                    "domain": addr.get("Domain", "vpc"),
                }
            })

    return flagged


def scan_account(
    ec2_client=None,
    dynamodb_resource=None,
    sns_client=None,
    sts_client=None,
    idle_threshold_hours=None,
    force_idle=None,
    region=None,
    publish_alerts=True
) -> dict:
    """Execute complete resource scan across EC2, EBS, and EIP."""
    now_utc = datetime.now(timezone.utc)
    scan_id = str(uuid.uuid4())
    scan_timestamp = now_utc.isoformat()
    current_region = region or DEFAULT_REGION

    if ec2_client is None:
        ec2_client = boto3.client("ec2", region_name=current_region)

    account_id = get_account_id(sts_client)
    threshold = IDLE_THRESHOLD_HOURS if idle_threshold_hours is None else float(idle_threshold_hours)
    force = DEMO_FORCE_IDLE if force_idle is None else bool(force_idle)

    logger.info(f"Starting FinOps Cost Guardian scan {scan_id} in {current_region} (threshold={threshold}h, force={force})")

    flagged_resources = []

    # 1. Scan EC2 instances
    ec2_flagged = scan_ec2_instances_impl(ec2_client, threshold, force, now_utc)
    flagged_resources.extend(ec2_flagged)

    # 2. Scan EBS volumes
    ebs_flagged = scan_ebs_volumes_impl(ec2_client, now_utc)
    flagged_resources.extend(ebs_flagged)

    # 3. Scan Elastic IPs
    eip_flagged = scan_elastic_ips_impl(ec2_client)
    flagged_resources.extend(eip_flagged)

    # 4. Write records to DynamoDB
    if flagged_resources:
        for resource in flagged_resources:
            record = {
                "resource_id": resource["resource_id"],
                "scan_timestamp": scan_timestamp,
                "scan_id": scan_id,
                "resource_type": resource["resource_type"],
                "region": current_region,
                "resource_state": resource["resource_state"],
                "idle_duration_hours": resource["idle_duration_hours"],
                "estimated_hourly_cost_usd": resource["estimated_hourly_cost_usd"],
                "estimated_monthly_waste_usd": resource["estimated_monthly_waste_usd"],
                "status": STATUS_FLAGGED,
                "eligible_for_remediation": resource["eligible_for_remediation"],
                "do_not_stop": resource["do_not_stop"],
                "action_taken": resource["action_taken"],
                "tags": resource["tags"],
                "scanner_version": SCANNER_VERSION,
                "account_id": account_id,
            }
            log_record_to_dynamodb(record, dynamodb_resource=dynamodb_resource)

        # Send SNS alert
        if publish_alerts and SNS_TOPIC_ARN:
            subject = f"[FinOps Cost Guardian] ALERT — {len(flagged_resources)} Idle Resource(s) Detected"
            message = format_scan_alert_email(flagged_resources, scan_id, scan_timestamp)
            publish_sns_alert(subject, message, sns_client=sns_client)
    else:
        # CLEAN scan summary logged to DynamoDB
        clean_record = {
            "resource_id": f"SCAN_SUMMARY_{scan_timestamp}",
            "scan_timestamp": scan_timestamp,
            "scan_id": scan_id,
            "resource_type": "SCAN_SUMMARY",
            "region": current_region,
            "resource_state": "clean",
            "idle_duration_hours": 0.0,
            "estimated_hourly_cost_usd": 0.0,
            "estimated_monthly_waste_usd": 0.0,
            "status": STATUS_CLEAN,
            "eligible_for_remediation": False,
            "do_not_stop": False,
            "action_taken": "CLEAN_SCAN_NO_IDLE_RESOURCES",
            "tags": {},
            "scanner_version": SCANNER_VERSION,
            "account_id": account_id,
        }
        log_record_to_dynamodb(clean_record, dynamodb_resource=dynamodb_resource)
        logger.info(f"Clean scan logged to DynamoDB: {scan_id}")

    total_monthly_waste = sum(r["estimated_monthly_waste_usd"] for r in flagged_resources)
    return {
        "scan_id": scan_id,
        "scan_timestamp": scan_timestamp,
        "status": STATUS_FLAGGED if flagged_resources else STATUS_CLEAN,
        "flagged_count": len(flagged_resources),
        "total_monthly_waste_usd": round(total_monthly_waste, 2),
        "resources": flagged_resources,
    }


def lambda_handler(event, context):
    """Entry point for AWS Lambda / EventBridge invocation."""
    logger.info(f"ResourceScanner invoked with event: {event}")

    # Allow event payload overrides (useful for manual test triggers or demo modes)
    event = event or {}
    override_threshold = event.get("idle_threshold_hours")
    override_force = event.get("force_idle")

    result = scan_account(
        idle_threshold_hours=override_threshold,
        force_idle=override_force
    )

    return {
        "statusCode": 200,
        "body": result
    }
