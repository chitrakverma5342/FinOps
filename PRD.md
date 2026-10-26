# Product Requirements Document (PRD): FinOps Cost Guardian
**Automated Idle-Resource Detection, Safe Remediation & Cost Governance on AWS**

## 1. Project Overview & Core Philosophy
- **Project Name:** FinOps Cost Guardian
- **Objective:** Build an event-driven, serverless AWS FinOps watchdog that continuously monitors an AWS account for idle or forgotten cloud resources (EC2 instances, EBS volumes, and Elastic IPs), logs every scan to an auditable DynamoDB history table, sends low-noise email alerts via SNS, performs tag-gated safe remediation, and visualizes cost governance trends via a modern web dashboard.
- **Account Environment & Cost Model:**
  - **Personal AWS Account ($200+ Credit Buffer, No Learner Lab):** Deployed into a dedicated personal AWS account with full IAM administrative control (no `LabRole` restrictions and no 4-hour lab session resets).
  - **The $0 Core Engine:** All core services (EventBridge, Lambda, DynamoDB, SNS, AWS Budgets, EC2/EBS `Describe*` APIs) operate strictly within the **AWS Always Free Tier ($0.00/month)**. The $200+ personal credit balance serves purely as a safety buffer for S3 static website hosting and short-lived planted test fixtures during live demos.

---

## 2. System Architecture & Exact Component Naming (Aligned with Report Figure 1)

1. **Amazon EventBridge (`cost-guardian-schedule`):**
   - Scheduled rule invoking `ResourceScanner` on a configurable interval (default `rate(6 hours)`) plus manual on-demand invocation.
2. **AWS Lambda — `ResourceScanner` (Python 3.12 / Boto3):**
   - Queries read-only EC2, EBS, and EIP `Describe*` APIs (with pagination across all pages).
   - Evaluates each resource against the configured idle threshold (e.g., `IDLE_THRESHOLD_HOURS=12`, overrideable to `0` for instant live demo detection).
   - Writes **every** scan outcome (`FLAGGED` or `CLEAN`) to the DynamoDB scan-log table.
   - Invokes `Remediator` if a flagged resource carries `eligible-for-remediation=true` and does NOT carry `DoNotStop=true`; otherwise triggers an alert-only notification to SNS.
3. **Amazon DynamoDB (`cost-guardian-scan-log`):**
   - Stores the full historical audit trail of both clean and flagged scans.
   - **Partition Key:** `resource_id` (String, or `SCAN#<scan_id>` for clean account summaries).
   - **Sort Key:** `scan_timestamp` (String, ISO-8601 UTC).
   - **Attributes:** `scan_id`, `resource_type` (`EC2` | `EBS` | `EIP`), `region`, `resource_state`, `idle_duration_hours`, `estimated_hourly_cost_usd`, `estimated_monthly_waste_usd`, `status` (`FLAGGED` | `CLEAN` | `REMEDIATED` | `SKIPPED_DO_NOT_STOP`), `eligible_for_remediation` (Boolean), `do_not_stop` (Boolean), `action_taken`, `tags`.
4. **AWS Lambda — `Remediator` (Python 3.12 / Boto3):**
   - Enforces "safe-to-fail" human-in-the-loop governance:
     - **Rule 1 (Exclusion Guard):** If tag `DoNotStop=true` (or any truthy value) is present -> **NEVER** stop or release; log as `SKIPPED_DO_NOT_STOP`.
     - **Rule 2 (Opt-In Eligibility Guard):** Only execute remediation if tag `eligible-for-remediation=true` is present AND `DRY_RUN=false`.
   - **Actions:**
     - Idle running EC2 instance -> `ec2.stop_instances()`
     - Unattached (`available`) EBS volume -> `ec2.delete_volume()` (or tag/snapshot per safety mode)
     - Unassociated Elastic IP -> `ec2.release_address()`
   - Updates the DynamoDB audit record with `action_taken` and publishes the remediation confirmation to SNS.
5. **Amazon SNS Topic (`cost-guardian-alerts`):**
   - Delivers formatted email notifications (never SMS, to preserve $0 cost) to the verified owner email address whenever idle resources are flagged or remediated.
6. **AWS Budgets (`cost-guardian-monthly-budget`):**
   - Independent monthly spend tripwire configured at **$1.00 USD** that fires an email alert if actual or forecasted spend breaches the near-zero threshold.
7. **AWS Lambda — `ReportAPI` (Exposed via Lambda Function URL):**
   - Reads the DynamoDB scan log on demand and exposes secure HTTPS endpoints (`GET /history`, `POST /scan`, `POST /remediate`) to the frontend dashboard.
   - Protected by **CORS configuration** and **`x-api-key` secret header validation** (returning sanitized fields only).
8. **Amazon S3 Static Website (`cost-guardian-dashboard-<account_id>`):**
   - Hosts the compiled modern FinOps Cost Guardian web dashboard (also compatible with local execution and GitHub Pages).
9. **AWS IAM (True Least-Privilege Roles):**
   - Because this runs on a personal AWS account (not Learner Lab), Terraform provisions **three distinct IAM roles**:
     1. `CostGuardianScannerRole`: Read-only `ec2:Describe*`, `dynamodb:PutItem`, `sns:Publish`, `lambda:InvokeFunction` (on `Remediator`).
     2. `CostGuardianRemediatorRole`: `ec2:StopInstances`, `ec2:DeleteVolume`, `ec2:ReleaseAddress` (scoped with IAM tag conditions where supported), `dynamodb:UpdateItem`/`PutItem`, `sns:Publish`.
     3. `CostGuardianReportApiRole`: Read-only `dynamodb:Query`/`Scan` + `lambda:InvokeFunction` for manual scan/remediate triggers from the UI.

---

## 3. Modern Frontend Specification: FinOps Cost Guardian Dashboard

The dashboard must look like a **modern, high-tech Cloud FinOps Command Center** (inspired by Linear, Vercel, and Datadog Dark Mode).

### 3.1 Tech Stack & Visual Identity
- **Stack:** React 18 (Vite) + Tailwind CSS + `lucide-react` icons + `recharts`.
- **Theme:** Deep Obsidian canvas (`#080C14`), translucent glassmorphic cards (`bg-slate-900/75 backdrop-blur-md border border-slate-800/80`), glowing status pills, and monospace data fields (`JetBrains Mono`) for instance IDs (`i-...`, `vol-...`, `eipalloc-...`), timestamps, and costs.
- **Accents:** Emerald (`#10B981` - Clean / Saved), Amber (`#F59E0B` - Flagged Idle), Rose (`#F43F5E` - Unprotected Waste), Cyan/Indigo (`#06B6D4` / `#6366F1` - Active Controls).

### 3.2 Dashboard Features
1. **Top Command Bar:**
   - Live Connection Badge: Toggles between **`AWS LIVE (ReportAPI Connected)`** and **`OFFLINE DEMO SIMULATION MODE`**.
   - **API Config Modal:** Input fields for `ReportAPI Lambda Function URL` and `x-api-key` secret header (persisted in `localStorage`).
   - **Primary Controls:**
     - **"Run ResourceScanner Now"** button with live scan spinner.
     - **"Run Remediator"** button with a **Dry-Run / Live Action toggle**.
2. **4 Executive FinOps KPI Cards:**
   - **Estimated Monthly Waste Prevented ($/mo & $/hr):** Calculated from stopped EC2s, cleaned EBS volumes, and released EIPs.
   - **Active Flagged Idle Resources:** Count broken down by `EC2`, `EBS`, and `EIP`.
   - **Tag Governance Breakdown:** Number of resources auto-remediated (`eligible-for-remediation=true`) vs. protected (`DoNotStop=true`) vs. alert-only.
   - **Guardian Operating Cost:** `$0.00 / mo` (Always Free Tier status badge + $1.00 AWS Budget tripwire status `OK`).
3. **Visual Analytics Grid (Recharts):**
   - **Cost Hygiene Trend Chart (AreaChart):** Flagged Waste ($) vs. Remediated Savings ($) across scan intervals.
   - **Idle Resource Distribution (Bar/Donut Chart):** Breakdown by resource type (`EC2`, `EBS`, `EIP`) and status (`CLEAN`, `FLAGGED`, `REMEDIATED`, `SKIPPED_DO_NOT_STOP`).
4. **Interactive Audit Log & Resource Governance Table:**
   - Filterable by `All`, `Flagged`, `Remediated`, `Protected (DoNotStop)`, and `Clean Scans`.
   - Displays `Resource ID`, `Type`, `State`, `Idle Duration (hrs)`, `Tags (eligible-for-remediation / DoNotStop)`, `Est. Cost`, `Action Taken`, `Timestamp`, and a per-row **"Remediate"** button.
5. **Live CloudWatch / Execution Console Drawer:**
   - Terminal-style drawer streaming step-by-step execution events matching Figure 1 of the report (`EventBridge -> ResourceScanner -> Describe* -> DynamoDB -> Remediator -> SNS`).

---

## 4. Agile Delivery Plan (5 Sprints — Matching Section 10 of Report)

Antigravity must generate complete Agile artifacts inside `docs/agile/` matching the 5-sprint table in the report:
- **Sprint 0 (Setup — Foundation & Design):** Personal AWS account & least-privilege IAM design, idle-resource rules & thresholds (`12h`), DynamoDB schema, Definition of Done, architecture diagram, product backlog.
- **Sprint 1 (Core Detection):** `ResourceScanner` Lambda, paginated `EC2`/`EBS`/`EIP` `Describe*` logic, unit tests using `pytest` + `moto` (mocked AWS APIs).
- **Sprint 2 (Automation & Logging):** EventBridge 6-hour schedule rule, `cost-guardian-scan-log` DynamoDB table, `cost-guardian-alerts` SNS topic & email subscription.
- **Sprint 3 (Safe Remediation & Governance):** Tag-gated `Remediator` Lambda (`eligible-for-remediation` opt-in + `DoNotStop` exclusion), $1.00 AWS Budgets tripwire, updated Risk Log.
- **Sprint 4 (Reporting & Polish):** `ReportAPI` Lambda Function URL (with CORS + `x-api-key`), S3 static website modern FinOps dashboard, GitHub Actions CI workflow, final demo scripts & retrospective notes.

---

## 5. Repository Structure

```text
finops-cost-guardian/
├── .github/workflows/
│   └── ci.yml                       # Runs ruff/flake8, pytest (moto unit tests), and Vite frontend build on push
├── backend/
│   ├── src/
│   │   ├── resource_scanner.py      # ResourceScanner Lambda handler (EC2, EBS, EIP pagination + DynamoDB + SNS)
│   │   ├── remediator.py            # Remediator Lambda handler (eligible-for-remediation & DoNotStop tag gates)
│   │   ├── report_api.py            # ReportAPI Lambda Function URL handler (CORS + x-api-key auth + endpoints)
│   │   └── common.py                # Shared cost estimators, pagination helpers, DynamoDB & SNS utilities
│   ├── tests/
│   │   ├── test_scanner.py          # Moto unit tests: clean scan, idle EC2, unattached EBS, unassociated EIP, pagination
│   │   ├── test_remediator.py       # Moto unit tests: eligible tag stopped, DoNotStop skipped, untagged alert-only
│   │   └── test_report_api.py       # Unit tests: CORS headers, 401 unauthorized without x-api-key, history payload
│   └── requirements.txt
├── terraform/
│   ├── main.tf                      # EventBridge, 3 Lambdas, DynamoDB, SNS, Function URL, S3 website, $1 AWS Budget
│   ├── iam.tf                       # 3 separate least-privilege IAM roles (Scanner, Remediator, ReportAPI)
│   ├── variables.tf                 # region, alert_email, api_secret_key, idle_threshold_hours, budget_limit_usd
│   └── outputs.tf                   # report_api_url, s3_dashboard_url, dynamodb_table, sns_topic_arn
├── scripts/
│   ├── plant_demo_fixtures.py       # Creates safe test fixtures (1 eligible idle instance/volume, 1 DoNotStop resource)
│   └── cleanup_demo_fixtures.py     # Immediately terminates/deletes all planted demo fixtures
├── dashboard/                       # React + Vite + Tailwind CSS + Recharts FinOps Cost Guardian Dashboard
├── docs/
│   ├── agile/
│   │   ├── PRODUCT_BACKLOG.md       # Full backlog across Sprints 0-4 with Story Points & Acceptance Criteria
│   │   ├── SPRINT_REVIEWS.md        # Sprint 0 to Sprint 4 Boards, Review Notes, & Retrospectives
│   │   └── RISK_AND_COST_LOG.md     # Updated Risk Assessment & Cost-Safety Log (Personal Account + $200 Credits)
│   └── REPORT_UPDATES_FOR_WORD.md   # Ready-to-paste updated sections for FinOps_Cost_Guardian_Report.docx
└── README.md                        # Setup guide, architecture diagram, and grading evidence checklist

## 6. Human-in-the-Loop (HITL) Protocol

Whenever an action requires the user's personal AWS Console, local AWS CLI configuration, email confirmation, or GitHub push, the AI Agent MUST PAUSE and output a clear "🛑 MANUAL ACTION REQUIRED" guide with exact click-by-click steps and CLI commands.