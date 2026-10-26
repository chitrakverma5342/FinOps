"""
Unit tests for ReportAPI Lambda Function URL Handler.
Covers:
  - CORS headers on all responses
  - OPTIONS preflight handler
  - 401 Unauthorized on missing or invalid x-api-key header
  - GET /history retrieving scan logs and executive KPI rollups
  - POST /scan trigger
  - POST /remediate trigger
  - 404 Not Found handling
"""

import json
import os
import boto3
from moto import mock_aws
import pytest

from report_api import lambda_handler
from common import TABLE_NAME, STATUS_FLAGGED, STATUS_REMEDIATED, API_SECRET_KEY


@mock_aws
def test_cors_headers_present_on_all_responses():
    """Verify CORS headers are present even on unauthorized requests."""
    event = {
        "rawPath": "/history",
        "requestContext": {"http": {"method": "GET"}},
        "headers": {}
    }
    response = lambda_handler(event, None)
    assert "headers" in response
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"
    assert "x-api-key" in response["headers"]["Access-Control-Allow-Headers"]


def test_options_preflight_returns_200():
    """Verify OPTIONS preflight returns 200 without requiring auth."""
    event = {
        "rawPath": "/history",
        "requestContext": {"http": {"method": "OPTIONS"}},
        "headers": {}
    }
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"


def test_missing_api_key_returns_401():
    """Verify missing x-api-key returns 401 Unauthorized."""
    event = {
        "rawPath": "/history",
        "requestContext": {"http": {"method": "GET"}},
        "headers": {}
    }
    response = lambda_handler(event, None)
    assert response["statusCode"] == 401
    body = json.loads(response["body"])
    assert "Unauthorized" in body["error"]


def test_invalid_api_key_returns_401():
    """Verify incorrect x-api-key returns 401 Unauthorized."""
    event = {
        "rawPath": "/history",
        "requestContext": {"http": {"method": "GET"}},
        "headers": {"x-api-key": "wrong-secret-key"}
    }
    response = lambda_handler(event, None)
    assert response["statusCode"] == 401


@mock_aws
def test_history_endpoint_returns_records_and_kpis():
    """Verify GET /history reads DynamoDB and calculates executive KPIs."""
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

    # Seed test records
    table.put_item(Item={
        "resource_id": "i-0demo12345678",
        "scan_timestamp": "2025-01-15T12:00:00Z",
        "resource_type": "EC2",
        "status": STATUS_FLAGGED,
        "estimated_monthly_waste_usd": "8.47",
        "eligible_for_remediation": True,
        "do_not_stop": False
    })
    table.put_item(Item={
        "resource_id": "vol-0demo987654",
        "scan_timestamp": "2025-01-15T13:00:00Z",
        "resource_type": "EBS",
        "status": STATUS_REMEDIATED,
        "estimated_monthly_waste_usd": "2.00",
        "eligible_for_remediation": True,
        "do_not_stop": False
    })

    event = {
        "rawPath": "/history",
        "requestContext": {"http": {"method": "GET"}},
        "headers": {"x-api-key": API_SECRET_KEY}
    }
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["count"] == 2
    assert "summary" in body
    summary = body["summary"]
    assert summary["estimated_waste_saved_usd"] == 2.0
    assert summary["active_flagged_total"] == 1
    assert summary["operating_cost_usd"] == "0.00"
    assert summary["budget_tripwire_limit_usd"] == "1.00"


@mock_aws
def test_post_scan_endpoint():
    """Verify POST /scan triggers scanner and returns results."""
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

    event = {
        "rawPath": "/scan",
        "requestContext": {"http": {"method": "POST"}},
        "headers": {"x-api-key": API_SECRET_KEY},
        "body": json.dumps({"idle_threshold_hours": 0})
    }
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"


@mock_aws
def test_post_remediate_endpoint():
    """Verify POST /remediate triggers remediation logic."""
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

    event = {
        "rawPath": "/remediate",
        "requestContext": {"http": {"method": "POST"}},
        "headers": {"x-api-key": API_SECRET_KEY},
        "body": json.dumps({"dry_run": True, "resources": []})
    }
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"


def test_unknown_path_returns_404():
    """Verify invalid path returns 404."""
    event = {
        "rawPath": "/nonexistent",
        "requestContext": {"http": {"method": "GET"}},
        "headers": {"x-api-key": API_SECRET_KEY}
    }
    response = lambda_handler(event, None)
    assert response["statusCode"] == 404
