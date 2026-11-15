import React, { useState } from 'react';
import { Sparkles, CheckSquare, Square, Volume2, Eye, Play, RefreshCw } from 'lucide-react';
import { DetectedScene, Project } from '../types';

interface SceneInspectorProps {
  project: Project;
  onSelectScene: (sceneId: string, selected: boolean) => void;
  onSelectAll: (selected: boolean) => void;
  onPreviewScene: (scene: DetectedScene) => void;
  onOpenReelGenerator: () => void;
  onReAnalyze: () => void;
  isAnalyzing: boolean;
}

export const SceneInspector: React.FC<SceneInspectorProps> = ({
  project,
  onSelectScene,
  onSelectAll,
  onPreviewScene,
  onOpenReelGenerator,
  onReAnalyze,
  isAnalyzing,
}) => {
  const [filter, setFilter] = useState<'all' | 'high_audio' | 'high_visual_change' | 'selected'>('all');

  const scenes = project.scenes || [];

  const filteredScenes = scenes.filter((scene) => {
    if (filter === 'selected') return scene.selected;
    if (filter === 'high_audio') return scene.audio_activity >= 0.7;
    if (filter === 'high_visual_change') return scene.visual_activity >= 0.5;
    return true;
  });

  const selectedCount = scenes.filter((s) => s.selected).length;

  const formatTimestamp = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-6">
      {/* Top Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-[#0F1422] border border-slate-800">
        <div className="flex min-w-0 items-start gap-3">
          <div className="p-2 rounded-xl bg-violet-500/10 text-violet-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="flex flex-wrap items-center gap-2 text-sm font-bold text-white">
              Detected Scenes & Moments
              <span className="text-xs px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-300 font-mono">
                {scenes.length} Scenes
              </span>
            </h3>
            <p className="text-xs text-slate-400 font-medium">
              Ranked using speech when local Whisper is available, audio activity, and sampled visual changes—not emotion or action recognition.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={onReAnalyze}
            disabled={isAnalyzing}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 transition cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isAnalyzing ? 'animate-spin text-violet-400' : ''}`} />
            <span>Re-Analyze</span>
          </button>

          <button
            onClick={onOpenReelGenerator}
            disabled={selectedCount === 0}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs tracking-wide shadow-md shadow-violet-600/30 transition cursor-pointer disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Generate Reels ({selectedCount})</span>
          </button>
        </div>
      </div>

      {/* Filter Chips & Selection Bar */}
      <div className="flex flex-col gap-3 px-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {(['all', 'high_audio', 'high_visual_change', 'selected'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold capitalize transition cursor-pointer ${
                filter === tab
                  ? 'bg-violet-600 text-white shadow-sm'
                  : 'bg-slate-900/80 text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              {tab === 'high_visual_change' ? 'high visual change' : tab.replace('_', ' ')}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 text-xs">
          <button
            onClick={() => onSelectAll(true)}
            className="text-violet-400 hover:text-violet-300 font-semibold cursor-pointer"
          >
            Select All
          </button>
          <span className="text-slate-700">•</span>
          <button
            onClick={() => onSelectAll(false)}
            className="text-slate-400 hover:text-slate-300 font-semibold cursor-pointer"
          >
            Deselect All
          </button>
        </div>
      </div>

      {/* Scenes Grid */}
      {filteredScenes.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-5">
          {filteredScenes.map((scene) => {
            const isTopScore = scene.score >= 0.8;
            return (
              <div
                key={scene.scene_id}
                className={`group rounded-2xl bg-[#0F1422] border transition-all duration-200 overflow-hidden flex flex-col justify-between ${
                  scene.selected
                    ? 'border-violet-500/60 shadow-lg shadow-violet-500/5 bg-[#121829]'
                    : 'border-slate-800/80 opacity-75 hover:opacity-100 hover:border-slate-700'
                }`}
              >
                {/* Thumbnail Header */}
                <div className="relative aspect-video bg-black overflow-hidden">
                  {scene.thumbnail_url ? (
                    <img
                      src={scene.thumbnail_url}
                      alt={scene.scene_id}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  ) : (
                    <div className="w-full h-full bg-slate-900 flex items-center justify-center text-slate-400">
                      <span>No Thumbnail</span>
                    </div>
                  )}

                  {/* Play Button Overlay */}
                  <button
                    onClick={() => onPreviewScene(scene)}
                    className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity cursor-pointer"
                  >
                    <div className="w-10 h-10 rounded-full bg-violet-600/90 text-white flex items-center justify-center shadow-lg">
                      <Play className="w-4 h-4 ml-0.5 fill-current" />
                    </div>
                  </button>

                  {/* Timestamp Badge */}
                  <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-[10px] font-mono font-bold text-white">
                    {formatTimestamp(scene.start_time)} - {formatTimestamp(scene.end_time)} ({scene.duration}s)
                  </div>

                  {/* Relative moment score badge */}
                  <div className="absolute top-2 right-2">
                    <span
                      className={`px-2 py-0.5 rounded-md text-[10px] font-black tracking-wider uppercase backdrop-blur-md ${
                        isTopScore
                          ? 'bg-gradient-to-r from-amber-500 to-rose-500 text-white shadow-md'
                          : 'bg-black/70 text-slate-300'
                      }`}
                    >
                      {Math.round(scene.score * 100)}% Moment Score
                    </span>
                  </div>

                  {/* Selection Checkbox */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectScene(scene.scene_id, !scene.selected);
                    }}
                    className="absolute top-2 left-2 p-1 rounded-md bg-black/70 text-white cursor-pointer hover:bg-black"
                  >
                    {scene.selected ? (
                      <CheckSquare className="w-4 h-4 text-violet-400 fill-violet-500/20" />
                    ) : (
                      <Square className="w-4 h-4 text-slate-400" />
                    )}
                  </button>
                </div>

                {/* Metrics & Content */}
                <div className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-white truncate">{scene.summary || scene.scene_id}</h4>
                    <span className="text-[11px] font-mono text-slate-400">{scene.duration}s</span>
                  </div>

                  {/* Signal Meters */}
                  <div className="space-y-1.5 pt-1">
                    {/* Audio activity proxy; speech is not transcribed during ranking. */}
                    <div className="space-y-0.5">
                      <div className="flex justify-between text-[10px] font-semibold text-slate-400">
                        <span className="flex items-center gap-1">
                          <Volume2 className="w-3 h-3 text-cyan-400" />
                          Audio Activity
                        </span>
                        <span className="font-mono">{Math.round(scene.audio_activity * 100)}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-cyan-400 rounded-full"
                          style={{ width: `${scene.audio_activity * 100}%` }}
                        />
                      </div>
                    </div>

                    {/* Visual Motion */}
                    <div className="space-y-0.5">
                      <div className="flex justify-between text-[10px] font-semibold text-slate-400">
                        <span className="flex items-center gap-1">
                          <Eye className="w-3 h-3 text-violet-400" />
                          Sampled Visual Change
                        </span>
                        <span className="font-mono">{Math.round(scene.visual_activity * 100)}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-violet-400 rounded-full"
                          style={{ width: `${scene.visual_activity * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="p-12 text-center rounded-2xl bg-[#0F1422] border border-slate-800 space-y-2">
          <p className="text-sm font-semibold text-slate-300">No scenes match the selected filter</p>
          <button
            onClick={() => setFilter('all')}
            className="text-xs text-violet-400 hover:underline cursor-pointer"
          >
            Reset Filters
          </button>
        </div>
      )}
    </div>
  );
};
