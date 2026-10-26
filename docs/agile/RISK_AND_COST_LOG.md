# FinOps Cost Guardian — Risk Assessment & Cost-Safety Log

> **Deployment Target:** Personal AWS Account  
> **Region:** us-east-1  
> **Account Type:** Personal with $200+ promotional credits  
> **Document Owner:** FinOps Cost Guardian Project  
> **Last Updated:** Sprint 4 (Week 6)  

---

## 1. Risk Register

> **Risk Score = Likelihood × Impact**  
> Score 1–8: Low | Score 9–14: Medium | Score 15–25: High

| Risk ID | Risk Description | Category | Likelihood (1–5) | Impact (1–5) | Risk Score | Mitigation Strategy | Owner | Status |
|---------|-----------------|----------|-----------------|-------------|------------|---------------------|-------|--------|
| R01 | **Accidental over-spending on personal AWS credits during demo.** Demo fixtures (EC2, EBS, EIP) left running between sessions could drain $200+ credits faster than expected. | Financial | 3 | 4 | **12 (Medium)** | (1) `cleanup_demo_fixtures.py` script terminates all demo resources in <2 min. (2) AWS Budget `cost-guardian-monthly-budget` set at **$1.00/month** tripwire — email alert fires before meaningful credit loss. (3) `DEMO_RUNBOOK.md` pre-demo checklist mandates running cleanup after every session. (4) Free Tier always-on resources (Lambda, DynamoDB, SNS, EventBridge) cost $0.00 for demo-scale traffic. | Developer | 🟡 Mitigated |
| R02 | **SNS email subscription not confirmed before live demo.** If the subscription confirmation email is not clicked, SNS notifications are silently dropped and the alert workflow appears broken during presentation. | Operational | 3 | 4 | **12 (Medium)** | (1) Pre-demo checklist in `DEMO_RUNBOOK.md` includes "SNS subscription confirmed?" as Step 3. (2) Send a test SNS publish from AWS Console to verify delivery end-to-end. (3) Note in README: check spam/junk folder — confirmation emails from AWS SES often land in spam. (4) If subscription expires (AWS keeps pending subscriptions for 3 days), re-subscribe via Terraform `aws_sns_topic_subscription` re-apply. | Developer | 🟡 Mitigated |
| R03 | **IAM permissions insufficient for Lambda execution.** If a Lambda function's IAM role is missing a required permission (e.g., `ec2:DescribeAddresses`), the function fails silently at runtime with `AccessDeniedException`. | Security / Operational | 2 | 5 | **10 (Medium)** | (1) Three least-privilege IAM roles explicitly list all required actions — reviewed against Lambda function code. (2) AWS IAM Access Analyzer policy validation run against all three roles during Sprint 0 — zero findings. (3) All Lambda functions log `boto3` exceptions to CloudWatch; `AccessDeniedException` triggers specific error message. (4) moto unit tests mock IAM grants implicitly, but integration tests run against real AWS to catch permission gaps. | Developer | ✅ Resolved |
| R04 | **Demo fixtures not cleaned up, running up charges.** A t2.micro instance left running for 30 days = ~$8.47/month. Multiple orphaned fixtures could exhaust the $200 credit budget. | Financial / Operational | 3 | 4 | **12 (Medium)** | (1) `cleanup_demo_fixtures.py` script tags all demo fixtures at creation with `DemoFixture=true` and uses this tag in bulk termination/deletion. (2) AWS Budget $1.00 tripwire fires before fixture cost reaches $1. (3) EventBridge schedule (`rate(6 hours)`) automatically scans and flags any untagged or forgotten instances, prompting their detection. (4) `DEMO_RUNBOOK.md` post-demo cleanup step is mandatory. | Developer | 🟡 Mitigated |
| R05 | **DynamoDB scan-log table schema mismatch.** If `resource_id` PK or `scan_timestamp` SK attribute names differ between Lambda code and Terraform table definition, `PutItem` calls fail with `ValidationException`. | Technical | 2 | 4 | **8 (Low)** | (1) Schema constants extracted into `lambdas/utils/constants.py` — single source of truth for attribute names. (2) All three Lambda functions import from `constants.py`; no string literals for key names in business logic. (3) moto unit tests exercise `PutItem` and `GetItem` paths, catching schema mismatches at test time. (4) Terraform `aws_dynamodb_table` attribute definitions reviewed against `constants.py` as part of Definition of Done. | Developer | ✅ Resolved |
| R06 | **Lambda cold start delays affecting demo experience.** First invocation after a period of inactivity can take 1–3 seconds (Python runtime), making the "Scan Now" button in the dashboard feel sluggish during a live presentation. | Performance | 4 | 2 | **8 (Low)** | (1) Dashboard shows a loading spinner with "Scanning your AWS account..." message — sets correct expectation. (2) Invoke ReportAPI Lambda once during demo pre-flight to warm the execution environment. (3) If cold start is unacceptable, enable Lambda Provisioned Concurrency (1 instance = ~$14.40/month — not worth it for demo; keep as awareness). (4) Simulation Mode as fallback requires zero Lambda invocations and is always instant. | Developer | 🟢 Accepted |
| R07 | **API key exposed in browser localStorage.** The `VITE_API_KEY` stored in localStorage and sent as `x-api-key` header could be extracted by a malicious browser extension or XSS attack. | Security | 2 | 4 | **8 (Low)** | (1) Dashboard is a personal demo tool, not a multi-tenant SaaS — threat model is low. (2) API key is not a long-lived IAM credential; rotating it requires only updating Lambda env var and dashboard `.env`. (3) Lambda Function URL has no financial blast radius — it can only read DynamoDB and invoke other Lambdas. (4) For production deployment: move to AWS Cognito + Lambda authorizer. Document this as a "post-MVP security hardening" backlog item. | Developer | 🟢 Accepted |
| R08 | **S3 bucket public access blocked by AWS default settings.** If a future feature uploads reports to S3 for public dashboard access, AWS account-level "Block Public Access" settings will silently prevent the bucket policy from granting public read. | Technical | 2 | 3 | **6 (Low)** | (1) Current implementation uses Lambda Function URL (not S3) for dashboard backend — S3 public access is not needed. (2) If S3 is added later: Terraform `aws_s3_bucket_public_access_block` resource explicitly sets all four block settings to `false` only for static website hosting buckets. (3) Dashboard is served from Vite dev server or GitHub Pages (zero S3 dependency for demo). | Developer | 🟢 Not Applicable |
| R09 | **AWS Budget alert not triggered due to <$1 spend.** Core services (Lambda, DynamoDB, SNS, EventBridge) run entirely within the AWS Free Tier for demo-scale traffic. If actual spend never reaches $1.00, the Budget alert never fires and may give false confidence. | Financial | 4 | 1 | **4 (Low)** | (1) AWS Budget can be set to trigger on **forecasted** spend exceeding $1.00, not just actual. This catches trending spend before it materializes. (2) Core service cost is genuinely $0.00 at demo scale — the $1.00 budget is a tripwire for accidental fixture leakage. (3) Manually test the budget alert by publishing a test SNS notification from the Budget console. (4) Budget is a monitoring tool, not the primary cost control — `cleanup_demo_fixtures.py` is the primary control. | Developer | 🟡 Mitigated |
| R10 | **Terraform state file corruption or loss.** Local `terraform.tfstate` file on developer workstation could be corrupted, deleted, or accidentally committed to Git with sensitive ARNs, causing infrastructure drift. | Technical | 2 | 4 | **8 (Low)** | (1) `.gitignore` includes `*.tfstate`, `*.tfstate.backup`, and `.terraform/` — state never committed to Git. (2) Terraform state stored in S3 backend (`cost-guardian-tf-state` bucket with versioning enabled) in production configuration. (3) Local state used during development only, with `terraform import` available as recovery mechanism. (4) `terraform plan` always run before `apply` — drift detected before apply, not after. | Developer | 🟡 Mitigated |

---

## 2. Cost-Safety Log

> All cost estimates based on `us-east-1` pricing as of 2025. Demo traffic well within Free Tier limits.

| Service | Free Tier Limit | Estimated Demo Usage | Estimated Cost (Personal Account) | Cost Safety Mechanism |
|---------|----------------|---------------------|-----------------------------------|-----------------------|
| **AWS Lambda** | 1M requests/month + 400,000 GB-seconds/month | ~50 invocations/month (EventBridge 6h schedule + manual demo triggers) | **$0.00** | Free Tier: 50 invocations = 0.005% of free limit. Even at 1,000 invocations, cost = $0.00. |
| **Amazon DynamoDB** | 25 GB storage + 25 WCU + 25 RCU (always free) | <100 items/month, <1 GB storage | **$0.00** | `PAY_PER_REQUEST` billing with free tier always-free allocation. Demo traffic: ~100 PutItem + ~200 GetItem/month = effectively $0.00. |
| **Amazon SNS** | 1M publishes/month free | ~20 publishes/month (alert emails) | **$0.00** | 20 << 1,000,000 free. Email delivery: $0.00 (first 1,000 emails free). |
| **Amazon EventBridge** | 14M events/month free (custom bus) | ~120 scheduled rule invocations/month (every 6h = 4/day × 30 days) | **$0.00** | Scheduled rules use AWS-managed event bus, which is free. Custom event bus free tier is 14M events. |
| **Amazon S3** | 5 GB storage + 20,000 GET + 2,000 PUT requests/month free | Terraform state only: <1 MB | **$0.00** | Single small state file. GET/PUT requests: <100/month. Well within free tier. |
| **EC2 Demo Fixtures** | t2.micro: 750 hours/month free (first 12 months) | 1 instance × ~2 hours per demo session × ~5 demo sessions = 10 hours/month | **$0.00** (within free tier) / **$0.12** if free tier exhausted | `cleanup_demo_fixtures.py` terminates fixtures immediately after demo. $1.00 Budget tripwire catches any runaway instances within $1 of spend. |
| **EBS Demo Fixtures** | 30 GB of SSD storage free (first 12 months) | 1 × 20 GB volume × 2 hours per demo | **$0.00** (within free tier) / **$0.002** per demo if free tier exhausted | Cleanup script deletes volume. Cost if left running 30 days: $2.00 — caught by $1.00 budget before full month elapses. |
| **EIP Demo Fixtures** | No free tier — charged immediately when unassociated | 1 EIP × ~2 hours per demo = 0.008 hours | **$0.00004 per demo session** ($0.005/hr × 0.008 hr) | Cleanup script releases EIP in <5 seconds. Maximum exposure: $3.60/month if left permanently — caught by $1.00 budget alert within 8.3 days. |
| **AWS Budgets** | 2 budgets free, additional $0.02/day/budget | 1 budget (`cost-guardian-monthly-budget`) | **$0.00** | First 2 budgets are free. |
| **TOTAL ESTIMATED MONTHLY COST** | | | **$0.00 (core, always)** + **<$0.50 demo fixtures if cleanup script skipped** | Primary: `cleanup_demo_fixtures.py`. Secondary: $1.00 Budget tripwire. Tertiary: $200+ credit buffer. |

---

## 3. Credit Burn Rate Analysis

### Starting Position
- **Initial Credit Balance:** $200.00+ (AWS promotional credits applied to personal account)
- **Credit Expiry:** 12 months from account activation
- **Target Monthly Burn Rate:** $0.00 (core infrastructure) + minimal fixture costs

### Monthly Cost Breakdown

| Cost Category | Monthly Amount | Notes |
|---------------|---------------|-------|
| Lambda (3 functions) | $0.00 | Free Tier: 1M requests/month |
| DynamoDB (`cost-guardian-scan-log`) | $0.00 | Always-free 25 WCU / 25 RCU / 25 GB |
| SNS (`cost-guardian-alerts`) | $0.00 | Free Tier: 1M publishes + 1K emails |
| EventBridge (scheduled rule) | $0.00 | AWS-managed bus rules are free |
| S3 (Terraform state) | $0.00 | <5 GB free, <2K PUTs free |
| EC2 demo fixtures (5 demo sessions × 2 hrs) | $0.00 | t2.micro 750 hrs/month free |
| EBS demo fixtures (5 sessions × 2 hrs) | $0.00 | 30 GB free, well within limit |
| EIP demo fixtures (5 sessions × 2 hrs) | ~$0.05 | $0.005/hr × 10 hours total |
| AWS Budget (1 budget) | $0.00 | First 2 budgets free |
| **TOTAL** | **~$0.05/month** | Essentially zero |

### Credit Longevity Projection

| Scenario | Monthly Burn | Credits Last |
|----------|-------------|-------------|
| Best case (cleanup always runs) | $0.00–$0.05 | 3,000–∞ months |
| Typical case (occasional fixture orphan) | $0.50 | 400 months |
| Worst case (EC2 left running all month, cleanup missed) | ~$8.50 | ~23 months |
| **Budget tripwire fires at** | **$1.00** | Alert fires at Day 3–4 of worst case |

### Safety Mechanism Stack

```
LAYER 1 (Prevention):   cleanup_demo_fixtures.py — destroys demo resources in <2 min
LAYER 2 (Detection):    EventBridge scan every 6h — flags any orphaned resources
LAYER 3 (Alerting):     SNS email alert when idle/orphaned resource detected
LAYER 4 (Tripwire):     AWS Budget at $1.00/month — email alert if any spend occurs
LAYER 5 (Simulation):   DRY_RUN=true mode — test remediator without AWS mutations
LAYER 6 (Buffer):       $200+ promotional credits — 200× safety margin on worst-case burn
```

### Key Safety Statements

1. **The core FinOps Cost Guardian infrastructure costs $0.00/month.** Lambda, DynamoDB, SNS, and EventBridge all operate entirely within the AWS Free Tier at demonstration-scale traffic volumes.

2. **The $1.00 monthly budget tripwire is a canary, not a cliff.** The budget alert fires at $1.00 actual spend. At the worst-case burn rate of $8.47/month (one t2.micro running continuously), the $1.00 alert fires within approximately 3.5 days, leaving $196.50 in credits.

3. **Demo fixture costs are transient.** Each demo session creates ~$0.01–$0.05 of AWS resources that exist for approximately 2 hours. The cleanup script eliminates this cost within seconds of the demo ending.

4. **DRY_RUN mode enables zero-cost remediation testing.** The Remediator Lambda can be tested at scale without any AWS resource mutations, meaning QA and rehearsal runs are completely free.

5. **The project demonstrates cost-consciousness by its own operation.** A FinOps tool that costs $0.00/month to operate is a powerful proof point for the cost optimization principles it enforces.
