"""
Shared test configuration, fixtures, and moto AWS mock decorators for FinOps Cost Guardian.
"""

import os
import sys
from pathlib import Path
import pytest
import boto3
from moto import mock_aws

# Ensure backend/src is on the import path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Mock environment variables
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing-access-key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing-secret-key"
os.environ["AWS_SECURITY_TOKEN"] = "testing-token"
os.environ["AWS_SESSION_TOKEN"] = "testing-session-token"
os.environ["DYNAMODB_TABLE_NAME"] = "cost-guardian-scan-log"
os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:cost-guardian-alerts"
os.environ["API_SECRET_KEY"] = "test-secret-key-123"
os.environ["IDLE_THRESHOLD_HOURS"] = "12"
os.environ["DEMO_FORCE_IDLE"] = "false"
os.environ["DRY_RUN"] = "false"


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb_mock(aws_credentials):
    """Set up mocked DynamoDB cost-guardian-scan-log table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="cost-guardian-scan-log",
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
        yield dynamodb


@pytest.fixture
def sns_mock(aws_credentials):
    """Set up mocked SNS topic cost-guardian-alerts."""
    with mock_aws():
        sns = boto3.client("sns", region_name="us-east-1")
        topic = sns.create_topic(Name="cost-guardian-alerts")
        topic_arn = topic["TopicArn"]
        os.environ["SNS_TOPIC_ARN"] = topic_arn
        yield sns, topic_arn


@pytest.fixture
def ec2_mock(aws_credentials):
    """Set up mocked EC2 client."""
    with mock_aws():
        ec2 = boto3.client("ec2", region_name="us-east-1")
        yield ec2
