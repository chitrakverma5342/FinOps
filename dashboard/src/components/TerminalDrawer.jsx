import React, { useState, useRef, useEffect } from 'react';
import { 
  Terminal, 
  ChevronUp, 
  ChevronDown, 
  Trash2, 
  Copy, 
  Check,
  Circle
} from 'lucide-react';

export default function TerminalDrawer({ logs, onClearLogs }) {
  const [isOpen, setIsOpen] = useState(true);
  const [copied, setCopied] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current && isOpen) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isOpen]);

  const handleCopyLogs = () => {
    const text = logs.map(l => `[${l.timestamp}] [${l.level}] ${l.message}`).join('\n');
    navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-slate-950/95 backdrop-blur-md border-t border-slate-800 shadow-2xl transition-all duration-300">
      {/* Drawer Bar */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 flex items-center justify-between text-xs font-mono">
        <div 
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 text-slate-300 hover:text-white cursor-pointer select-none"
        >
          <Terminal className="h-3.5 w-3.5 text-cyan-400" />
          <span className="font-semibold text-slate-200">Execution & CloudWatch Stream</span>
          <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-800/40">
            <Circle className="h-1.5 w-1.5 fill-emerald-400 animate-pulse" /> Live Pipeline
          </span>
          <span className="text-slate-500 text-[11px]">({logs.length} events)</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopyLogs}
            className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 transition"
            title="Copy audit log stream"
          >
            {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
          </button>
          <button
            onClick={onClearLogs}
            className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 transition"
            title="Clear console"
          >
            <Trash2 className="h-3 w-3" />
          </button>
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 transition"
          >
            {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Terminal Body */}
      {isOpen && (
        <div 
          ref={scrollRef}
          className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-3 max-h-48 overflow-y-auto font-mono text-[11px] space-y-1"
        >
          {logs.length === 0 ? (
            <div className="text-slate-600 py-2">
              Console idle. Trigger 'Run Scan Now' or 'Remediate' to observe live pipeline execution.
            </div>
          ) : (
            logs.map((log, index) => {
              const levelColor = 
                log.level === 'WARN' ? 'text-amber-400' :
                log.level === 'ERROR' ? 'text-rose-400' :
                log.level === 'SUCCESS' ? 'text-emerald-400' : 'text-cyan-400';

              return (
                <div key={index} className="flex items-start gap-2 leading-relaxed hover:bg-slate-900/60 px-1 py-0.5 rounded">
                  <span className="text-slate-500 select-none">[{log.timestamp}]</span>
                  <span className={`font-semibold ${levelColor} select-none`}>[{log.level}]</span>
                  <span className="text-slate-300 font-normal">{log.message}</span>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
