/**
 * FinOps Cost Guardian — Offline Demo Simulation Fixture
 * Matches the exact Sprint 2 Saturday evening incident (t2.micro i-0abc123def456789)
 * and Section 4 narrative from the project report.
 */

export const INITIAL_RECORDS = [
  {
    resource_id: "i-0abc123def456789",
    scan_timestamp: "2025-01-18T22:47:00Z",
    scan_id: "scan-sat-2247-demo",
    resource_type: "EC2",
    region: "us-east-1",
    resource_state: "running",
    idle_duration_hours: 13.5,
    estimated_hourly_cost_usd: 0.0116,
    estimated_monthly_waste_usd: 8.47,
    status: "FLAGGED",
    eligible_for_remediation: true,
    do_not_stop: false,
    action_taken: "FLAGGED_FOR_REMEDIATION",
    tags: {
      Project: "FinOpsCostGuardian",
      Env: "demo",
      "eligible-for-remediation": "true"
    },
    scanner_version: "1.2.0",
    account_id: "123456789012"
  },
  {
    resource_id: "vol-078a9c21b3e4f5a6b",
    scan_timestamp: "2025-01-18T18:00:00Z",
    scan_id: "scan-sat-1800-demo",
    resource_type: "EBS",
    region: "us-east-1",
    resource_state: "available",
    idle_duration_hours: 48.0,
    estimated_hourly_cost_usd: 0.0027,
    estimated_monthly_waste_usd: 2.00,
    status: "SKIPPED_DO_NOT_STOP",
    eligible_for_remediation: false,
    do_not_stop: true,
    action_taken: "PROTECTED_BY_DO_NOT_STOP_TAG",
    tags: {
      Project: "FinOpsCostGuardian",
      Env: "demo",
      DoNotStop: "true"
    },
    scanner_version: "1.2.0",
    account_id: "123456789012"
  },
  {
    resource_id: "eipalloc-01f2e3d4c5b6a7890",
    scan_timestamp: "2025-01-18T12:00:00Z",
    scan_id: "scan-sat-1200-demo",
    resource_type: "EIP",
    region: "us-east-1",
    resource_state: "unassociated",
    idle_duration_hours: 24.0,
    estimated_hourly_cost_usd: 0.0050,
    estimated_monthly_waste_usd: 3.60,
    status: "REMEDIATED",
    eligible_for_remediation: true,
    do_not_stop: false,
    action_taken: "Released unassociated Elastic IP eipalloc-01f2e3d4c5b6a7890",
    tags: {
      Project: "FinOpsCostGuardian",
      "eligible-for-remediation": "true"
    },
    scanner_version: "1.2.0",
    account_id: "123456789012"
  },
  {
    resource_id: "i-0f9e8d7c6b5a43210",
    scan_timestamp: "2025-01-17T06:00:00Z",
    scan_id: "scan-fri-0600-demo",
    resource_type: "EC2",
    region: "us-east-1",
    resource_state: "stopped",
    idle_duration_hours: 15.2,
    estimated_hourly_cost_usd: 0.0116,
    estimated_monthly_waste_usd: 8.47,
    status: "REMEDIATED",
    eligible_for_remediation: true,
    do_not_stop: false,
    action_taken: "Stopped EC2 instance i-0f9e8d7c6b5a43210",
    tags: {
      Project: "FinOpsCostGuardian",
      "eligible-for-remediation": "true"
    },
    scanner_version: "1.2.0",
    account_id: "123456789012"
  },
  {
    resource_id: "SCAN_SUMMARY_2025-01-16T12:00:00Z",
    scan_timestamp: "2025-01-16T12:00:00Z",
    scan_id: "scan-thu-1200-clean",
    resource_type: "SCAN_SUMMARY",
    region: "us-east-1",
    resource_state: "clean",
    idle_duration_hours: 0.0,
    estimated_hourly_cost_usd: 0.0,
    estimated_monthly_waste_usd: 0.0,
    status: "CLEAN",
    eligible_for_remediation: false,
    do_not_stop: false,
    action_taken: "CLEAN_SCAN_NO_IDLE_RESOURCES",
    tags: {},
    scanner_version: "1.2.0",
    account_id: "123456789012"
  }
];

export const INITIAL_LOGS = [
  { timestamp: "22:45:00", level: "INFO", message: "[EventBridge] Trigger received: cost-guardian-schedule (rate(6 hours))" },
  { timestamp: "22:45:01", level: "INFO", message: "[ResourceScanner] Invoked with threshold=12h, force_idle=false" },
  { timestamp: "22:45:02", level: "INFO", message: "[ResourceScanner] EC2 Paginator scanned 1 instance (us-east-1)" },
  { timestamp: "22:45:03", level: "WARN", message: "[ResourceScanner] FLAGGED idle instance i-0abc123def456789 (running 13.5h, est. $8.47/mo)" },
  { timestamp: "22:45:04", level: "INFO", message: "[DynamoDB] PutItem written to cost-guardian-scan-log (PK=i-0abc123def456789)" },
  { timestamp: "22:47:00", level: "INFO", message: "[SNS] Published alert email to cost-guardian-alerts (1 flagged resource)" },
];

export const MOCK_TREND_CHART = [
  { date: "Day 1", flaggedWaste: 35.20, remediatedSavings: 14.50 },
  { date: "Day 2", flaggedWaste: 42.10, remediatedSavings: 28.00 },
  { date: "Day 3", flaggedWaste: 29.80, remediatedSavings: 45.20 },
  { date: "Day 4", flaggedWaste: 22.40, remediatedSavings: 68.90 },
  { date: "Day 5", flaggedWaste: 18.00, remediatedSavings: 94.30 },
  { date: "Day 6", flaggedWaste: 14.20, remediatedSavings: 132.00 },
  { date: "Day 7 (Today)", flaggedWaste: 8.47, remediatedSavings: 247.30 },
];
