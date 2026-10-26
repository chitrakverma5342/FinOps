import React, { useState } from 'react';
import { 
  Search, 
  Copy, 
  Check, 
  Cpu, 
  HardDrive, 
  Globe, 
  ShieldAlert, 
  ShieldCheck, 
  Play, 
  FileText,
  Clock,
  ExternalLink
} from 'lucide-react';

export default function AuditTable({ records, onRemediateRow, dryRun }) {
  const [filterTab, setFilterTab] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedId, setCopiedId] = useState(null);

  const handleCopy = (id) => {
    navigator.clipboard?.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Filter records based on selected tab and search query
  const filteredRecords = records.filter(record => {
    // Tab filter
    if (filterTab === 'FLAGGED' && record.status !== 'FLAGGED') return false;
    if (filterTab === 'REMEDIATED' && record.status !== 'REMEDIATED' && record.status !== 'DRY_RUN_SIMULATED') return false;
    if (filterTab === 'PROTECTED' && record.status !== 'SKIPPED_DO_NOT_STOP') return false;
    if (filterTab === 'CLEAN' && record.status !== 'CLEAN') return false;

    // Search query filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const idMatch = (record.resource_id || '').toLowerCase().includes(q);
      const typeMatch = (record.resource_type || '').toLowerCase().includes(q);
      const statusMatch = (record.status || '').toLowerCase().includes(q);
      const tagsMatch = JSON.stringify(record.tags || {}).toLowerCase().includes(q);
      return idMatch || typeMatch || statusMatch || tagsMatch;
    }

    return true;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'FLAGGED':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30">FLAGGED</span>;
      case 'REMEDIATED':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">REMEDIATED</span>;
      case 'DRY_RUN_SIMULATED':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">SIMULATED</span>;
      case 'SKIPPED_DO_NOT_STOP':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">SKIPPED (GUARD)</span>;
      case 'CLEAN':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-slate-800 text-slate-400 border border-slate-700">CLEAN SCAN</span>;
      default:
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-mono text-slate-400">{status}</span>;
    }
  };

  const getResourceIcon = (type) => {
    switch (type) {
      case 'EC2': return <Cpu className="h-4 w-4 text-amber-400" />;
      case 'EBS': return <HardDrive className="h-4 w-4 text-cyan-400" />;
      case 'EIP': return <Globe className="h-4 w-4 text-indigo-400" />;
      default: return <FileText className="h-4 w-4 text-slate-400" />;
    }
  };

  return (
    <div className="bg-slate-900/75 backdrop-blur-md border border-slate-800/80 rounded-xl overflow-hidden shadow-xl">
      {/* Table Header Controls */}
      <div className="p-4 border-b border-slate-800/80 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        {/* Filter Tabs */}
        <div className="flex flex-wrap items-center gap-1 bg-slate-950/60 p-1 rounded-lg border border-slate-800">
          {[
            { id: 'ALL', label: 'All Records' },
            { id: 'FLAGGED', label: 'Flagged Idle' },
            { id: 'REMEDIATED', label: 'Remediated' },
            { id: 'PROTECTED', label: 'Protected (DoNotStop)' },
            { id: 'CLEAN', label: 'Clean Scans' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setFilterTab(tab.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${
                filterTab === tab.id
                  ? 'bg-slate-800 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative min-w-[240px]">
          <Search className="h-3.5 w-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search resource ID, type, tag..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/70 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500/50"
          />
        </div>
      </div>

      {/* Responsive Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-800/80 bg-slate-950/40 text-slate-400 font-mono text-[11px]">
              <th className="py-3 px-4">Resource Identifier</th>
              <th className="py-3 px-4">Type & State</th>
              <th className="py-3 px-4">Idle Duration</th>
              <th className="py-3 px-4">Cost Waste</th>
              <th className="py-3 px-4">Governance Tags</th>
              <th className="py-3 px-4">Audit Status</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {filteredRecords.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-slate-500 font-mono text-xs">
                  No records matching current filter or search criteria.
                </td>
              </tr>
            ) : (
              filteredRecords.map((item, index) => {
                const isCleanSummary = (item.resource_id || '').startsWith('SCAN_SUMMARY');
                const isFlagged = item.status === 'FLAGGED';
                const hasDoNotStop = item.do_not_stop === true;
                const hasEligible = item.eligible_for_remediation === true;

                return (
                  <tr 
                    key={item.resource_id + (item.scan_timestamp || index)}
                    className="hover:bg-slate-800/30 transition group"
                  >
                    {/* Resource ID + Copy */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-slate-200 font-medium">
                          {isCleanSummary ? 'CLEAN ACCOUNT AUDIT' : item.resource_id}
                        </span>
                        {!isCleanSummary && (
                          <button
                            onClick={() => handleCopy(item.resource_id)}
                            className="text-slate-500 hover:text-slate-300 transition"
                            title="Copy Resource ID"
                          >
                            {copiedId === item.resource_id ? (
                              <Check className="h-3 w-3 text-emerald-400" />
                            ) : (
                              <Copy className="h-3 w-3" />
                            )}
                          </button>
                        )}
                      </div>
                      <div className="text-[10px] font-mono text-slate-500 flex items-center gap-1 mt-0.5">
                        <Clock className="h-2.5 w-2.5" />
                        <span>{item.scan_timestamp ? item.scan_timestamp.replace('T', ' ').substring(0, 19) + ' UTC' : 'Recent'}</span>
                      </div>
                    </td>

                    {/* Type & State */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        {getResourceIcon(item.resource_type)}
                        <span className="font-medium text-slate-300">
                          {item.resource_type}
                        </span>
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700/60">
                          {item.resource_state || 'unknown'}
                        </span>
                      </div>
                    </td>

                    {/* Idle Duration */}
                    <td className="py-3 px-4 font-mono text-slate-300">
                      {isCleanSummary ? '—' : `${item.idle_duration_hours || 0} hrs`}
                    </td>

                    {/* Cost Waste */}
                    <td className="py-3 px-4 font-mono">
                      {isCleanSummary ? (
                        <span className="text-slate-500">$0.00</span>
                      ) : (
                        <div>
                          <span className={`font-semibold ${isFlagged ? 'text-amber-400' : 'text-emerald-400'}`}>
                            ${item.estimated_monthly_waste_usd ? Number(item.estimated_monthly_waste_usd).toFixed(2) : '0.00'}/mo
                          </span>
                          <div className="text-[10px] text-slate-500">
                            ${item.estimated_hourly_cost_usd ? Number(item.estimated_hourly_cost_usd).toFixed(4) : '0.00'}/hr
                          </div>
                        </div>
                      )}
                    </td>

                    {/* Governance Tags */}
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1">
                        {hasDoNotStop && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-700/60">
                            <ShieldCheck className="h-2.5 w-2.5 text-indigo-400" />
                            DoNotStop=true
                          </span>
                        )}
                        {hasEligible && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-700/60">
                            eligible-for-remediation
                          </span>
                        )}
                        {!hasDoNotStop && !hasEligible && !isCleanSummary && (
                          <span className="text-[10px] font-mono text-slate-500">
                            No governance tags
                          </span>
                        )}
                        {isCleanSummary && (
                          <span className="text-[10px] font-mono text-emerald-400">
                            Zero idle waste detected
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Audit Status */}
                    <td className="py-3 px-4">
                      {getStatusBadge(item.status)}
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-4 text-right">
                      {isFlagged ? (
                        <button
                          onClick={() => onRemediateRow(item)}
                          className={`inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded transition shadow-sm ${
                            hasDoNotStop
                              ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                              : dryRun
                              ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
                              : 'bg-emerald-600 hover:bg-emerald-500 text-white'
                          }`}
                          disabled={hasDoNotStop}
                          title={hasDoNotStop ? 'Strictly protected by DoNotStop tag' : 'Execute safe remediation'}
                        >
                          <Play className="h-2.5 w-2.5" />
                          <span>{hasDoNotStop ? 'Protected' : dryRun ? 'Simulate' : 'Remediate'}</span>
                        </button>
                      ) : (
                        <span className="text-[11px] font-mono text-slate-500">
                          {item.status === 'REMEDIATED' ? 'Resolved' : item.status === 'SKIPPED_DO_NOT_STOP' ? 'Preserved' : 'Audited'}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
