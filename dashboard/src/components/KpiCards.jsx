import React from 'react';
import { 
  TrendingDown, 
  AlertTriangle, 
  Tags, 
  ShieldCheck, 
  CheckCircle2, 
  Cpu, 
  HardDrive, 
  Globe 
} from 'lucide-react';

export default function KpiCards({ summary, records }) {
  const wasteSaved = summary?.estimated_waste_saved_usd ?? 247.30;
  const activeFlagged = summary?.active_flagged_total ?? 1;
  const breakdown = summary?.flagged_breakdown ?? { ec2: 1, ebs: 0, eip: 0 };
  const governance = summary?.tag_governance ?? { eligible_for_remediation: 3, protected_do_not_stop: 1 };
  const operatingCost = summary?.operating_cost_usd ?? "0.00";
  const budgetLimit = summary?.budget_tripwire_limit_usd ?? "1.00";
  const budgetStatus = summary?.budget_status ?? "OK";

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* KPI 1: Estimated Monthly Waste Saved */}
      <div className="bg-slate-900/75 backdrop-blur-md border border-slate-800/80 rounded-xl p-4 shadow-lg hover:border-emerald-500/40 transition group">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-slate-400">Waste Prevented</span>
          <div className="h-8 w-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition">
            <TrendingDown className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-2 flex items-baseline gap-1">
          <span className="text-2xl font-bold font-mono tracking-tight text-emerald-400">
            ${typeof wasteSaved === 'number' ? wasteSaved.toFixed(2) : wasteSaved}
          </span>
          <span className="text-xs text-slate-400 font-mono">/ mo</span>
        </div>
        <div className="mt-2 text-xs text-slate-400 flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          <span>Reclaimed compute, storage & EIPs</span>
        </div>
      </div>

      {/* KPI 2: Active Flagged Idle Resources */}
      <div className="bg-slate-900/75 backdrop-blur-md border border-slate-800/80 rounded-xl p-4 shadow-lg hover:border-amber-500/40 transition group">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-slate-400">Active Flagged Idle</span>
          <div className="h-8 w-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 group-hover:scale-105 transition">
            <AlertTriangle className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-2 flex items-baseline gap-1">
          <span className="text-2xl font-bold font-mono tracking-tight text-amber-400">
            {activeFlagged}
          </span>
          <span className="text-xs text-slate-400 font-mono">resource{activeFlagged === 1 ? '' : 's'}</span>
        </div>
        <div className="mt-2 flex items-center gap-2 text-[11px] font-mono text-slate-400">
          <span className="flex items-center gap-0.5">
            <Cpu className="h-3 w-3 text-amber-400" /> {breakdown.ec2 || 0} EC2
          </span>
          <span className="text-slate-600">·</span>
          <span className="flex items-center gap-0.5">
            <HardDrive className="h-3 w-3 text-cyan-400" /> {breakdown.ebs || 0} EBS
          </span>
          <span className="text-slate-600">·</span>
          <span className="flex items-center gap-0.5">
            <Globe className="h-3 w-3 text-indigo-400" /> {breakdown.eip || 0} EIP
          </span>
        </div>
      </div>

      {/* KPI 3: Tag Governance Breakdown */}
      <div className="bg-slate-900/75 backdrop-blur-md border border-slate-800/80 rounded-xl p-4 shadow-lg hover:border-cyan-500/40 transition group">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-slate-400">Tag Governance</span>
          <div className="h-8 w-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 group-hover:scale-105 transition">
            <Tags className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold font-mono tracking-tight text-white">
            {governance.eligible_for_remediation + governance.protected_do_not_stop}
          </span>
          <span className="text-xs text-slate-400 font-mono">governed items</span>
        </div>
        <div className="mt-2 flex items-center justify-between text-[11px] font-mono">
          <span className="text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-800/50">
            {governance.eligible_for_remediation} eligible
          </span>
          <span className="text-amber-400 bg-amber-950/40 px-1.5 py-0.5 rounded border border-amber-800/50">
            {governance.protected_do_not_stop} DoNotStop
          </span>
        </div>
      </div>

      {/* KPI 4: Operating Cost & $1 Budget Tripwire */}
      <div className="bg-slate-900/75 backdrop-blur-md border border-slate-800/80 rounded-xl p-4 shadow-lg hover:border-emerald-500/40 transition group">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-slate-400">Guardian Operating Cost</span>
          <div className="h-8 w-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition">
            <CheckCircle2 className="h-4 w-4" />
          </div>
        </div>
        <div className="mt-2 flex items-baseline gap-1.5">
          <span className="text-2xl font-bold font-mono tracking-tight text-emerald-400">
            ${operatingCost}
          </span>
          <span className="text-[10px] font-mono text-emerald-300 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/60">
            AWS Always Free Tier
          </span>
        </div>
        <div className="mt-2 text-xs text-slate-400 flex items-center justify-between">
          <span className="text-[11px] font-mono text-slate-400">
            Tripwire: <strong className="text-white">${budgetLimit}/mo</strong>
          </span>
          <span className="text-[10px] font-mono font-semibold px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-400">
            STATUS: {budgetStatus}
          </span>
        </div>
      </div>
    </div>
  );
}
