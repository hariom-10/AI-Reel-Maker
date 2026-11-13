import React from 'react';
import { Film, Video, Clock, CheckCircle2, Plus, Sparkles, ArrowRight, Play, Layers } from 'lucide-react';
import { DashboardStats, Project } from '../types';

interface DashboardViewProps {
  stats: DashboardStats | null;
  onNewProject: () => void;
  onOpenProject: (project: Project) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ stats, onNewProject, onOpenProject }) => {
  const cards = [
    {
      title: 'Total Videos Uploaded',
      value: stats?.total_videos ?? 0,
      icon: Video,
      color: 'from-blue-500 to-indigo-600',
      textColor: 'text-indigo-400',
    },
    {
      title: 'Total Clips Generated',
      value: stats?.total_clips ?? 0,
      icon: Film,
      color: 'from-violet-500 to-purple-600',
      textColor: 'text-violet-400',
    },
    {
      title: 'Processing Videos',
      value: stats?.processing_videos ?? 0,
      icon: Clock,
      color: 'from-amber-500 to-orange-600',
      textColor: 'text-amber-400',
    },
    {
      title: 'Completed Projects',
      value: stats?.completed_projects ?? 0,
      icon: CheckCircle2,
      color: 'from-emerald-500 to-teal-600',
      textColor: 'text-emerald-400',
    },
  ];

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:space-y-8 sm:p-6 lg:p-8">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-violet-900/60 via-indigo-900/40 to-slate-900 border border-violet-500/20 p-5 shadow-2xl sm:p-8">
        <div className="absolute -right-10 -bottom-10 w-96 h-96 bg-violet-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 max-w-2xl space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/30 text-violet-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Reel Maker Pro 2.0</span>
          </div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight leading-tight sm:text-3xl">
            Turn Long Videos Into Short Clips
          </h1>
          <p className="text-sm text-slate-300 leading-relaxed font-medium">
            Find scene and audio-activity highlights, format clips for vertical platforms, add optional local Whisper captions, and batch-export your reels.
          </p>
          <div className="pt-2 flex flex-wrap items-center gap-3">
            <button
              onClick={onNewProject}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs tracking-wide shadow-lg shadow-violet-600/30 transition cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Upload Video Now</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 sm:gap-5">
        {cards.map((card, i) => {
          const Icon = card.icon;
          return (
            <div
              key={i}
              className="p-5 rounded-2xl bg-[#0F1422] border border-slate-800/80 hover:border-slate-700/80 transition-all shadow-lg flex items-center justify-between"
            >
              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-400">{card.title}</span>
                <p className="text-2xl font-black text-white tracking-tight">{card.value}</p>
              </div>
              <div className={`p-3 rounded-xl bg-gradient-to-br ${card.color} text-white shadow-md`}>
                <Icon className="w-5 h-5" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Recent Projects Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Layers className="w-5 h-5 text-violet-400" />
            <h3 className="text-lg font-bold text-white tracking-tight">Recent Projects</h3>
          </div>
          <span className="text-xs font-semibold text-slate-400">
            {stats?.recent_projects?.length ?? 0} Projects Saved
          </span>
        </div>

        {stats?.recent_projects && stats.recent_projects.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-6">
            {stats.recent_projects.map((project) => (
              <div
                key={project.id}
                onClick={() => onOpenProject(project)}
                className="group p-4 rounded-2xl bg-[#0F1422] border border-slate-800 hover:border-violet-500/50 hover:bg-[#121929] transition-all duration-200 cursor-pointer shadow-lg flex flex-col justify-between space-y-4"
              >
                {/* Thumbnail Header */}
                <div className="relative aspect-video rounded-xl bg-slate-900 overflow-hidden border border-slate-800 group-hover:border-violet-500/30">
                  {project.scenes?.[0]?.thumbnail_url ? (
                    <img
                      src={project.scenes[0].thumbnail_url}
                      alt={project.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-400">
                      <Film className="w-8 h-8" />
                    </div>
                  )}
                  {/* Duration Badge */}
                  <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-[10px] font-mono font-bold text-white">
                    {formatDuration(project.metadata.duration)}
                  </div>
                  {/* Status Pill */}
                  <div className="absolute top-2 left-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase ${
                        project.status === 'completed'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : project.status === 'analyzing'
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          : 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
                      }`}
                    >
                      {project.status}
                    </span>
                  </div>
                </div>

                {/* Details */}
                <div className="space-y-1">
                  <h4 className="text-sm font-bold text-white group-hover:text-violet-300 transition truncate">
                    {project.name}
                  </h4>
                  <p className="text-xs text-slate-400 font-medium">
                    {project.clips?.length ?? 0} Reels Generated • {project.metadata.width}x{project.metadata.height}
                  </p>
                </div>

                {/* Card Action */}
                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-semibold text-slate-400 group-hover:text-violet-400">
                  <span>Open Studio</span>
                  <ArrowRight className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* Empty Projects State */
          <div className="p-12 text-center rounded-3xl bg-[#0F1422] border border-slate-800 space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-violet-500/10 text-violet-400 flex items-center justify-center mx-auto">
              <Film className="w-8 h-8" />
            </div>
            <div className="space-y-1 max-w-sm mx-auto">
              <h4 className="text-base font-bold text-white">No Video Projects Yet</h4>
              <p className="text-xs text-slate-400">
                Upload your first video to start automatically detecting viral moments and creating shorts.
              </p>
            </div>
            <button
              onClick={onNewProject}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs tracking-wide shadow-lg shadow-violet-600/30 transition cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Create First Project</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
