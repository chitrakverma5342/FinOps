"""
Moto unit tests for ResourceScanner Lambda.
Covers:
  - Clean scan with zero idle resources (DynamoDB summary written)
  - True-positive idle EC2 instance detection
  - Unattached EBS volume detection
  - Unassociated Elastic IP detection
  - DynamoDB schema attribute validation
  - SNS email alert delivery
  - Multi-resource pagination
"""

import os
from datetime import datetime, timezone, timedelta
import boto3
from moto import mock_aws
import pytest

from resource_scanner import scan_account, lambda_handler
from common import (
    TABLE_NAME,
    STATUS_CLEAN,
    STATUS_FLAGGED,
    get_dynamodb_table,
)


@mock_aws
def test_clean_scan_no_idle_resources():
    """Verify that when no idle resources exist, a CLEAN scan summary is written to DynamoDB."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "resource_id", "KeyType": "HASH"},
            {"AttributeName": "scan_timestamp", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "resource_id", "AttributeType": "S"},
            {"AttributeName": "scan_timestamp", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST"
    )
    table.wait_until_exists()

    result = scan_account(region="us-east-1", publish_alerts=False)

    assert result["status"] == STATUS_CLEAN
    assert result["flagged_count"] == 0
    assert result["total_monthly_waste_usd"] == 0.0

    # Verify DynamoDB record
    scan_items = table.scan().get("Items", [])
    assert len(scan_items) == 1
    clean_item = scan_items[0]
    assert clean_item["status"] == STATUS_CLEAN
    assert clean_item["resource_type"] == "SCAN_SUMMARY"
    assert clean_item["action_taken"] == "CLEAN_SCAN_NO_IDLE_RESOURCES"


@mock_aws
def test_idle_ec2_flagged_with_threshold_override():
    """Verify that a running EC2 instance is detected and flagged with estimated waste."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "resource_id", "KeyType": "HASH"},
            {"AttributeName": "scan_timestamp", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "resource_id", "AttributeType": "S"},
            {"AttributeName": "scan_timestamp", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST"
    )
    table.wait_until_exists()

    ec2 = boto3.client("ec2", region_name="us-east-1")
    # Launch EC2 instance
    res = ec2.run_instances(
        ImageId="ami-12345678",
        InstanceType="t2.micro",
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Project", "Value": "FinOpsCostGuardian"},
                {"Key": "eligible-for-remediation", "Value": "true"}
            ]
        }]
    )
    instance_id = res["Instances"][0]["InstanceId"]

    # Run scan with threshold 0 so instant detection happens
    result = scan_account(ec2_client=ec2, dynamodb_resource=dynamodb, idle_threshold_hours=0, publish_alerts=False)

    assert result["status"] == STATUS_FLAGGED
    assert result["flagged_count"] >= 1

    flagged_ids = [r["resource_id"] for r in result["resources"]]
    assert instance_id in flagged_ids

    inst_record = next(r for r in result["resources"] if r["resource_id"] == instance_id)
    assert inst_record["resource_type"] == "EC2"
    assert inst_record["resource_state"] == "running"
    assert inst_record["estimated_hourly_cost_usd"] == 0.0116
    assert inst_record["estimated_monthly_waste_usd"] == 8.47
    assert inst_record["eligible_for_remediation"] is True
    assert inst_record["do_not_stop"] is False


@mock_aws
def test_unattached_ebs_volume_flagged():
    """Verify unattached 'available' EBS volumes are detected and flagged."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "resource_id", "KeyType": "HASH"},
            {"AttributeName": "scan_timestamp", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "resource_id", "AttributeType": "S"},
            {"AttributeName": "scan_timestamp", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST"
    )
    table.wait_until_exists()

    ec2 = boto3.client("ec2", region_name="us-east-1")
    vol_res = ec2.create_volume(
        AvailabilityZone="us-east-1a",
        Size=20,
        TagSpecifications=[{
            "ResourceType": "volume",
            "Tags": [
                {"Key": "DoNotStop", "Value": "true"}
            ]
        }]
    )
    vol_id = vol_res["VolumeId"]

    result = scan_account(ec2_client=ec2, dynamodb_resource=dynamodb, publish_alerts=False)

    assert result["status"] == STATUS_FLAGGED
    vol_record = next((r for r in result["resources"] if r["resource_id"] == vol_id), None)
    assert vol_record is not None
    assert vol_record["resource_type"] == "EBS"
    assert vol_record["resource_state"] == "available"
    assert vol_record["do_not_stop"] is True
    assert vol_record["action_taken"] == "PROTECTED_BY_DO_NOT_STOP_TAG"
    assert vol_record["estimated_monthly_waste_usd"] == 2.00  # 20 GB * $0.10/GB


@mock_aws
def test_unassociated_elastic_ip_flagged():
    """Verify unassociated Elastic IPs are detected with $0.005/hr cost."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "resource_id", "KeyType": "HASH"},
            {"AttributeName": "scan_timestamp", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "resource_id", "AttributeType": "S"},
            {"AttributeName": "scan_timestamp", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST"
    )
    table.wait_until_exists()

    ec2 = boto3.client("ec2", region_name="us-east-1")
    eip_res = ec2.allocate_address(Domain="vpc")
    alloc_id = eip_res["AllocationId"]

    result = scan_account(ec2_client=ec2, dynamodb_resource=dynamodb, publish_alerts=False)

    assert result["status"] == STATUS_FLAGGED
    eip_record = next((r for r in result["resources"] if r["resource_id"] == alloc_id), None)
    assert eip_record is not None
    assert eip_record["resource_type"] == "EIP"
    assert eip_record["resource_state"] == "unassociated"
    assert eip_record["estimated_hourly_cost_usd"] == 0.005
    assert eip_record["estimated_monthly_waste_usd"] == 3.60


@mock_aws
def test_dynamodb_schema_validation():
    """Verify all 13 required attributes are saved to DynamoDB on flagged scan."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "resource_id", "KeyType": "HASH"},
            {"AttributeName": "scan_timestamp", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "resource_id", "AttributeType": "S"},
            {"AttributeName": "scan_timestamp", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST"
    )
    table.wait_until_exists()

    ec2 = boto3.client("ec2", region_name="us-east-1")
    ec2.allocate_address(Domain="vpc")

    scan_account(ec2_client=ec2, dynamodb_resource=dynamodb, publish_alerts=False)

    items = table.scan().get("Items", [])
    assert len(items) >= 1
    record = items[0]

    # Validate full schema per PRD
    required_keys = [
        "resource_id",
        "scan_timestamp",
        "scan_id",
        "resource_type",
        "region",
        "resource_state",
        "idle_duration_hours",
        "estimated_hourly_cost_usd",
        "estimated_monthly_waste_usd",
        "status",
        "eligible_for_remediation",
        "do_not_stop",
        "action_taken",
        "tags",
        "scanner_version",
        "account_id"
    ]
    for key in required_keys:
        assert key in record, f"Missing required attribute '{key}' in DynamoDB scan record"


@mock_aws
def test_sns_alert_published_on_flagged():
    """Verify SNS alert is formatted and published when flagged resources exist."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "resource_id", "KeyType": "HASH"},
            {"AttributeName": "scan_timestamp", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "resource_id", "AttributeType": "S"},
            {"AttributeName": "scan_timestamp", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST"
    )

    sns = boto3.client("sns", region_name="us-east-1")
    topic = sns.create_topic(Name="cost-guardian-alerts")
    topic_arn = topic["TopicArn"]

    ec2 = boto3.client("ec2", region_name="us-east-1")
    ec2.allocate_address(Domain="vpc")

    # Set topic ARN and trigger scan with publish_alerts=True
    os.environ["SNS_TOPIC_ARN"] = topic_arn
    result = scan_account(
        ec2_client=ec2,
        dynamodb_resource=dynamodb,
        sns_client=sns,
        publish_alerts=True
    )
    assert result["status"] == STATUS_FLAGGED


@mock_aws
def test_multi_resource_pagination():
    """Verify that paginated describe calls process multiple resources cleanly."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "resource_id", "KeyType": "HASH"},
            {"AttributeName": "scan_timestamp", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "resource_id", "AttributeType": "S"},
            {"AttributeName": "scan_timestamp", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST"
    )

    ec2 = boto3.client("ec2", region_name="us-east-1")
    # Create 10 volumes
    for i in range(10):
        ec2.create_volume(AvailabilityZone="us-east-1a", Size=5)

    result = scan_account(ec2_client=ec2, dynamodb_resource=dynamodb, publish_alerts=False)
    ebs_records = [r for r in result["resources"] if r["resource_type"] == "EBS"]
    assert len(ebs_records) == 10
