import React from 'react';
import { LayoutDashboard, Film, FolderKanban, Library, Settings, Sparkles, Layers } from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  activeProjectName?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onTabChange, activeProjectName }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'studio', label: 'Create Reels', icon: Film },
    { id: 'projects', label: 'My Projects', icon: FolderKanban },
    { id: 'library', label: 'Video Library', icon: Library },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-[#0D121F] border-r border-slate-800/80 flex flex-col h-screen select-none shrink-0 z-20">
      {/* Brand Logo */}
      <div className="p-6 flex items-center gap-3 border-b border-slate-800/60">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
            AI Reel Maker
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-violet-500/20 text-violet-400 border border-violet-500/30">PRO</span>
          </h1>
          <p className="text-xs text-slate-400 font-medium">Video to Viral Shorts</p>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-6 space-y-1.5 overflow-y-auto">
        <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
          Menu
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center gap-3.5 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-gradient-to-r from-violet-600/90 to-indigo-600/90 text-white shadow-lg shadow-violet-600/20 font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}

        {/* Current Active Project Quick-Card if in Studio */}
        {activeProjectName && (
          <div className="mt-8 mx-1 p-3.5 rounded-xl bg-slate-800/40 border border-slate-700/50 text-left">
            <div className="flex items-center gap-2 text-xs font-semibold text-violet-400 mb-1">
              <Layers className="w-3.5 h-3.5" />
              <span>Active Project</span>
            </div>
            <p className="text-xs text-slate-200 font-medium truncate" title={activeProjectName}>
              {activeProjectName}
            </p>
          </div>
        )}
      </nav>

      {/* Local Engine Status Footer */}
      <div className="p-4 m-3 rounded-xl bg-slate-900/80 border border-slate-800 text-xs">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-slate-400">Processing Mode</span>
          <span className="flex items-center gap-1.5 text-emerald-400 font-semibold text-[11px]">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            100% Local
          </span>
        </div>
        <p className="text-[11px] text-slate-400 leading-relaxed">
          FFmpeg 8.1 Hardware Accel Active. No paid APIs required.
        </p>
      </div>
    </aside>
  );
};
