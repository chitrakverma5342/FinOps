import React from 'react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend
} from 'recharts';
import { Activity, BarChart2 } from 'lucide-react';
import { MOCK_TREND_CHART } from '../simulationData';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-900/95 border border-slate-700/80 p-3 rounded-lg shadow-xl backdrop-blur-md text-xs font-mono">
        <p className="font-semibold text-slate-200 mb-1.5">{label}</p>
        {payload.map((entry, index) => (
          <p key={`item-${index}`} className="flex items-center justify-between gap-4 py-0.5" style={{ color: entry.color }}>
            <span>{entry.name}:</span>
            <span className="font-bold">${entry.value.toFixed(2)}</span>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function Charts({ records }) {
  // Aggregate status breakdown for BarChart
  const breakdownData = [
    {
      category: 'EC2',
      Flagged: records.filter(r => r.resource_type === 'EC2' && r.status === 'FLAGGED').length,
      Remediated: records.filter(r => r.resource_type === 'EC2' && (r.status === 'REMEDIATED' || r.status === 'DRY_RUN_SIMULATED')).length,
      Protected: records.filter(r => r.resource_type === 'EC2' && r.status === 'SKIPPED_DO_NOT_STOP').length,
    },
    {
      category: 'EBS',
      Flagged: records.filter(r => r.resource_type === 'EBS' && r.status === 'FLAGGED').length,
      Remediated: records.filter(r => r.resource_type === 'EBS' && (r.status === 'REMEDIATED' || r.status === 'DRY_RUN_SIMULATED')).length,
      Protected: records.filter(r => r.resource_type === 'EBS' && r.status === 'SKIPPED_DO_NOT_STOP').length,
    },
    {
      category: 'EIP',
      Flagged: records.filter(r => r.resource_type === 'EIP' && r.status === 'FLAGGED').length,
      Remediated: records.filter(r => r.resource_type === 'EIP' && (r.status === 'REMEDIATED' || r.status === 'DRY_RUN_SIMULATED')).length,
      Protected: records.filter(r => r.resource_type === 'EIP' && r.status === 'SKIPPED_DO_NOT_STOP').length,
    },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Visual Analytics 1: Cost Hygiene Trend (AreaChart) */}
      <div className="bg-slate-900/75 backdrop-blur-md border border-slate-800/80 rounded-xl p-4 shadow-lg flex flex-col justify-between">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-slate-200">Cost Hygiene Trajectory</h3>
          </div>
          <span className="text-[11px] font-mono text-slate-400">7-Day Rolling Trend</span>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={MOCK_TREND_CHART} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorSaved" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10B981" stopOpacity={0.4}/>
                  <stop offset="95%" stopColor="#10B981" stopOpacity={0.0}/>
                </linearGradient>
                <linearGradient id="colorWaste" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#F43F5E" stopOpacity={0.4}/>
                  <stop offset="95%" stopColor="#F43F5E" stopOpacity={0.0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
              <XAxis dataKey="date" stroke="#64748B" fontSize={11} tickLine={false} />
              <YAxis stroke="#64748B" fontSize={11} tickLine={false} tickFormatter={(val) => `$${val}`} />
              <Tooltip content={<CustomTooltip />} />
              <Area 
                type="monotone" 
                dataKey="remediatedSavings" 
                name="Remediated Savings ($)" 
                stroke="#10B981" 
                strokeWidth={2}
                fillOpacity={1} 
                fill="url(#colorSaved)" 
              />
              <Area 
                type="monotone" 
                dataKey="flaggedWaste" 
                name="Flagged Waste ($)" 
                stroke="#F43F5E" 
                strokeWidth={2}
                fillOpacity={1} 
                fill="url(#colorWaste)" 
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-sm bg-emerald-500"></span>
            <span>Remediated Cumulative ($)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-sm bg-rose-500"></span>
            <span>Active Idle Risk ($)</span>
          </div>
        </div>
      </div>

      {/* Visual Analytics 2: Idle Resource Distribution (BarChart) */}
      <div className="bg-slate-900/75 backdrop-blur-md border border-slate-800/80 rounded-xl p-4 shadow-lg flex flex-col justify-between">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <BarChart2 className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-slate-200">Resource Governance Status</h3>
          </div>
          <span className="text-[11px] font-mono text-slate-400">By Cloud Asset Class</span>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={breakdownData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
              <XAxis dataKey="category" stroke="#64748B" fontSize={11} tickLine={false} />
              <YAxis stroke="#64748B" fontSize={11} tickLine={false} allowDecimals={false} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#0F172A', borderColor: '#334155', borderRadius: '8px', fontSize: '11px', fontFamily: 'monospace' }}
                itemStyle={{ padding: '2px 0' }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace', paddingTop: '8px' }} />
              <Bar dataKey="Flagged" fill="#F59E0B" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Remediated" fill="#10B981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Protected" fill="#6366F1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
          <span>Target Governance: 100% of idle assets safely handled</span>
          <span className="text-emerald-400">Exclusion Rule Active</span>
        </div>
      </div>
    </div>
  );
}
