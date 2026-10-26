"""
FinOps Cost Guardian — ReportAPI Lambda Function URL Handler
Exposes secure RESTful endpoints for the modern web dashboard:
  - GET  /history   -> Historical scan logs & executive KPI rollups from DynamoDB
  - POST /scan      -> Synchronous trigger of ResourceScanner
  - POST /remediate -> Synchronous trigger of Remediator (supports dry_run)
Protected with CORS headers and 'x-api-key' secret header authentication.
"""

import os
import json
import logging
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError

from common import (
    TABLE_NAME,
    DEFAULT_REGION,
    API_SECRET_KEY,
    STATUS_FLAGGED,
    STATUS_REMEDIATED,
    STATUS_SKIPPED_DO_NOT_STOP,
    STATUS_DRY_RUN_SIMULATED,
    get_dynamodb_table,
    decimal_to_float,
    DecimalEncoder,
)

logger = logging.getLogger("report_api")
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, x-api-key, Authorization",
    "Access-Control-Max-Age": "86400",
    "Content-Type": "application/json",
}


def build_response(status_code: int, body: dict) -> dict:
    """Format standard API response with CORS and serialized JSON."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, cls=DecimalEncoder)
    }


def extract_header(headers: dict, key_name: str) -> str | None:
    """Case-insensitive header extraction."""
    if not headers:
        return None
    for k, v in headers.items():
        if k.lower() == key_name.lower():
            return v
    return None


def authenticate_request(headers: dict) -> bool:
    """Verify x-api-key matches configured secret key."""
    provided_key = extract_header(headers, "x-api-key")
    configured_key = os.environ.get("API_SECRET_KEY", API_SECRET_KEY)
    if not provided_key or not configured_key:
        return False
    return provided_key.strip() == configured_key.strip()


def compute_summary_kpis(records: list[dict]) -> dict:
    """Aggregate executive KPIs from scan history."""
    total_waste_saved = 0.0
    active_flagged = 0
    protected_count = 0
    eligible_count = 0
    ec2_flagged = 0
    ebs_flagged = 0
    eip_flagged = 0

    # Only count recent non-summary records for active stats
    for r in records:
        rtype = r.get("resource_type", "")
        status = r.get("status", "")
        monthly_waste = float(r.get("estimated_monthly_waste_usd", 0.0) or 0.0)

        if status in (STATUS_REMEDIATED, STATUS_DRY_RUN_SIMULATED):
            total_waste_saved += monthly_waste
        elif status == STATUS_FLAGGED:
            active_flagged += 1
            if rtype == "EC2":
                ec2_flagged += 1
            elif rtype == "EBS":
                ebs_flagged += 1
            elif rtype == "EIP":
                eip_flagged += 1

        if r.get("do_not_stop") is True:
            protected_count += 1
        elif r.get("eligible_for_remediation") is True:
            eligible_count += 1

    return {
        "estimated_waste_saved_usd": round(total_waste_saved, 2),
        "active_flagged_total": active_flagged,
        "flagged_breakdown": {
            "ec2": ec2_flagged,
            "ebs": ebs_flagged,
            "eip": eip_flagged,
        },
        "tag_governance": {
            "eligible_for_remediation": eligible_count,
            "protected_do_not_stop": protected_count,
        },
        "operating_cost_usd": "0.00",
        "budget_tripwire_limit_usd": "1.00",
        "budget_status": "OK",
    }


def handle_get_history(dynamodb_resource=None) -> dict:
    """Fetch scan history from DynamoDB and compute summary metrics."""
    try:
        table = get_dynamodb_table(dynamodb_resource=dynamodb_resource)
        response = table.scan(Limit=100)
        items = response.get("Items", [])

        # Sort descending by scan_timestamp
        items.sort(key=lambda x: str(x.get("scan_timestamp", "")), reverse=True)
        converted_items = [decimal_to_float(item) for item in items]
        summary = compute_summary_kpis(converted_items)

        return build_response(200, {
            "status": "success",
            "count": len(converted_items),
            "summary": summary,
            "records": converted_items,
        })
    except Exception as e:
        logger.error(f"Error fetching history from DynamoDB: {e}", exc_info=True)
        return build_response(500, {"error": f"Failed to retrieve scan history: {str(e)}"})


def handle_post_scan(event: dict, lambda_client=None) -> dict:
    """Trigger ResourceScanner synchronously."""
    try:
        scanner_fn_name = os.environ.get("RESOURCE_SCANNER_FUNCTION_NAME", "ResourceScanner")

        # In AWS environment, invoke Lambda function
        if lambda_client is None:
            lambda_client = boto3.client("lambda", region_name=DEFAULT_REGION)

        try:
            body_payload = event.get("body")
            if isinstance(body_payload, str):
                body_payload = json.loads(body_payload) if body_payload else {}
            elif body_payload is None:
                body_payload = {}

            response = lambda_client.invoke(
                FunctionName=scanner_fn_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(body_payload)
            )
            raw_payload = response["Payload"].read().decode("utf-8")
            result = json.loads(raw_payload)
            return build_response(200, {
                "status": "success",
                "message": "ResourceScanner completed successfully",
                "result": result
            })
        except (ClientError, Exception) as invoke_err:
            # Fallback to direct python invocation (useful during tests or local simulation)
            logger.info(f"Direct import fallback for ResourceScanner: {invoke_err}")
            from resource_scanner import scan_account
            direct_result = scan_account()
            return build_response(200, {
                "status": "success",
                "message": "ResourceScanner executed via direct runner",
                "result": direct_result
            })

    except Exception as e:
        logger.error(f"Error triggering scan: {e}", exc_info=True)
        return build_response(500, {"error": f"Failed to trigger scan: {str(e)}"})


def handle_post_remediate(event: dict, lambda_client=None) -> dict:
    """Trigger Remediator synchronously."""
    try:
        remediator_fn_name = os.environ.get("REMEDIATOR_FUNCTION_NAME", "Remediator")
        body_payload = event.get("body")
        if isinstance(body_payload, str):
            body_payload = json.loads(body_payload) if body_payload else {}
        elif body_payload is None:
            body_payload = {}

        if lambda_client is None:
            lambda_client = boto3.client("lambda", region_name=DEFAULT_REGION)

        try:
            response = lambda_client.invoke(
                FunctionName=remediator_fn_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(body_payload)
            )
            raw_payload = response["Payload"].read().decode("utf-8")
            result = json.loads(raw_payload)
            return build_response(200, {
                "status": "success",
                "message": "Remediator completed successfully",
                "result": result
            })
        except (ClientError, Exception) as invoke_err:
            # Fallback to direct python invocation
            logger.info(f"Direct import fallback for Remediator: {invoke_err}")
            from remediator import lambda_handler as remediator_handler
            direct_result = remediator_handler(body_payload, None)
            return build_response(200, {
                "status": "success",
                "message": "Remediator executed via direct runner",
                "result": direct_result.get("body", direct_result)
            })

    except Exception as e:
        logger.error(f"Error triggering remediator: {e}", exc_info=True)
        return build_response(500, {"error": f"Failed to trigger remediator: {str(e)}"})


def lambda_handler(event, context):
    """Entry point for Lambda Function URL."""
    logger.info(f"ReportAPI received request: {event.get('rawPath') or event.get('path')}")

    # 1. Determine HTTP method
    http_method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    ).upper()

    # 2. Handle CORS preflight OPTIONS request immediately
    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"status": "ok", "message": "CORS preflight OK"})
        }

    # 3. Check Authentication (x-api-key)
    headers = event.get("headers", {})
    if not authenticate_request(headers):
        logger.warning("Unauthorized access attempt: invalid or missing x-api-key")
        return build_response(401, {
            "error": "Unauthorized: Invalid or missing x-api-key header",
            "hint": "Please supply 'x-api-key' matching your Cost Guardian API secret"
        })

    # 4. Route request based on path and method
    raw_path = (
        event.get("rawPath")
        or event.get("path")
        or event.get("requestContext", {}).get("http", {}).get("path")
        or "/history"
    ).rstrip("/")

    # Normalize path suffix
    if not raw_path or raw_path.endswith("/history") or raw_path == "":
        if http_method == "GET":
            return handle_get_history()
        else:
            return build_response(405, {"error": f"Method {http_method} not allowed for /history"})

    elif raw_path.endswith("/scan"):
        if http_method == "POST":
            return handle_post_scan(event)
        else:
            return build_response(405, {"error": f"Method {http_method} not allowed for /scan"})

    elif raw_path.endswith("/remediate"):
        if http_method == "POST":
            return handle_post_remediate(event)
        else:
            return build_response(405, {"error": f"Method {http_method} not allowed for /remediate"})

    return build_response(404, {"error": f"Path not found: {raw_path}"})
