"""
FinOps Cost Guardian - Common Utilities, Constants & Shared Helpers
"""

import os
import json
import logging
from decimal import Decimal
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("cost_guardian")
logger.setLevel(logging.INFO)

# Environment variables & Defaults
TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "cost-guardian-scan-log")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
DEFAULT_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
IDLE_THRESHOLD_HOURS = float(os.environ.get("IDLE_THRESHOLD_HOURS", "12"))
DEMO_FORCE_IDLE = os.environ.get("DEMO_FORCE_IDLE", "false").lower() in ("true", "1", "yes")
DRY_RUN_DEFAULT = os.environ.get("DRY_RUN", "false").lower() in ("true", "1", "yes")
API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "cost-guardian-secret-2025")
SCANNER_VERSION = "1.2.0"

# Governance Tags
TAG_ELIGIBLE = "eligible-for-remediation"
TAG_DO_NOT_STOP = "DoNotStop"
TRUTHY_VALUES = {"true", "1", "yes", "enabled"}

# Status Constants
STATUS_CLEAN = "CLEAN"
STATUS_FLAGGED = "FLAGGED"
STATUS_REMEDIATED = "REMEDIATED"
STATUS_SKIPPED_DO_NOT_STOP = "SKIPPED_DO_NOT_STOP"
STATUS_SKIPPED_NOT_ELIGIBLE = "SKIPPED_NOT_ELIGIBLE"
STATUS_DRY_RUN_SIMULATED = "DRY_RUN_SIMULATED"

# Cost reference table (USD per hour)
EC2_HOURLY_COSTS = {
    "t2.nano": 0.0058,
    "t2.micro": 0.0116,
    "t2.small": 0.023,
    "t2.medium": 0.0464,
    "t3.nano": 0.0052,
    "t3.micro": 0.0104,
    "t3.small": 0.0208,
    "t3.medium": 0.0416,
}
DEFAULT_EC2_HOURLY = 0.0116  # fallback to t2.micro pricing
EBS_MONTHLY_PER_GB = 0.10    # gp2/gp3 standard $0.10/GB-month
EIP_HOURLY_COST = 0.005      # $0.005/hr unassociated idle charge
HOURS_PER_MONTH = 730


def get_ec2_hourly_cost(instance_type: str) -> float:
    return EC2_HOURLY_COSTS.get(instance_type.lower(), DEFAULT_EC2_HOURLY)


def calculate_ec2_waste(instance_type: str, idle_hours: float) -> tuple[float, float]:
    hourly = get_ec2_hourly_cost(instance_type)
    monthly = round(hourly * HOURS_PER_MONTH, 2)
    return hourly, monthly


def calculate_ebs_waste(size_gb: int) -> tuple[float, float]:
    monthly = round(size_gb * EBS_MONTHLY_PER_GB, 2)
    hourly = round(monthly / HOURS_PER_MONTH, 4)
    return hourly, monthly


def calculate_eip_waste() -> tuple[float, float]:
    hourly = EIP_HOURLY_COST
    monthly = round(hourly * 720, 2)  # 720 hours * $0.005/hr = $3.60/month
    return hourly, monthly


def parse_tags(tags_input) -> dict[str, str]:
    """Normalize tags from AWS API format or dict to a standard dictionary."""
    if not tags_input:
        return {}
    if isinstance(tags_input, dict):
        return {str(k): str(v) for k, v in tags_input.items()}
    if isinstance(tags_input, list):
        result = {}
        for tag in tags_input:
            if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                result[str(tag["Key"])] = str(tag["Value"])
        return result
    return {}


def is_tag_truthy(tags_dict: dict[str, str], tag_key: str) -> bool:
    """Case-insensitive lookup for truthy tag values."""
    if not tags_dict:
        return False
    for k, v in tags_dict.items():
        if k.lower() == tag_key.lower():
            return str(v).strip().lower() in TRUTHY_VALUES
    return False


def float_to_decimal(obj):
    """Recursively convert float values to Decimal for DynamoDB serialization."""
    if isinstance(obj, float):
        return Decimal(str(round(obj, 4)))
    elif isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [float_to_decimal(v) for v in obj]
    return obj


def decimal_to_float(obj):
    """Recursively convert Decimal objects to float/int for JSON serialization."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(v) for v in obj]
    return obj


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            if o % 1 == 0:
                return int(o)
            return float(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def get_dynamodb_table(table_name=None, dynamodb_resource=None):
    name = table_name or TABLE_NAME
    if dynamodb_resource is None:
        dynamodb_resource = boto3.resource("dynamodb", region_name=DEFAULT_REGION)
    return dynamodb_resource.Table(name)


def log_record_to_dynamodb(record: dict, table_name=None, dynamodb_resource=None) -> bool:
    """Write an auditable record to the DynamoDB scan log table."""
    try:
        table = get_dynamodb_table(table_name=table_name, dynamodb_resource=dynamodb_resource)
        converted_item = float_to_decimal(record)
        table.put_item(Item=converted_item)
        return True
    except Exception as e:
        logger.error(f"Failed to write record to DynamoDB: {e}", exc_info=True)
        return False


def publish_sns_alert(subject: str, message: str, topic_arn=None, sns_client=None) -> bool:
    """Publish a formatted email notification to SNS."""
    arn = topic_arn or SNS_TOPIC_ARN
    if not arn:
        logger.info("SNS_TOPIC_ARN not configured, skipping alert publish.")
        return False

    try:
        if sns_client is None:
            sns_client = boto3.client("sns", region_name=DEFAULT_REGION)
        sns_client.publish(
            TopicArn=arn,
            Subject=subject[:100],  # SNS subject limit is 100 characters
            Message=message
        )
        logger.info(f"SNS alert published successfully to {arn}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish SNS alert: {e}", exc_info=True)
        return False


def format_scan_alert_email(flagged_resources: list[dict], scan_id: str, timestamp: str) -> str:
    """Format SNS alert email matching project report format."""
    total_monthly = sum(r.get("estimated_monthly_waste_usd", 0.0) for r in flagged_resources)
    lines = [
        "==================================================",
        "  FINOPS COST GUARDIAN — IDLE RESOURCE ALERT",
        "==================================================",
        f"Scan ID:        {scan_id}",
        f"Scan Timestamp: {timestamp}",
        f"Total Flagged:  {len(flagged_resources)} resource(s)",
        f"Est. Waste:     ${total_monthly:.2f}/month",
        "--------------------------------------------------\n"
    ]

    for idx, r in enumerate(flagged_resources, start=1):
        lines.append(f"[{idx}] {r.get('resource_type')} — {r.get('resource_id')}")
        lines.append(f"    Region:          {r.get('region')}")
        lines.append(f"    State:           {r.get('resource_state')}")
        lines.append(f"    Idle Duration:   {r.get('idle_duration_hours', 0):.1f} hours")
        lines.append(f"    Est. Monthly:    ${r.get('estimated_monthly_waste_usd', 0):.2f}")
        lines.append(f"    Eligible Tag:    {r.get('eligible_for_remediation')}")
        lines.append(f"    DoNotStop Tag:   {r.get('do_not_stop')}")
        lines.append(f"    Action Taken:    {r.get('action_taken')}")
        tags_str = ", ".join(f"{k}={v}" for k, v in r.get("tags", {}).items()) or "None"
        lines.append(f"    Tags:            {tags_str}")
        lines.append("")

    lines.append("--------------------------------------------------")
    lines.append("This alert was generated automatically by FinOps Cost Guardian.")
    lines.append("Core Engine operates within AWS Always Free Tier ($0.00/mo).")
    lines.append("To remediate, review tags or trigger Remediator via Dashboard.")
    lines.append("==================================================")
    return "\n".join(lines)


def format_remediation_email(remediated_items: list[dict], dry_run: bool = False) -> str:
    """Format SNS email confirming remediation actions."""
    mode_str = "[DRY-RUN SIMULATION]" if dry_run else "[LIVE ACTION APPLIED]"
    lines = [
        "==================================================",
        f"  FINOPS COST GUARDIAN — REMEDIATION REPORT {mode_str}",
        "==================================================",
        f"Timestamp:       {datetime.now(timezone.utc).isoformat()}",
        f"Total Processed: {len(remediated_items)} resource(s)",
        "--------------------------------------------------\n"
    ]

    for idx, item in enumerate(remediated_items, start=1):
        lines.append(f"[{idx}] {item.get('resource_type')} — {item.get('resource_id')}")
        lines.append(f"    Status:       {item.get('status')}")
        lines.append(f"    Action:       {item.get('action_taken')}")
        lines.append(f"    Est. Saved:   ${item.get('estimated_monthly_waste_usd', 0):.2f}/mo")
        lines.append(f"    DoNotStop:    {item.get('do_not_stop')}")
        lines.append(f"    Eligible:     {item.get('eligible_for_remediation')}")
        lines.append("")

    lines.append("--------------------------------------------------")
    lines.append("Automated remediation enforced by FinOps Cost Guardian.")
    lines.append("Exclusion rule: 'DoNotStop=true' resources are strictly preserved.")
    lines.append("==================================================")
    return "\n".join(lines)
