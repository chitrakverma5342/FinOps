import React from 'react';
import { 
  ShieldCheck, 
  Wifi, 
  WifiOff, 
  Settings, 
  Play, 
  Zap, 
  RotateCw,
  Sliders,
  DollarSign
} from 'lucide-react';

export default function Header({
  isLive,
  onOpenConfig,
  onRunScan,
  onRunRemediate,
  scanning,
  remediating,
  dryRun,
  setDryRun,
  apiUrl
}) {
  return (
    <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        {/* Brand & Subtitle */}
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-lg shadow-emerald-500/10">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                FinOps Cost Guardian
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  v1.2.0
                </span>
              </h1>
            </div>
            <p className="text-xs text-slate-400">
              Automated Idle-Resource Detection & Safe Tag Governance
            </p>
          </div>
        </div>

        {/* Status Badge & Actions */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Connection Status Badge */}
          <button
            onClick={onOpenConfig}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
              isLive 
                ? 'bg-emerald-950/40 text-emerald-300 border-emerald-800/60 hover:bg-emerald-900/50' 
                : 'bg-amber-950/40 text-amber-300 border-amber-800/60 hover:bg-amber-900/50'
            }`}
            title="Click to configure ReportAPI Function URL and x-api-key"
          >
            {isLive ? <Wifi className="h-3.5 w-3.5 animate-pulse text-emerald-400" /> : <WifiOff className="h-3.5 w-3.5 text-amber-400" />}
            <span className="font-mono">{isLive ? 'AWS LIVE (ReportAPI)' : 'SIMULATION MODE'}</span>
            <Settings className="h-3 w-3 ml-1 text-slate-400 hover:text-white" />
          </button>

          {/* Dry Run Toggle */}
          <div className="flex items-center bg-slate-900/90 border border-slate-800 rounded-lg p-0.5">
            <button
              onClick={() => setDryRun(true)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                dryRun 
                  ? 'bg-indigo-600 text-white shadow-sm' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Dry-Run
            </button>
            <button
              onClick={() => setDryRun(false)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                !dryRun 
                  ? 'bg-rose-600 text-white shadow-sm' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="WARNING: Will stop EC2s, delete EBS, and release EIPs tagged eligible-for-remediation"
            >
              Live Action
            </button>
          </div>

          {/* Action: Run ResourceScanner */}
          <button
            onClick={onRunScan}
            disabled={scanning}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded-lg text-xs font-medium border border-slate-700/80 transition shadow-sm disabled:opacity-50"
          >
            <RotateCw className={`h-3.5 w-3.5 ${scanning ? 'animate-spin text-cyan-400' : 'text-slate-400'}`} />
            <span>{scanning ? 'Scanning AWS...' : 'Run Scan Now'}</span>
          </button>

          {/* Action: Run Remediator */}
          <button
            onClick={onRunRemediate}
            disabled={remediating}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium text-white transition shadow-sm disabled:opacity-50 ${
              dryRun 
                ? 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-500/20' 
                : 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-500/20'
            }`}
          >
            <Zap className={`h-3.5 w-3.5 ${remediating ? 'animate-bounce' : ''}`} />
            <span>{remediating ? 'Remediating...' : dryRun ? 'Simulate Remediate' : 'Remediate Eligible'}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
