import React, { useCallback, useEffect, useState, useRef } from 'react';
import {
  Eraser, ShieldAlert, Sparkles, Play, Pause, Eye, Plus, Trash2,
  Download, CheckCircle2, Layers, Loader2, Save
} from 'lucide-react';
import { Project, CleanupRegion } from '../types';
import { api } from '../services/api';

interface VideoCleanupViewProps {
  project: Project;
  onUpdateProject: (project: Project) => void;
  onPreviewVideo: (url: string, title: string) => void;
}

export const VideoCleanupView: React.FC<VideoCleanupViewProps> = ({
  project,
  onUpdateProject,
  onPreviewVideo,
}) => {
  const [regions, setRegions] = useState<CleanupRegion[]>(
    project.cleanup_regions && project.cleanup_regions.length > 0
      ? project.cleanup_regions
      : []
  );

  const [activeRegionId, setActiveRegionId] = useState<string>(regions[0]?.id || '');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [videoContentBounds, setVideoContentBounds] = useState<{
    left: number;
    top: number;
    width: number;
    height: number;
  } | null>(null);

  // Before / After inspection
  const [previewMode, setPreviewMode] = useState<'original' | 'inpaint_preview'>('original');
  const [previewFrameUrl, setPreviewFrameUrl] = useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  // Authorization state
  const [authConfirmed, setAuthConfirmed] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSavingRegions, setIsSavingRegions] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    id: string;
    pointerX: number;
    pointerY: number;
    originX: number;
    originY: number;
  } | null>(null);

  const activeRegion = regions.find((r) => r.id === activeRegionId) || regions[0];
  const getVideoContentBounds = useCallback(() => {
    const video = videoRef.current;
    const container = containerRef.current;

    if (!video || !container || !video.videoWidth || !video.videoHeight) {
      return null;
    }

    const videoRect = video.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();

    const scale = Math.min(
      videoRect.width / video.videoWidth,
      videoRect.height / video.videoHeight
    );

    const width = video.videoWidth * scale;
    const height = video.videoHeight * scale;

    return {
      left:
        videoRect.left - containerRect.left - container.clientLeft +
        (videoRect.width - width) / 2,
      top:
        videoRect.top - containerRect.top - container.clientTop +
        (videoRect.height - height) / 2,
      width,
      height,
    };
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const updateBounds = () => setVideoContentBounds(getVideoContentBounds());
    const observer = new ResizeObserver(updateBounds);
    observer.observe(container);
    updateBounds();
    return () => observer.disconnect();
  }, [getVideoContentBounds]);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleAddRegion = () => {
    const newId = `region_${Date.now().toString().slice(-4)}`;
    const newReg: CleanupRegion = {
      id: newId,
      type: 'inpaint',
      x: 35,
      y: 40,
      width: 25,
      height: 12,
      blur_strength: 20,
      replacement_text: '',
      text_color: '#FFFFFF',
      bg_color: '#000000',
      bg_opacity: 0.6,
    };
    const updated = [...regions, newReg];
    setRegions(updated);
    setActiveRegionId(newId);
  };

  const handleDeleteRegion = (id: string) => {
    const updated = regions.filter((r) => r.id !== id);
    setRegions(updated);
    setActiveRegionId(updated[0]?.id || '');
  };

  const handleUpdateActiveRegion = (partial: Partial<CleanupRegion>) => {
    setRegions((prev) =>
      prev.map((r) => (r.id === activeRegionId ? { ...r, ...partial } : r))
    );
  };

  // Render a single-frame preview of the selected FFmpeg operation.
  const handleFetchPreviewFrame = async () => {
    if (!authConfirmed) {
      setStatusMsg('Confirm that you are authorized to edit this video before previewing cleanup.');
      return;
    }
    try {
      setIsPreviewLoading(true);
      const res = await api.previewCleanupFrame(
        project.id,
        { regions, authorization_confirmed: authConfirmed },
        currentTime || 2.0
      );
      setPreviewFrameUrl(res.preview_url);
      setPreviewMode('inpaint_preview');
      setIsPreviewLoading(false);
    } catch (e: any) {
      console.error(e);
      setStatusMsg(`Could not preview the selected region: ${e.message}`);
      setIsPreviewLoading(false);
    }
  };

  const handleStartCleanup = async () => {
    if (!authConfirmed || regions.length === 0) {
      setStatusMsg(regions.length === 0
        ? 'Add and position at least one cleanup region before exporting.'
        : 'Confirm that you are authorized to edit this video before exporting.');
      return;
    }

    try {
      setIsProcessing(true);
      setStatusMsg('Starting authorized region cleanup in the background...');

      await api.triggerCleanup(project.id, {
        regions,
        authorization_confirmed: true,
      });

      // Poll until done
      const interval = setInterval(async () => {
        try {
          const updated = await api.getProject(project.id);
          onUpdateProject(updated);

          if (updated.status !== 'cleaning') {
            clearInterval(interval);
            setIsProcessing(false);
            setStatusMsg(updated.status_message);
          }
        } catch {
          clearInterval(interval);
          setIsProcessing(false);
        }
      }, 2000);
    } catch (err: any) {
      setIsProcessing(false);
      setStatusMsg(`Cleanup error: ${err.message}`);
    }
  };

  const handleSaveRegions = async () => {
    try {
      setIsSavingRegions(true);
      const savedRegions = await api.saveCleanupRegions(project.id, regions);
      onUpdateProject({ ...project, cleanup_regions: savedRegions });
      setStatusMsg('Cleanup region edits saved to this project.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setStatusMsg(`Could not save cleanup edits: ${message}`);
    } finally {
      setIsSavingRegions(false);
    }
  };

  const cleanupOperations: { id: CleanupRegion['type']; label: string }[] = [
    { id: 'inpaint', label: 'Spatial Delogo' },
    { id: 'blur', label: 'Blur Region' },
    { id: 'replace_logo', label: 'Replace with Text' },
    { id: 'add_text', label: 'Add Custom Text' },
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 select-none sm:space-y-6 sm:p-6 lg:p-8">
      {/* Top Banner */}
      <div className="flex flex-col gap-4 rounded-3xl border border-violet-500/20 bg-gradient-to-r from-violet-950/60 via-slate-900 to-[#0F1422] p-4 shadow-xl sm:p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 items-start gap-3.5">
          <div className="p-3 rounded-2xl bg-violet-600/20 text-violet-400 border border-violet-500/30">
            <Eraser className="w-6 h-6" />
          </div>
          <div>
            <h2 className="flex flex-wrap items-center gap-2 text-base font-bold text-white sm:text-lg">
              Authorized Video Region Editor
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-300">
                Non-Destructive
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Blur, overlay text, or apply FFmpeg's spatial delogo filter to authorized footage. The source file is never overwritten.
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-sky-500/20 bg-sky-500/5 px-4 py-3 text-xs text-sky-200/90">
          The remove operation uses FFmpeg's spatial delogo filter. It is not AI video inpainting and does not track moving overlays; inspect the preview before exporting.
        </div>
        {statusMsg && (
          <div role="status" className="rounded-xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-xs text-slate-200">
            {statusMsg}
          </div>
        )}

        {/* Action Button */}
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleSaveRegions}
            disabled={isSavingRegions || isProcessing}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-slate-700 bg-slate-900 text-slate-200 text-xs font-semibold hover:bg-slate-800 disabled:opacity-50"
          >
            {isSavingRegions ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            <span>Save Edits</span>
          </button>
          <button
            onClick={handleStartCleanup}
            disabled={isProcessing || !authConfirmed || regions.length === 0}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs tracking-wide shadow-lg shadow-violet-600/30 transition cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Processing Video...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Export Edited Video</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Cleaned Result Alert if ready */}
      {project.cleaned_video_url && (
        <div className="flex flex-col gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <h4 className="text-xs font-bold text-white">Cleaned Video Ready</h4>
              <p className="text-xs text-emerald-300/80">Saved as a separate high-resolution file.</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => onPreviewVideo(project.cleaned_video_url!, `${project.name} (Cleaned)`)}
              className="px-3.5 py-1.5 rounded-xl bg-slate-800 text-slate-200 text-xs font-semibold hover:bg-slate-700 transition"
            >
              Watch Video
            </button>
            <a
              href={project.cleaned_video_url}
              download
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition shadow"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download Cleaned MP4</span>
            </a>
          </div>
        </div>
      )}
      {regions.length === 0 && (
        <p className="rounded-xl border border-dashed border-slate-700 p-4 text-xs leading-relaxed text-slate-400">
          Add a region, then drag it over the authorized area you want to edit. No area is selected by default.
        </p>
      )}

      {/* Main Studio Viewport */}
      <div className="grid min-w-0 grid-cols-1 gap-5 lg:grid-cols-3 lg:gap-6">
        {/* Left: Video Canvas & Interactive Region Bounding Boxes */}
        <div className="min-w-0 space-y-4 lg:col-span-2">
          <div
            ref={containerRef}
            className="relative aspect-video rounded-3xl bg-black overflow-hidden border border-slate-800 shadow-2xl flex items-center justify-center group"
          >
            {/* Display either Video or Inpainted Preview Frame */}
            {previewMode === 'inpaint_preview' && previewFrameUrl ? (
              <img
                src={previewFrameUrl}
                alt="Edited Region Preview"
                className="w-full h-full object-contain"
              />
            ) : (
              <video
                ref={videoRef}
                src={project.video_url}
                playsInline
                onLoadStart={() => setVideoContentBounds(null)}
                onLoadedMetadata={() => setVideoContentBounds(getVideoContentBounds())}
                onTimeUpdate={handleTimeUpdate}
                onClick={togglePlay}
                className="w-full h-full object-contain cursor-pointer"
              />
            )}

            {/* Interactive Bounding Boxes Overlay */}
            {previewMode === 'original' && videoContentBounds &&
              regions.map((reg) => {
                const isActive = reg.id === activeRegionId;
                return (
                  <div
                    key={reg.id}
                    onClick={() => setActiveRegionId(reg.id)}
                    onPointerDown={(event) => {
                      event.stopPropagation();
                      setActiveRegionId(reg.id);
                      dragRef.current = {
                        id: reg.id,
                        pointerX: event.clientX,
                        pointerY: event.clientY,
                        originX: reg.x,
                        originY: reg.y,
                      };
                      event.currentTarget.setPointerCapture(event.pointerId);
                    }}
                    onPointerMove={(event) => {
                      const drag = dragRef.current;
                      const bounds = getVideoContentBounds();
                      if (!drag || drag.id !== reg.id || !bounds) return;
                      const x = Math.max(0, Math.min(100 - reg.width,
                        drag.originX + ((event.clientX - drag.pointerX) / bounds.width) * 100));
                      const y = Math.max(0, Math.min(100 - reg.height,
                        drag.originY + ((event.clientY - drag.pointerY) / bounds.height) * 100));
                      setRegions((previous) => previous.map((item) =>
                        item.id === reg.id ? { ...item, x, y } : item
                      ));
                    }}
                    onPointerUp={() => { dragRef.current = null; }}
                    onPointerCancel={() => { dragRef.current = null; }}
                    className={`absolute border-2 rounded cursor-move transition-all ${
                      isActive
                        ? 'border-violet-400 bg-violet-500/20 shadow-lg shadow-violet-500/30'
                        : 'border-cyan-400/70 bg-cyan-500/10 hover:border-cyan-400'
                    }`}
                    style={{
                      left: `${videoContentBounds.left + (reg.x / 100) * videoContentBounds.width}px`,
                      top: `${videoContentBounds.top + (reg.y / 100) * videoContentBounds.height}px`,
                      width: `${(reg.width / 100) * videoContentBounds.width}px`,
                      height: `${(reg.height / 100) * videoContentBounds.height}px`,
                      touchAction: 'none',
                    }}
                  >
                    <div className="absolute -top-6 left-0 px-2 py-0.5 rounded bg-black/80 text-[10px] font-bold text-white uppercase tracking-wider flex items-center gap-1">
                      <span>{reg.type}</span>
                    </div>
                  </div>
                );
              })}

            {/* Play/Pause Overlay */}
            {previewMode === 'original' && !isPlaying && (
              <button
                onClick={togglePlay}
                className="absolute inset-0 bg-black/30 flex items-center justify-center cursor-pointer"
              >
                <div className="w-14 h-14 rounded-full bg-violet-600/90 text-white flex items-center justify-center shadow-xl hover:scale-110 transition">
                  <Play className="w-6 h-6 ml-1 fill-current" />
                </div>
              </button>
            )}
          </div>

          {/* Player Bar & Before / After Toggle */}
          <div className="flex flex-col items-stretch justify-between gap-3 rounded-2xl border border-slate-800 bg-[#0F1422] p-3 sm:flex-row sm:items-center sm:gap-4 sm:p-4">
            <div className="flex items-center gap-3">
              <button
                onClick={togglePlay}
                className="p-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white transition cursor-pointer"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
              </button>

              <div className="text-xs font-mono text-slate-400">
                <span>{currentTime.toFixed(1)}s</span> / <span>{project.metadata.duration.toFixed(1)}s</span>
              </div>
            </div>

            {/* Before vs After Switcher */}
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setPreviewMode('original')}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer ${
                  previewMode === 'original'
                    ? 'bg-violet-600 text-white'
                    : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                Original View
              </button>
              <button
                onClick={handleFetchPreviewFrame}
                  disabled={isPreviewLoading || !regions.length || !authConfirmed}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer ${
                  previewMode === 'inpaint_preview'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                {isPreviewLoading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Eye className="w-3.5 h-3.5" />
                )}
                <span>Preview Region Edit</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right: Region Editor & Compliance Checklist */}
        <div className="space-y-5">
          {/* Defined Regions Selector */}
          <div className="p-5 rounded-3xl bg-[#0F1422] border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Layers className="w-4 h-4 text-violet-400" />
                Cleanup Regions ({regions.length})
              </h3>
              <button
                onClick={handleAddRegion}
                className="flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300 font-semibold cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Region</span>
              </button>
            </div>

            <div className="flex gap-2 overflow-x-auto pb-1">
              {regions.map((reg, i) => (
                <button
                  key={reg.id}
                  onClick={() => setActiveRegionId(reg.id)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition shrink-0 cursor-pointer ${
                    activeRegionId === reg.id
                      ? 'bg-violet-600 text-white'
                      : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  Region #{i + 1}
                </button>
              ))}
            </div>

            {/* Active Region Configuration */}
            {activeRegion && (
              <div className="space-y-4 pt-2 border-t border-slate-800">
                {/* Cleanup Operation Type */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">Operation</label>
                  <div className="grid grid-cols-2 gap-2">
                    {cleanupOperations.map((op) => (
                      <button
                        key={op.id}
                        onClick={() => handleUpdateActiveRegion({ type: op.id })}
                        className={`p-2 rounded-xl text-xs font-bold transition cursor-pointer text-center ${
                          activeRegion.type === op.id
                            ? 'bg-violet-500/20 text-violet-300 border border-violet-500/40'
                            : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
                        }`}
                      >
                        {op.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Spatial Sliders */}
                <div className="space-y-2.5 pt-1 text-xs">
                  <div>
                    <div className="flex justify-between text-slate-400 font-medium">
                      <span>Horizontal X</span>
                      <span className="font-mono text-white">{activeRegion.x}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max={Math.max(0, 100 - activeRegion.width)}
                      value={activeRegion.x}
                      onChange={(e) => handleUpdateActiveRegion({ x: Number(e.target.value) })}
                      className="w-full accent-violet-500"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-slate-400 font-medium">
                      <span>Vertical Y</span>
                      <span className="font-mono text-white">{activeRegion.y}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max={Math.max(0, 100 - activeRegion.height)}
                      value={activeRegion.y}
                      onChange={(e) => handleUpdateActiveRegion({ y: Number(e.target.value) })}
                      className="w-full accent-violet-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <div className="flex justify-between text-slate-400 font-medium">
                        <span>Width</span>
                        <span className="font-mono text-white">{activeRegion.width}%</span>
                      </div>
                      <input
                        type="range"
                        min="5"
                        max="80"
                        value={activeRegion.width}
                        onChange={(e) => handleUpdateActiveRegion({ width: Number(e.target.value) })}
                        className="w-full accent-violet-500"
                      />
                    </div>
                    <div>
                      <div className="flex justify-between text-slate-400 font-medium">
                        <span>Height</span>
                        <span className="font-mono text-white">{activeRegion.height}%</span>
                      </div>
                      <input
                        type="range"
                        min="5"
                        max="60"
                        value={activeRegion.height}
                        onChange={(e) => handleUpdateActiveRegion({ height: Number(e.target.value) })}
                        className="w-full accent-violet-500"
                      />
                    </div>
                  </div>
                </div>

                {/* Extra Options for Text/Logo */}
                {(activeRegion.type === 'add_text' || activeRegion.type === 'replace_logo') && (
                  <div className="space-y-1.5 pt-2">
                    <label className="text-xs font-semibold text-slate-300">Replacement Brand Text</label>
                    <input
                      type="text"
                      value={activeRegion.replacement_text || ''}
                      onChange={(e) => handleUpdateActiveRegion({ replacement_text: e.target.value })}
                      placeholder="e.g. My Brand Name"
                      className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-white"
                    />
                  </div>
                )}

                {activeRegion.type === 'blur' && (
                  <div className="space-y-1.5 pt-1">
                    <div className="flex justify-between text-xs text-slate-400 font-medium">
                      <span>Blur Strength</span>
                      <span className="font-mono text-white">{activeRegion.blur_strength}px</span>
                    </div>
                    <input
                      type="range"
                      min="5"
                      max="50"
                      value={activeRegion.blur_strength}
                      onChange={(e) => handleUpdateActiveRegion({ blur_strength: Number(e.target.value) })}
                      className="w-full accent-violet-500"
                    />
                  </div>
                )}

                {/* Delete button */}
                {(
                  <button
                    onClick={() => handleDeleteRegion(activeRegion.id)}
                    className="w-full py-2 rounded-xl text-xs font-semibold text-rose-400 hover:bg-rose-500/10 border border-rose-500/20 transition flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Delete This Region</span>
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Ownership & Authorization Confirmation Card */}
          <div className="p-5 rounded-3xl bg-amber-500/10 border border-amber-500/30 space-y-3">
            <div className="flex items-center gap-2 text-xs font-bold text-amber-300">
              <ShieldAlert className="w-4 h-4" />
              <span>Creator Authorization Policy</span>
            </div>
            <p className="text-[11px] text-amber-200/80 leading-relaxed">
              Edit only videos you own or have explicit permission to modify. Do not remove third-party ownership notices or attribution.
            </p>
            <label className="flex items-start gap-2.5 pt-1 cursor-pointer">
              <input
                type="checkbox"
                checked={authConfirmed}
                onChange={(e) => setAuthConfirmed(e.target.checked)}
                className="w-4 h-4 mt-0.5 accent-amber-500 shrink-0"
              />
              <span className="text-[11px] font-semibold text-white">
                I confirm that I own this video or have explicit permission to edit or remove these overlays.
              </span>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
};
