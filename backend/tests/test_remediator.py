"""
Moto unit tests for Remediator Lambda.
Covers:
  - Stopping EC2 instance tagged eligible-for-remediation=true
  - Strict Exclusion Guard: DoNotStop=true is NEVER modified (SKIPPED_DO_NOT_STOP)
  - Deleting unattached EBS volume tagged eligible-for-remediation=true
  - Preserving EBS volume tagged DoNotStop=true
  - Releasing unassociated Elastic IP
  - Dry-Run Simulation Mode: zero AWS mutations when DRY_RUN=true
  - Skipping resources lacking opt-in tag (SKIPPED_NOT_ELIGIBLE)
"""

import boto3
from botocore.exceptions import ClientError
from moto import mock_aws
import pytest

from remediator import (
    evaluate_and_remediate_single,
    remediate_all,
    lambda_handler,
)
from common import (
    TABLE_NAME,
    STATUS_REMEDIATED,
    STATUS_SKIPPED_DO_NOT_STOP,
    STATUS_SKIPPED_NOT_ELIGIBLE,
    STATUS_DRY_RUN_SIMULATED,
)


@mock_aws
def test_stop_idle_ec2_instance_eligible():
    """Verify EC2 instance tagged eligible-for-remediation=true is stopped."""
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
    res = ec2.run_instances(
        ImageId="ami-12345678",
        InstanceType="t2.micro",
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "eligible-for-remediation", "Value": "true"}
            ]
        }]
    )
    instance_id = res["Instances"][0]["InstanceId"]

    outcome = evaluate_and_remediate_single(
        resource_id=instance_id,
        resource_type="EC2",
        dry_run=False,
        ec2_client=ec2,
        dynamodb_resource=dynamodb
    )

    assert outcome["status"] == STATUS_REMEDIATED
    assert "Stopped EC2 instance" in outcome["action_taken"]

    # Verify instance state in EC2
    desc = ec2.describe_instances(InstanceIds=[instance_id])
    state = desc["Reservations"][0]["Instances"][0]["State"]["Name"]
    assert state in ("stopping", "stopped")


@mock_aws
def test_do_not_stop_exclusion_guard_strict():
    """Verify DoNotStop=true strictly blocks remediation even if eligible tag is set."""
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
    res = ec2.run_instances(
        ImageId="ami-12345678",
        InstanceType="t2.micro",
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "eligible-for-remediation", "Value": "true"},
                {"Key": "DoNotStop", "Value": "true"}
            ]
        }]
    )
    instance_id = res["Instances"][0]["InstanceId"]

    outcome = evaluate_and_remediate_single(
        resource_id=instance_id,
        resource_type="EC2",
        dry_run=False,
        ec2_client=ec2,
        dynamodb_resource=dynamodb
    )

    assert outcome["status"] == STATUS_SKIPPED_DO_NOT_STOP
    assert "protected by DoNotStop" in outcome["action_taken"]

    # Verify instance state remains running
    desc = ec2.describe_instances(InstanceIds=[instance_id])
    state = desc["Reservations"][0]["Instances"][0]["State"]["Name"]
    assert state == "running"


@mock_aws
def test_delete_unattached_ebs_volume_eligible():
    """Verify unattached EBS volume tagged eligible-for-remediation=true is deleted."""
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
    vol_res = ec2.create_volume(
        AvailabilityZone="us-east-1a",
        Size=10,
        TagSpecifications=[{
            "ResourceType": "volume",
            "Tags": [
                {"Key": "eligible-for-remediation", "Value": "true"}
            ]
        }]
    )
    vol_id = vol_res["VolumeId"]

    outcome = evaluate_and_remediate_single(
        resource_id=vol_id,
        resource_type="EBS",
        dry_run=False,
        ec2_client=ec2,
        dynamodb_resource=dynamodb
    )

    assert outcome["status"] == STATUS_REMEDIATED
    assert "Deleted unattached EBS volume" in outcome["action_taken"]

    # Verify volume no longer exists
    with pytest.raises(ClientError) as exc_info:
        ec2.describe_volumes(VolumeIds=[vol_id])
    assert "InvalidVolume.NotFound" in str(exc_info.value)


@mock_aws
def test_do_not_stop_ebs_volume_preserved():
    """Verify unattached EBS volume tagged DoNotStop=true is preserved."""
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
    vol_res = ec2.create_volume(
        AvailabilityZone="us-east-1a",
        Size=10,
        TagSpecifications=[{
            "ResourceType": "volume",
            "Tags": [
                {"Key": "DoNotStop", "Value": "true"}
            ]
        }]
    )
    vol_id = vol_res["VolumeId"]

    outcome = evaluate_and_remediate_single(
        resource_id=vol_id,
        resource_type="EBS",
        dry_run=False,
        ec2_client=ec2,
        dynamodb_resource=dynamodb
    )

    assert outcome["status"] == STATUS_SKIPPED_DO_NOT_STOP

    # Volume must still exist
    vol_desc = ec2.describe_volumes(VolumeIds=[vol_id])
    assert len(vol_desc["Volumes"]) == 1


@mock_aws
def test_release_unassociated_elastic_ip_eligible():
    """Verify unassociated Elastic IP tagged eligible-for-remediation=true is released."""
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
    eip_res = ec2.allocate_address(
        Domain="vpc",
        TagSpecifications=[{
            "ResourceType": "elastic-ip",
            "Tags": [
                {"Key": "eligible-for-remediation", "Value": "true"}
            ]
        }]
    )
    alloc_id = eip_res["AllocationId"]

    outcome = evaluate_and_remediate_single(
        resource_id=alloc_id,
        resource_type="EIP",
        dry_run=False,
        ec2_client=ec2,
        dynamodb_resource=dynamodb
    )

    assert outcome["status"] == STATUS_REMEDIATED

    # Address must be released
    all_addrs = ec2.describe_addresses().get("Addresses", [])
    assert not any(a.get("AllocationId") == alloc_id for a in all_addrs)


@mock_aws
def test_dry_run_mode_no_mutations():
    """Verify that DRY_RUN=true simulates actions without modifying any AWS resources."""
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
    res = ec2.run_instances(
        ImageId="ami-12345678",
        InstanceType="t2.micro",
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "eligible-for-remediation", "Value": "true"}
            ]
        }]
    )
    instance_id = res["Instances"][0]["InstanceId"]

    outcome = evaluate_and_remediate_single(
        resource_id=instance_id,
        resource_type="EC2",
        dry_run=True,
        ec2_client=ec2,
        dynamodb_resource=dynamodb
    )

    assert outcome["status"] == STATUS_DRY_RUN_SIMULATED
    assert "SIMULATED" in outcome["action_taken"]

    # Assert instance was NOT stopped
    desc = ec2.describe_instances(InstanceIds=[instance_id])
    state = desc["Reservations"][0]["Instances"][0]["State"]["Name"]
    assert state == "running"


@mock_aws
def test_missing_eligible_tag_skipped():
    """Verify resource without eligible-for-remediation=true tag is skipped."""
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
    res = ec2.run_instances(
        ImageId="ami-12345678",
        InstanceType="t2.micro",
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Env", "Value": "production"}]
        }]
    )
    instance_id = res["Instances"][0]["InstanceId"]

    outcome = evaluate_and_remediate_single(
        resource_id=instance_id,
        resource_type="EC2",
        dry_run=False,
        ec2_client=ec2,
        dynamodb_resource=dynamodb
    )

    assert outcome["status"] == STATUS_SKIPPED_NOT_ELIGIBLE
    assert "missing eligible-for-remediation" in outcome["action_taken"]
