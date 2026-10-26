# FinOps Cost Guardian — Product Backlog

## Definition of Done (Global)
- Code merged to `main` via PR with CI green
- Unit tests pass (pytest + moto coverage ≥ 80%)
- Terraform plan produces zero errors
- All resources tagged `Project=FinOpsCostGuardian`
- Documentation updated
- Demo screenshot captured (where applicable)

---

## EPIC 1: Foundation & Infrastructure Setup (Sprint 0)

| Story ID | User Story | Story Points | Priority | Acceptance Criteria |
|----------|-----------|--------------|----------|---------------------|
| US-01 | As a DevOps engineer, I want a personal AWS account with full IAM access so that I can deploy resources without Learner Lab restrictions. | 3 | Must Have | AWS account active, IAM admin user created, `aws configure` succeeds, credits > $200 visible |
| US-02 | As an architect, I want the DynamoDB schema (`cost-guardian-scan-log`) designed with PK=`resource_id`, SK=`scan_timestamp` so that all scan records are uniquely addressable. | 5 | Must Have | Schema document finalized, all 13 attributes listed, no CLEAN scans missed |
| US-03 | As a security engineer, I want three least-privilege IAM roles (CostGuardianScannerRole, CostGuardianRemediatorRole, CostGuardianReportApiRole) so that each Lambda only has the permissions it needs. | 5 | Must Have | Each role has zero wildcard `*` resource ARNs, passes AWS IAM Access Analyzer |
| US-04 | As a product owner, I want a documented Definition of Done and idle threshold of 12 hours so that the team has shared acceptance criteria. | 2 | Must Have | DoD published in PRODUCT_BACKLOG.md, threshold stored as env var `IDLE_THRESHOLD_HOURS=12` |
| US-05 | As a DevOps engineer, I want the Terraform project initialized with S3 backend (or local) so that state is versioned. | 3 | Should Have | `terraform init` succeeds, no provider errors |

**Sprint 0 Velocity:** 18 story points

---

## EPIC 2: Core Resource Detection (Sprint 1)

| Story ID | User Story | Story Points | Priority | Acceptance Criteria |
|----------|-----------|--------------|----------|---------------------|
| US-06 | As a FinOps engineer, I want `ResourceScanner` to paginate all EC2 instances and flag those running continuously for > 12 hours as idle so that no forgotten instance escapes detection. | 8 | Must Have | Pagination tested with 150+ mock instances, FLAGGED record written to DynamoDB, `DEMO_FORCE_IDLE=true` mode tested |
| US-07 | As a FinOps engineer, I want `ResourceScanner` to detect all EBS volumes in `available` state (unattached) so that orphaned storage costs are surfaced. | 5 | Must Have | All `available` volumes flagged regardless of idle threshold, DynamoDB record written |
| US-08 | As a FinOps engineer, I want `ResourceScanner` to detect all unassociated Elastic IPs so that the $0.005/hr idle EIP charge is caught. | 3 | Must Have | All unassociated EIPs flagged, estimated monthly waste = $3.60/EIP/month |
| US-09 | As a QA engineer, I want moto-based unit tests for ResourceScanner covering clean scan, idle EC2, unattached EBS, and unassociated EIP so that I have automated regression coverage. | 5 | Must Have | `pytest -v test_scanner.py` shows 5+ PASSED, 0 FAILED |
| US-10 | As a DevOps engineer, I want `IDLE_THRESHOLD_HOURS=0` environment variable override so that demo scans instantly flag resources without waiting 12 real hours. | 3 | Must Have | With `IDLE_THRESHOLD_HOURS=0`, running EC2 is immediately flagged |

**Sprint 1 Velocity:** 24 story points

---

## EPIC 3: Automation & Audit Logging (Sprint 2)

| Story ID | User Story | Story Points | Priority | Acceptance Criteria |
|----------|-----------|--------------|----------|---------------------|
| US-11 | As a FinOps engineer, I want EventBridge to trigger `ResourceScanner` on a `rate(6 hours)` schedule so that idle resources are caught within 6 hours of becoming idle. | 3 | Must Have | EventBridge rule `cost-guardian-schedule` active, Lambda invocation logs confirm 6h cadence |
| US-12 | As a FinOps engineer, I want every scan (both CLEAN and FLAGGED) written to DynamoDB `cost-guardian-scan-log` so that there is a complete immutable audit trail. | 5 | Must Have | DynamoDB table created, all 13 attributes present in each record, CLEAN summaries recorded |
| US-13 | As a cloud owner, I want SNS topic `cost-guardian-alerts` with my email subscribed so that I receive formatted email alerts when idle resources are found. | 3 | Must Have | SNS topic ARN confirmed, subscription confirmed via email click, test notification received |
| US-14 | As a stakeholder, I want email alerts formatted with resource ID, type, estimated cost, and tag status so that I can triage without logging into AWS Console. | 3 | Should Have | SNS email body includes all required fields, plain text format |
| US-15 | As a DevOps engineer, I want Terraform to manage EventBridge + DynamoDB + SNS as code so that infrastructure is reproducible. | 5 | Must Have | `terraform apply` provisions all three, `terraform destroy` removes cleanly |

**Sprint 2 Velocity:** 19 story points

---

## EPIC 4: Safe Remediation & Cost Governance (Sprint 3)

| Story ID | User Story | Story Points | Priority | Acceptance Criteria |
|----------|-----------|--------------|----------|---------------------|
| US-16 | As a cloud owner, I want `Remediator` to stop EC2 instances tagged `eligible-for-remediation=true` so that idle compute is automatically reclaimed. | 8 | Must Have | `stop_instances()` called, DynamoDB updated to REMEDIATED, SNS email sent |
| US-17 | As a cloud owner, I want `Remediator` to NEVER touch resources tagged `DoNotStop=true` so that production systems are absolutely protected. | 8 | Must Have | Resource with `DoNotStop=true` is logged as SKIPPED_DO_NOT_STOP, no stop/delete action taken |
| US-18 | As a FinOps engineer, I want `Remediator` to delete unattached EBS volumes tagged `eligible-for-remediation=true` so that orphaned storage is cleaned up. | 5 | Must Have | `delete_volume()` called, DynamoDB updated, SNS email sent |
| US-19 | As a FinOps engineer, I want `Remediator` to release unassociated EIPs tagged `eligible-for-remediation=true` so that idle EIP charges are eliminated. | 3 | Must Have | `release_address()` called, DynamoDB updated, SNS email sent |
| US-20 | As a cloud owner, I want a `DRY_RUN=true` mode that simulates remediation without taking action so that I can safely test the Remediator. | 5 | Must Have | With `DRY_RUN=true`, no AWS resources are modified, DynamoDB records show DRY_RUN_SIMULATED |
| US-21 | As a financial controller, I want an AWS Budget `cost-guardian-monthly-budget` at $1.00/month so that any unexpected spend triggers an immediate alert. | 3 | Must Have | Budget created, threshold at $1.00, email alert tested |
| US-22 | As a QA engineer, I want moto unit tests for Remediator covering all 3 resource types, DoNotStop guard, and DRY_RUN mode so that remediation logic has regression coverage. | 5 | Must Have | `pytest -v test_remediator.py` shows 6+ PASSED, 0 FAILED |

**Sprint 3 Velocity:** 37 story points

---

## EPIC 5: Reporting, Dashboard & CI/CD (Sprint 4)

| Story ID | User Story | Story Points | Priority | Acceptance Criteria |
|----------|-----------|--------------|----------|---------------------|
| US-23 | As a stakeholder, I want `ReportAPI` Lambda Function URL exposing `GET /history`, `POST /scan`, `POST /remediate` so that the dashboard has a secure backend. | 8 | Must Have | Function URL live, CORS headers present, 401 returned without valid `x-api-key` |
| US-24 | As a developer, I want the dashboard to show AWS LIVE vs SIMULATION MODE badge so that demo audience sees clear connection status. | 5 | Should Have | Badge toggles on valid API config, falls back to offline simulation data |
| US-25 | As a stakeholder, I want 4 KPI cards (Waste Prevented, Flagged Count, Tag Governance, $0 Operating Cost) displayed prominently so that FinOps impact is immediately visible. | 5 | Must Have | All 4 cards render, data populates from live or simulation source |
| US-26 | As a stakeholder, I want a Recharts AreaChart showing Flagged Waste vs. Remediated Savings trend so that cost impact over time is visualized. | 5 | Should Have | AreaChart renders with ≥ 7 data points, both lines visible |
| US-27 | As an auditor, I want a filterable Audit Log table showing all scan statuses with per-row remediation controls so that governance evidence is complete. | 8 | Must Have | Table shows CLEAN, FLAGGED, REMEDIATED, SKIPPED_DO_NOT_STOP rows, filter tabs work |
| US-28 | As a DevOps engineer, I want GitHub Actions CI running ruff lint + pytest + Vite build on every push so that quality gates are automated. | 5 | Must Have | `.github/workflows/ci.yml` passes on main branch push |
| US-29 | As a developer, I want plant_demo_fixtures.py and cleanup_demo_fixtures.py scripts so that I can create and destroy test resources safely during live demos. | 5 | Must Have | Fixtures planted in < 2 minutes, cleanup completes in < 2 minutes, no orphaned resources |
| US-30 | As a QA engineer, I want moto unit tests for ReportAPI covering CORS, auth, and history endpoint so that the API layer has regression coverage. | 3 | Must Have | `pytest -v test_report_api.py` shows 4+ PASSED, 0 FAILED |

**Sprint 4 Velocity:** 44 story points

---

## Backlog Summary

| Sprint | Epic | Total Story Points | Stories |
|--------|------|--------------------|---------|
| Sprint 0 | Foundation & Infrastructure Setup | 18 | US-01 to US-05 |
| Sprint 1 | Core Resource Detection | 24 | US-06 to US-10 |
| Sprint 2 | Automation & Audit Logging | 19 | US-11 to US-15 |
| Sprint 3 | Safe Remediation & Cost Governance | 37 | US-16 to US-22 |
| Sprint 4 | Reporting, Dashboard & CI/CD | 44 | US-23 to US-30 |
| **TOTAL** | | **142** | **US-01 to US-30** |
