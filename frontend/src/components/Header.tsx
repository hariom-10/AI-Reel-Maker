import React from 'react';
import { Upload, Cpu, HardDrive } from 'lucide-react';

interface HeaderProps {
  title: string;
  subtitle?: string;
  onNewProject: () => void;
  isProcessing?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ title, subtitle, onNewProject, isProcessing }) => {
  return (
    <header className="h-16 border-b border-slate-800/80 bg-[#0B0F17]/90 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-10 select-none">
      <div>
        <h2 className="text-lg font-bold text-slate-100">{title}</h2>
        {subtitle && <p className="text-xs text-slate-400 font-medium">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        {/* Hardware Status Tag */}
        <div className="hidden md:flex items-center gap-3 px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-400">
          <div className="flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-indigo-400" />
            <span className="font-mono text-[11px] text-slate-300">GPU / FFmpeg</span>
          </div>
          <span className="text-slate-700">|</span>
          <div className="flex items-center gap-1.5">
            <HardDrive className="w-3.5 h-3.5 text-cyan-400" />
            <span className="font-mono text-[11px] text-slate-300">Local Disk</span>
          </div>
        </div>

        {/* Action Button */}
        <button
          onClick={onNewProject}
          disabled={isProcessing}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs tracking-wide shadow-md shadow-violet-600/20 transition-all cursor-pointer disabled:opacity-50"
        >
          <Upload className="w-3.5 h-3.5" />
          <span>New Video Project</span>
        </button>
      </div>
    </header>
  );
};
