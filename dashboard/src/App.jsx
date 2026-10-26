import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import KpiCards from './components/KpiCards';
import Charts from './components/Charts';
import AuditTable from './components/AuditTable';
import TerminalDrawer from './components/TerminalDrawer';
import ApiConfigModal from './components/ApiConfigModal';
import { INITIAL_RECORDS, INITIAL_LOGS } from './simulationData';
import { normalizeLambdaUrl, smartFetch } from './utils';

export default function App() {
  const [apiUrl, setApiUrl] = useState(() => normalizeLambdaUrl(localStorage.getItem('finops_api_url') || ''));
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('finops_api_key') || 'cost-guardian-secret-2025');
  const [isLive, setIsLive] = useState(false);
  const [records, setRecords] = useState(INITIAL_RECORDS);
  const [summary, setSummary] = useState(null);
  const [logs, setLogs] = useState(INITIAL_LOGS);
  const [dryRun, setDryRun] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [remediating, setRemediating] = useState(false);
  const [isConfigOpen, setIsConfigOpen] = useState(false);

  const addLog = useCallback((level, message) => {
    const timestamp = new Date().toTimeString().split(' ')[0];
    setLogs(prev => [...prev, { timestamp, level, message }]);
  }, []);

  // Fetch live history from ReportAPI Function URL
  const fetchHistory = useCallback(async (url, key) => {
    const targetUrl = normalizeLambdaUrl(url || apiUrl);
    const targetKey = (key || apiKey).trim();

    if (!targetUrl) {
      setIsLive(false);
      return;
    }

    try {
      const response = await smartFetch(`${targetUrl}/history`, {
        method: 'GET',
        headers: {
          'x-api-key': targetKey,
        }
      });

      if (response.ok) {
        const data = await response.json();
        if (data.records && data.records.length > 0) {
          setRecords(data.records);
        }
        if (data.summary) {
          setSummary(data.summary);
        }
        setIsLive(true);
        addLog('SUCCESS', `Synchronized ${data.count ?? 0} records from AWS ReportAPI`);
      } else {
        setIsLive(false);
        addLog('WARN', `ReportAPI returned HTTP ${response.status}. Reverting to Simulation Mode.`);
      }
    } catch (err) {
      setIsLive(false);
      addLog('WARN', `Cannot connect to ReportAPI (${err.message}). Active in Simulation Mode.`);
    }
  }, [apiUrl, apiKey, addLog]);

  useEffect(() => {
    if (apiUrl) {
      fetchHistory(apiUrl, apiKey);
    }
  }, []);

  // Run ResourceScanner
  const handleRunScan = async () => {
    setScanning(true);
    addLog('INFO', '[EventBridge / Manual] Triggering ResourceScanner...');

    if (isLive && apiUrl) {
      try {
        const cleanUrl = normalizeLambdaUrl(apiUrl);
        const response = await smartFetch(`${cleanUrl}/scan`, {
          method: 'POST',
          headers: {
            'x-api-key': apiKey.trim(),
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ idle_threshold_hours: 0 }) // Instant demo discovery
        });
        const result = await response.json();
        addLog('SUCCESS', `ResourceScanner completed: ${result.message || 'Scan successful'}`);
        await fetchHistory(apiUrl, apiKey);
      } catch (err) {
        addLog('ERROR', `Scan invocation failed: ${err.message}`);
      }
    } else {
      // Offline Simulation Scan
      setTimeout(() => {
        addLog('INFO', '[ResourceScanner] Describing EC2 instances, EBS volumes, and Elastic IPs...');
        addLog('WARN', '[ResourceScanner] Found 1 idle EC2 instance (i-0abc123def456789) - 13.5h idle');
        addLog('INFO', '[DynamoDB] Logged audit record to cost-guardian-scan-log table');
        addLog('INFO', '[SNS] Formatted email notification published to cost-guardian-alerts');
        setScanning(false);
      }, 1000);
      return;
    }
    setScanning(false);
  };

  // Run Remediator
  const handleRunRemediate = async () => {
    setRemediating(true);
    const modeDesc = dryRun ? '[DRY-RUN SIMULATION]' : '[LIVE MUTATION]';
    addLog('INFO', `[Remediator] Initiating safe governance pipeline ${modeDesc}...`);

    if (isLive && apiUrl) {
      try {
        const cleanUrl = normalizeLambdaUrl(apiUrl);
        const response = await smartFetch(`${cleanUrl}/remediate`, {
          method: 'POST',
          headers: {
            'x-api-key': apiKey.trim(),
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ dry_run: dryRun })
        });
        const result = await response.json();
        addLog('SUCCESS', `Remediator finished: ${result.message || 'Remediation completed'}`);
        await fetchHistory(apiUrl, apiKey);
      } catch (err) {
        addLog('ERROR', `Remediator invocation failed: ${err.message}`);
      }
    } else {
      // Offline Simulation Remediation
      setTimeout(() => {
        setRecords(prev => prev.map(item => {
          if (item.status === 'FLAGGED') {
            if (item.do_not_stop) {
              addLog('INFO', `[Remediator] ${item.resource_id} has DoNotStop=true -> SKIPPED_DO_NOT_STOP`);
              return { ...item, status: 'SKIPPED_DO_NOT_STOP', action_taken: 'PROTECTED_BY_DO_NOT_STOP_TAG' };
            }
            if (item.eligible_for_remediation) {
              if (dryRun) {
                addLog('INFO', `[Remediator] DRY_RUN: Would stop/remediate ${item.resource_id} (savings: $${item.estimated_monthly_waste_usd}/mo)`);
                return { ...item, status: 'DRY_RUN_SIMULATED', action_taken: `SIMULATED: would stop ${item.resource_id}` };
              } else {
                addLog('SUCCESS', `[Remediator] Executed stop_instances on ${item.resource_id} -> status=REMEDIATED`);
                return { ...item, status: 'REMEDIATED', action_taken: `Stopped EC2 instance ${item.resource_id}`, resource_state: 'stopped' };
              }
            }
          }
          return item;
        }));
        addLog('INFO', '[SNS] Published remediation confirmation email to cost-guardian-alerts topic');
        setRemediating(false);
      }, 1000);
      return;
    }
    setRemediating(false);
  };

  // Remediate Single Row
  const handleRemediateRow = async (item) => {
    addLog('INFO', `Targeted remediation on ${item.resource_type} ${item.resource_id} (dry_run=${dryRun})...`);
    if (item.do_not_stop) {
      addLog('WARN', `BLOCKED: ${item.resource_id} carries 'DoNotStop=true' tag. Strict exclusion guard active.`);
      return;
    }

    if (isLive && apiUrl) {
      try {
        const cleanUrl = normalizeLambdaUrl(apiUrl);
        await smartFetch(`${cleanUrl}/remediate`, {
          method: 'POST',
          headers: {
            'x-api-key': apiKey.trim(),
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            resource_id: item.resource_id,
            resource_type: item.resource_type,
            dry_run: dryRun
          })
        });
        await fetchHistory(apiUrl, apiKey);
      } catch (err) {
        addLog('ERROR', `Single remediation failed: ${err.message}`);
      }
    } else {
      setRecords(prev => prev.map(r => {
        if (r.resource_id === item.resource_id) {
          const newStatus = dryRun ? 'DRY_RUN_SIMULATED' : 'REMEDIATED';
          const newAction = dryRun ? `SIMULATED: Would remediate ${r.resource_id}` : `Remediated ${r.resource_id}`;
          return { ...r, status: newStatus, action_taken: newAction, resource_state: dryRun ? r.resource_state : 'stopped' };
        }
        return r;
      }));
      addLog('SUCCESS', `Remediated ${item.resource_id} in Simulation Mode.`);
    }
  };

  const handleSaveConfig = (newUrl, newKey) => {
    const cleanUrl = normalizeLambdaUrl(newUrl);
    setApiUrl(cleanUrl);
    setApiKey(newKey);
    localStorage.setItem('finops_api_url', cleanUrl);
    localStorage.setItem('finops_api_key', newKey);
    if (cleanUrl) {
      fetchHistory(cleanUrl, newKey);
    }
  };

  const handleSwitchToSimulation = () => {
    setApiUrl('');
    localStorage.removeItem('finops_api_url');
    setIsLive(false);
    setRecords(INITIAL_RECORDS);
    setSummary(null);
    addLog('INFO', 'Switched to Offline Demo Simulation Mode.');
  };

  return (
    <div className="min-h-screen bg-[#080C14] text-slate-100 flex flex-col font-sans selection:bg-emerald-500/20">
      {/* Top Navigation & Controls */}
      <Header
        isLive={isLive}
        onOpenConfig={() => setIsConfigOpen(true)}
        onRunScan={handleRunScan}
        onRunRemediate={handleRunRemediate}
        scanning={scanning}
        remediating={remediating}
        dryRun={dryRun}
        setDryRun={setDryRun}
        apiUrl={apiUrl}
      />

      {/* Main Content Dashboard */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 pb-36">
        {/* KPI Cards */}
        <KpiCards summary={summary} records={records} />

        {/* Visual Analytics Grid */}
        <Charts records={records} />

        {/* Audit Log & Governance Table */}
        <AuditTable 
          records={records} 
          onRemediateRow={handleRemediateRow} 
          dryRun={dryRun}
        />
      </main>

      {/* CloudWatch / Execution Console Drawer */}
      <TerminalDrawer 
        logs={logs} 
        onClearLogs={() => setLogs([])} 
      />

      {/* Live API Config Modal */}
      <ApiConfigModal
        isOpen={isConfigOpen}
        onClose={() => setIsConfigOpen(false)}
        apiUrl={apiUrl}
        apiKey={apiKey}
        onSave={handleSaveConfig}
        onSwitchToSimulation={handleSwitchToSimulation}
        isLive={isLive}
      />
    </div>
  );
}
