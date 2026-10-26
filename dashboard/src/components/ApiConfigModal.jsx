import React, { useState } from 'react';
import { X, Key, Link2, CheckCircle2, AlertCircle, RefreshCw, Zap } from 'lucide-react';
import { normalizeLambdaUrl, smartFetch } from '../utils';

export default function ApiConfigModal({
  isOpen,
  onClose,
  apiUrl,
  apiKey,
  onSave,
  onSwitchToSimulation,
  isLive
}) {
  const [urlInput, setUrlInput] = useState(apiUrl || '');
  const [keyInput, setKeyInput] = useState(apiKey || 'cost-guardian-secret-2025');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  if (!isOpen) return null;

  const handleTestConnection = async () => {
    if (!urlInput.trim()) {
      setTestResult({ success: false, message: 'Please provide a valid Lambda Function URL.' });
      return;
    }

    setTesting(true);
    setTestResult(null);

    const cleanUrl = normalizeLambdaUrl(urlInput);
    // Update input display if we auto-completed the domain
    if (cleanUrl !== urlInput.trim()) {
      setUrlInput(cleanUrl);
    }

    try {
      const response = await smartFetch(`${cleanUrl}/history`, {
        method: 'GET',
        headers: {
          'x-api-key': keyInput.trim(),
        }
      });

      if (response.ok) {
        const data = await response.json();
        setTestResult({
          success: true,
          message: `Connected successfully! Retrieved ${data.count ?? 0} historical scan records.`
        });
      } else {
        const errData = await response.json().catch(() => ({}));
        setTestResult({
          success: false,
          message: `HTTP ${response.status}: ${errData.error || 'Access Denied (Verify x-api-key or Function URL)'}`
        });
      }
    } catch (err) {
      setTestResult({
        success: false,
        message: `Network or CORS error: ${err.message}. Ensure ReportAPI URL has CORS enabled and ends with '.on.aws/'.`
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = () => {
    const cleanUrl = normalizeLambdaUrl(urlInput);
    onSave(cleanUrl, keyInput.trim());
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-5">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Zap className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">AWS Live Connection Config</h2>
              <p className="text-xs text-slate-400">Connect to ReportAPI Lambda Function URL</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Inputs */}
        <div className="space-y-4 text-xs font-mono">
          <div>
            <label className="block text-slate-300 font-medium mb-1.5 flex items-center gap-1.5">
              <Link2 className="h-3.5 w-3.5 text-cyan-400" />
              <span>ReportAPI Lambda Function URL</span>
            </label>
            <input
              type="text"
              placeholder="https://<unique-id>.lambda-url.us-east-1.on.aws/"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan-500/60"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Copied from Terraform output: <code className="text-slate-400">report_api_function_url</code>
            </p>
          </div>

          <div>
            <label className="block text-slate-300 font-medium mb-1.5 flex items-center gap-1.5">
              <Key className="h-3.5 w-3.5 text-amber-400" />
              <span>API Secret Key (x-api-key)</span>
            </label>
            <input
              type="password"
              placeholder="cost-guardian-secret-2025"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-amber-500/60"
            />
          </div>
        </div>

        {/* Test Result Feedback */}
        {testResult && (
          <div className={`p-3 rounded-lg text-xs font-mono flex items-start gap-2 ${
            testResult.success 
              ? 'bg-emerald-950/50 border border-emerald-800/80 text-emerald-300' 
              : 'bg-rose-950/50 border border-rose-800/80 text-rose-300'
          }`}>
            {testResult.success ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400 mt-0.5" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
            )}
            <div>{testResult.message}</div>
          </div>
        )}

        {/* Modal Actions */}
        <div className="pt-2 border-t border-slate-800 flex flex-wrap items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => {
              onSwitchToSimulation();
              onClose();
            }}
            className="text-xs text-amber-400 hover:text-amber-300 font-medium underline"
          >
            Switch to Simulation Mode
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={testing}
              className="px-3.5 py-2 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition disabled:opacity-50 flex items-center gap-1.5"
            >
              {testing && <RefreshCw className="h-3 w-3 animate-spin text-cyan-400" />}
              <span>{testing ? 'Testing...' : 'Test Connection'}</span>
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="px-4 py-2 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20 transition"
            >
              Save & Connect
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
