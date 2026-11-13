import React, { useState } from 'react';
import { X, Download, CheckCircle2, AlertCircle, Loader2, RefreshCw, FileArchive, Play } from 'lucide-react';
import { Project, ClipConfig } from '../types';
import { api } from '../services/api';

interface BatchExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  project: Project;
  onUpdateProject: (project: Project) => void;
  onPreviewClip: (clip: ClipConfig) => void;
}

export const BatchExportModal: React.FC<BatchExportModalProps> = ({
  isOpen,
  onClose,
  project,
  onUpdateProject,
  onPreviewClip,
}) => {
  const [selectedIds, setSelectedIds] = useState<string[]>(
    project.clips?.map((c) => c.clip_id) || []
  );
  const [isExporting, setIsExporting] = useState(false);
  const [zipUrl, setZipUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const clips = project.clips || [];
  const completedCount = clips.filter((c) => c.status === 'exported').length;
  const totalCount = clips.length;

  const toggleSelect = (clipId: string) => {
    setSelectedIds((prev) =>
      prev.includes(clipId) ? prev.filter((id) => id !== clipId) : [...prev, clipId]
    );
  };

  const selectAll = (select: boolean) => {
    setSelectedIds(select ? clips.map((c) => c.clip_id) : []);
  };

  const handleStartExport = async () => {
    if (selectedIds.length === 0) return;
    try {
      setIsExporting(true);
      setError(null);

      // Trigger batch export
      await api.exportBatch(project.id, selectedIds);

      // Poll project status until complete
      const pollInterval = setInterval(async () => {
        try {
          const updated = await api.getProject(project.id);
          onUpdateProject(updated);

          if (updated.status === 'completed' || updated.progress === 100) {
            clearInterval(pollInterval);
            setIsExporting(false);

            // Fetch zip url
            try {
              const zipRes = await api.getDownloadZip(project.id);
              setZipUrl(zipRes.download_url);
            } catch (e) {
              console.error('Zip fetch error:', e);
            }
          }
        } catch (e) {
          clearInterval(pollInterval);
          setIsExporting(false);
        }
      }, 1500);
    } catch (e: any) {
      setError(e.message || 'Failed to start batch export');
      setIsExporting(false);
    }
  };

  const handleRetryClip = async (clipId: string) => {
    try {
      const rendered = await api.renderClip(project.id, clipId);
      const updatedClips = clips.map((c) => (c.clip_id === clipId ? rendered : c));
      onUpdateProject({ ...project, clips: updatedClips });
    } catch (e: any) {
      setError(`Retry failed for clip: ${e.message}`);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur-sm animate-in fade-in duration-200 sm:p-4">
      <div className="flex max-h-[calc(100dvh-1rem)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-[#0F1422] shadow-2xl sm:max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-violet-500/10 text-violet-400">
              <Download className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Batch Export Vertical Reels</h3>
              <p className="text-xs text-slate-400 font-medium">
                1080x1920 MP4 • 30 FPS • H.264 High Profile
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-5 overflow-y-auto p-4 sm:p-6">
          {error && (
            <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Export Overall Progress Bar */}
          {isExporting && (
            <div className="space-y-2 p-4 rounded-xl bg-slate-900 border border-slate-800">
              <div className="flex flex-wrap justify-between gap-2 text-xs font-semibold">
                <span className="text-slate-300 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
                  {project.status_message || 'Rendering clips in batch...'}
                </span>
                <span className="text-violet-400 font-mono">{project.progress}%</span>
              </div>
              <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-300"
                  style={{ width: `${project.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Download All as ZIP Banner */}
          {zipUrl && (
            <div className="flex flex-col gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <FileArchive className="w-6 h-6 text-emerald-400 shrink-0" />
                <div>
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">All Clips Ready</h4>
                  <p className="text-xs text-emerald-300/80">Packaged into a single high-speed ZIP archive</p>
                </div>
              </div>
              <a
                href={zipUrl}
                download
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs tracking-wide shadow-md transition cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download All (ZIP)</span>
              </a>
            </div>
          )}

          {/* Clips List Selection */}
          <div className="space-y-3">
            <div className="flex flex-col gap-2 px-1 text-xs font-semibold text-slate-400 sm:flex-row sm:items-center sm:justify-between">
              <span>Select Clips to Export ({selectedIds.length} / {clips.length})</span>
              <div className="flex items-center gap-3">
                <button onClick={() => selectAll(true)} className="text-violet-400 hover:underline cursor-pointer">
                  Select All
                </button>
                <span>•</span>
                <button onClick={() => selectAll(false)} className="hover:underline cursor-pointer">
                  Deselect All
                </button>
              </div>
            </div>

            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {clips.map((clip) => {
                const isSelected = selectedIds.includes(clip.clip_id);
                return (
                  <div
                    key={clip.clip_id}
                    className={`flex flex-col gap-3 rounded-xl border p-3 transition sm:flex-row sm:items-center sm:justify-between ${
                      isSelected
                        ? 'border-slate-700 bg-slate-900/90'
                        : 'border-slate-800/60 bg-slate-900/30 opacity-60'
                    }`}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(clip.clip_id)}
                        className="w-4 h-4 accent-violet-500 cursor-pointer"
                      />
                      <div className="min-w-0 space-y-0.5">
                        <p className="text-xs font-bold text-white">{clip.title}</p>
                        <p className="text-[11px] font-mono text-slate-400">
                          {clip.duration}s • {clip.crop_config.aspect_ratio} •{' '}
                          {clip.caption_config.enabled ? 'Subtitles On' : 'No Subtitles'}
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {clip.status === 'exported' && (
                        <>
                          <button
                            onClick={() => onPreviewClip(clip)}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition cursor-pointer"
                            title="Preview Exported Video"
                          >
                            <Play className="w-3.5 h-3.5" />
                          </button>
                          <a
                            href={clip.output_url}
                            download
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 text-xs font-semibold transition"
                          >
                            <Download className="w-3 h-3" />
                            <span>Download MP4</span>
                          </a>
                        </>
                      )}

                      {clip.status === 'rendering' && (
                        <span className="flex items-center gap-1.5 text-xs text-amber-400 font-semibold px-2.5 py-1 rounded-lg bg-amber-500/10">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          Rendering...
                        </span>
                      )}

                      {clip.status === 'error' && (
                        <button
                          onClick={() => handleRetryClip(clip.clip_id)}
                          className="flex items-center gap-1 text-xs text-rose-400 hover:text-rose-300 px-2 py-1 rounded-lg bg-rose-500/10 cursor-pointer"
                        >
                          <RefreshCw className="w-3 h-3" />
                          Retry
                        </button>
                      )}

                      {clip.status === 'ready' && (
                        <span className="text-[11px] text-slate-400 font-medium px-2 py-1 rounded-lg bg-slate-800">
                          Ready to render
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 border-t border-slate-800 bg-[#0B0F17] px-4 py-4 sm:px-6">
          <button
            onClick={onClose}
            disabled={isExporting}
            className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white cursor-pointer"
          >
            Close
          </button>

          <button
            onClick={handleStartExport}
            disabled={isExporting || selectedIds.length === 0}
            className="flex items-center justify-center gap-2 px-3 sm:px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs tracking-wide shadow-lg shadow-violet-600/30 transition cursor-pointer disabled:opacity-50"
          >
            {isExporting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Exporting Batch...</span>
              </>
            ) : (
              <>
                <Download className="w-3.5 h-3.5" />
                <span>Export {selectedIds.length} Selected Clips</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
