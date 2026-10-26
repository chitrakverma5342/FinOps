# FinOps Cost Guardian

> **Automated Idle-Resource Detection, Safe Remediation & Cost Governance on AWS**  
> *DevOps & Agile Cloud Optimization Platform*

[![CI](https://github.com/finops-cost-guardian/finops-cost-guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/finops-cost-guardian/finops-cost-guardian/actions)
[![AWS Always Free Tier](https://img.shields.io/badge/AWS%20Core%20Cost-%240.00%2Fmonth-emerald)](https://aws.amazon.com/free/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![Terraform 1.5+](https://img.shields.io/badge/Terraform-1.5%2B-purple)](https://www.terraform.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 1. Project Overview & Architecture

**FinOps Cost Guardian** continuously inspects an AWS account for idle or abandoned cloud resources:
- **Idle EC2 Instances:** Running compute past configured threshold (`12h` default, `0h` instant demo mode).
- **Unattached EBS Volumes:** Persistent block storage in `available` (unattached) state.
- **Unassociated Elastic IPs:** Static public IPv4 addresses incurring the `$0.005/hr` ($3.60/mo) idle charge.

Every scan outcome (both **CLEAN** account audits and **FLAGGED** idle findings) is written to DynamoDB for compliance tracking, broadcasted via SNS formatted email alerts, safely remediated based on strict tag governance, and visualized on an executive dark-mode FinOps Command Center.

### Architectural Workflow (Report Figure 1 Alignment)

```mermaid
flowchart TD
    EB["Amazon EventBridge<br/><code>cost-guardian-schedule</code><br/>(rate: 6 hours)"] -->|Scheduled / Manual Trigger| RS["AWS Lambda: ResourceScanner<br/>(Python 3.12 / Boto3)"]
    
    RS -->|DescribeInstances / DescribeVolumes / DescribeAddresses| EC2["Amazon EC2 & EBS & EIP APIs"]
    
    RS -->|Log CLEAN or FLAGGED Scans| DDB[("Amazon DynamoDB<br/><code>cost-guardian-scan-log</code><br/>(PK: resource_id, SK: scan_timestamp)")]
    
    RS -->|Dispatch Formatted Alert| SNS["Amazon SNS Topic<br/><code>cost-guardian-alerts</code>"]
    SNS -->|Verified Email| DEV["Engineer / FinOps Lead Inbox"]
    
    RS -.->|Auto-Remediate or Manual Trigger| REM["AWS Lambda: Remediator<br/>(Python 3.12 / Boto3)"]
    
    REM -->|Exclusion Check: DoNotStop=true?| GUARD{"Strict Exclusion<br/>Guard"}
    GUARD -->|Yes (DoNotStop=true)| SKIP["Log SKIPPED_DO_NOT_STOP<br/>(Strictly Preserved)"]
    GUARD -->|No + eligible-for-remediation=true| ACT["Execute Safe Action:<br/>• stop_instances()<br/>• delete_volume()<br/>• release_address()"]
    
    ACT -->|Update Status: REMEDIATED| DDB
    ACT -->|Remediation Confirmation| SNS
    
    UI["FinOps Command Center Dashboard<br/>(React + Vite + Recharts + Tailwind)"] -->|HTTPS + x-api-key| API["AWS Lambda: ReportAPI<br/>(Lambda Function URL + CORS)"]
    API -->|Read History & KPIs| DDB
    API -->|Trigger Scan / Remediate| RS
    
    BUDGET["AWS Budgets<br/><code>cost-guardian-monthly-budget</code><br/>($1.00 USD Tripwire)"] -.->|Spend Alert| DEV
```

---

## 2. Environment & Zero-Cost Architecture

- **Personal AWS Account ($200+ Promotional Credits):** Full IAM administrative control, eliminating AWS Academy `LabRole` blocks and 4-hour session timeouts.
- **The $0.00 Core Engine:** All core components (Lambda invocations, DynamoDB storage, SNS emails, EventBridge rules, and AWS Budgets) operate within the **AWS Always Free Tier ($0.00/month)**.
- **Credit Buffer:** The $200+ credit balance acts as an extra layer of safety for S3 static website hosting and transient demo fixtures.

| AWS Resource | Name / Identifier | Free Tier Limit | Operating Cost |
|---|---|---|---|
| Lambda Function 1 | `ResourceScanner` | 1M req / 400k GB-s free | $0.00 / month |
| Lambda Function 2 | `Remediator` | 1M req / 400k GB-s free | $0.00 / month |
| Lambda Function 3 | `ReportAPI` (Function URL) | 1M req / 400k GB-s free | $0.00 / month |
| DynamoDB Table | `cost-guardian-scan-log` | 25 GB / 25 WCU / 25 RCU | $0.00 / month |
| EventBridge Rule | `cost-guardian-schedule` | Free AWS-managed events | $0.00 / month |
| SNS Topic | `cost-guardian-alerts` | 1M publishes / 1k emails | $0.00 / month |
| AWS Budget | `cost-guardian-monthly-budget` | 2 budgets free | $0.00 / month |
| **Total Core Cost** | | | **$0.00 / month** |

---

## 3. Tag Governance & Safe-to-Fail Protocol

1. **Strict Exclusion Guard (`DoNotStop=true`):**
   - Any resource bearing `DoNotStop=true` (or any truthy value) is **NEVER** stopped, deleted, or released.
   - It is permanently recorded in DynamoDB as `SKIPPED_DO_NOT_STOP`.
2. **Opt-In Remediation Guard (`eligible-for-remediation=true`):**
   - Remediation only modifies resources that explicitly opt in.
3. **Dry-Run Simulation Mode (`DRY_RUN=true`):**
   - Calculates potential savings and logs `DRY_RUN_SIMULATED` to DynamoDB without mutating live cloud resources.

---

## 4. Quickstart: Local Verification & Moto Unit Tests

### 4.1 Run Backend Pytest Suite
```bash
# Navigate to backend and activate virtualenv
cd finops-cost-guardian
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate # Linux/macOS

pip install -r backend/requirements.txt

# Run full test suite with Moto AWS mocking
pytest -v backend/tests/
```
*Expected: 22 passed in ~20 seconds.*

### 4.2 Run Dashboard Locally
```bash
cd dashboard
npm install
npm run dev
```
*Open http://localhost:3000 in your browser to view the Command Center.*

---

## 5. Live AWS Deployment (Terraform)

```bash
cd terraform
terraform init
terraform apply -var="alert_email=your-verified-email@domain.com"
```

Outputs will display:
- `report_api_function_url`: Lambda Function URL for ReportAPI
- `api_secret_key`: Secret key (`cost-guardian-secret-2025`)
- `s3_dashboard_website_url`: Public S3 URL for web dashboard

---

## 6. Live Demo Runbook

1. **Plant Safe Demo Fixtures:**
   ```bash
   python scripts/plant_demo_fixtures.py
   ```
2. **Trigger Scan:**
   - From the dashboard, click **"Run Scan Now"** or invoke `ResourceScanner` in AWS Console.
   - Review flagged items in the Audit Table.
3. **Trigger Remediator:**
   - Click **"Remediate Eligible"** (with Dry-Run toggled on or off).
   - Observe that `DoNotStop=true` EBS volume is skipped while eligible EC2 is safely stopped.
   - Check your inbox for the formatted SNS notification email.
4. **Immediate Cleanup:**
   ```bash
   python scripts/cleanup_demo_fixtures.py
   ```
5. **Teardown Terraform:**
   ```bash
   cd terraform
   terraform destroy
   ```

---

## 7. Grading Evidence Checklist

- [x] Moto test suite passing (22/22 tests covering Section 14)
- [x] EventBridge 6-hour trigger rule active
- [x] DynamoDB `cost-guardian-scan-log` table storing CLEAN & FLAGGED scans
- [x] SNS `cost-guardian-alerts` email notification delivered
- [x] $1.00 AWS Budget tripwire active
- [x] Three least-privilege IAM roles provisioned
- [x] ReportAPI Function URL with CORS + `x-api-key` validation
- [x] React FinOps Command Center running with Live & Simulation fallback modes
- [x] Fixture planting and immediate cleanup verified
