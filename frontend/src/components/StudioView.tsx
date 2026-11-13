import React, { useState, useRef, useEffect } from 'react';
import {
  Play, Pause, Crop, Type, Scissors, ShieldAlert, Sparkles, Download, Check,
  Smartphone, Square, Monitor, Palette, ArrowLeft, RefreshCw, Loader2, Eye
} from 'lucide-react';
import { Project, ClipConfig, SubtitleItem } from '../types';
import { api } from '../services/api';

interface StudioViewProps {
  project: Project;
  onUpdateProject: (project: Project) => void;
  onOpenBatchExport: () => void;
  onBackToScenes: () => void;
}

export const StudioView: React.FC<StudioViewProps> = ({
  project,
  onUpdateProject,
  onOpenBatchExport,
  onBackToScenes,
}) => {
  const [activeClipIndex, setActiveClipIndex] = useState(0);
  const [activeTab, setActiveTab] = useState<'framing' | 'captions' | 'trim' | 'privacy'>('framing');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isRendering, setIsRendering] = useState(false);
  const [renderMessage, setRenderMessage] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const bgVideoRef = useRef<HTMLVideoElement>(null);

  const clips = project.clips || [];
  const currentClip = clips[activeClipIndex];

  // Keep playback within clip boundaries
  useEffect(() => {
    if (currentClip && videoRef.current) {
      videoRef.current.currentTime = currentClip.start_time;
      setCurrentTime(currentClip.start_time);
      if (bgVideoRef.current) {
        bgVideoRef.current.currentTime = currentClip.start_time;
      }
    }
  }, [activeClipIndex, currentClip?.start_time]);

  const handleTimeUpdate = () => {
    if (!videoRef.current || !currentClip) return;
    const time = videoRef.current.currentTime;
    setCurrentTime(time);

    // Sync background video if present
    if (bgVideoRef.current && Math.abs(bgVideoRef.current.currentTime - time) > 0.3) {
      bgVideoRef.current.currentTime = time;
    }

    // Loop clip
    if (time >= currentClip.end_time) {
      videoRef.current.currentTime = currentClip.start_time;
      if (bgVideoRef.current) bgVideoRef.current.currentTime = currentClip.start_time;
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      if (bgVideoRef.current) bgVideoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play();
      if (bgVideoRef.current) bgVideoRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleUpdateClip = async (updated: ClipConfig) => {
    const updatedClips = [...clips];
    updatedClips[activeClipIndex] = updated;
    const updatedProject = { ...project, clips: updatedClips };
    onUpdateProject(updatedProject);

    try {
      await api.updateClip(project.id, updated.clip_id, updated);
    } catch (e) {
      console.error('Failed to sync clip update to backend:', e);
    }
  };

  const handleRenderSingleClip = async () => {
    if (!currentClip) return;
    try {
      setIsRendering(true);
      setRenderMessage('Rendering high-quality vertical MP4 with FFmpeg...');
      const rendered = await api.renderClip(project.id, currentClip.clip_id);
      
      const updatedClips = [...clips];
      updatedClips[activeClipIndex] = rendered;
      onUpdateProject({ ...project, clips: updatedClips });

      setIsRendering(false);
      setRenderMessage('Reel rendered successfully! Ready to preview or download.');
      setTimeout(() => setRenderMessage(null), 4000);
    } catch (e: any) {
      setIsRendering(false);
      setRenderMessage(`Render failed: ${e.message}`);
    }
  };

  // Find active subtitle for current video timestamp
  const getActiveSubtitle = (): string => {
    if (!currentClip || !currentClip.caption_config.enabled) return '';
    const activeSub = currentClip.subtitles.find(
      (sub) => currentTime >= sub.start_time && currentTime <= sub.end_time
    );
    return activeSub ? activeSub.text : '';
  };

  if (!currentClip) {
    return (
      <div className="p-12 text-center text-slate-400">
        <p>No clips generated yet.</p>
        <button onClick={onBackToScenes} className="mt-4 px-4 py-2 bg-violet-600 text-white rounded-xl">
          Back to Scene Detection
        </button>
      </div>
    );
  }

  const crop = currentClip.crop_config;
  const captions = currentClip.caption_config;
  const activeSubText = getActiveSubtitle();

  // Dynamic subtitle CSS styles
  const getSubtitleStyles = (): React.CSSProperties => {
    const styles: React.CSSProperties = {
      fontFamily: captions.font_family || 'Impact, sans-serif',
      fontSize: `${captions.font_size}px`,
      color: captions.text_color || '#FFD700',
    };

    if (captions.style === 'bold_outline') {
      styles.textTransform = 'uppercase';
      styles.textShadow = '3px 3px 0 #000, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 0 4px 10px rgba(0,0,0,0.8)';
    } else if (captions.style === 'clean_pill') {
      styles.backgroundColor = `rgba(0, 0, 0, ${captions.bg_opacity})`;
      styles.padding = '6px 14px';
      styles.borderRadius = '9999px';
    }

    return styles;
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-[#090D16] overflow-hidden select-none">
      {/* Top Studio Bar */}
      <div className="px-6 py-3 border-b border-slate-800/80 bg-[#0D121F] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onBackToScenes}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Moments</span>
          </button>

          {/* Clip Selector Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto max-w-xl py-1">
            {clips.map((clip, idx) => (
              <button
                key={clip.clip_id}
                onClick={() => setActiveClipIndex(idx)}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition shrink-0 cursor-pointer ${
                  activeClipIndex === idx
                    ? 'bg-violet-600 text-white shadow-md shadow-violet-600/30'
                    : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                Reel #{idx + 1} ({clip.duration}s)
              </button>
            ))}
          </div>
        </div>

        {/* Studio Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleRenderSingleClip}
            disabled={isRendering}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs tracking-wide border border-slate-700 transition cursor-pointer disabled:opacity-50"
          >
            {isRendering ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-violet-400" />
                <span>Rendering...</span>
              </>
            ) : currentClip.status === 'exported' ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span>Re-Render Reel</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 text-violet-400 fill-violet-400" />
                <span>Render This Reel</span>
              </>
            )}
          </button>

          <button
            onClick={onOpenBatchExport}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs tracking-wide shadow-md shadow-violet-600/30 transition cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Batch Export All</span>
          </button>
        </div>
      </div>

      {/* Render Alert Notification */}
      {renderMessage && (
        <div className="px-6 py-2 bg-indigo-950/80 border-b border-indigo-500/30 text-indigo-300 text-xs flex items-center justify-between">
          <span>{renderMessage}</span>
          {currentClip.output_url && (
            <a
              href={currentClip.output_url}
              download
              className="text-violet-400 underline font-semibold ml-4 hover:text-violet-300"
            >
              Download MP4
            </a>
          )}
        </div>
      )}

      {/* Main Workspace: Left Mockup Player + Right Settings Panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Interactive Phone Canvas */}
        <div className="flex-1 flex flex-col items-center justify-center p-6 relative bg-gradient-to-b from-slate-950 to-[#0A0E17] overflow-hidden">
          {/* Smartphone Mockup */}
          <div
            className={`relative rounded-[36px] p-3.5 bg-slate-900 border-4 border-slate-700 shadow-2xl shadow-black/80 flex flex-col items-center justify-center transition-all ${
              crop.aspect_ratio === '9:16'
                ? 'w-[320px] h-[570px]'
                : crop.aspect_ratio === '1:1'
                ? 'w-[420px] h-[420px]'
                : 'w-[560px] h-[315px]'
            }`}
          >
            {/* Phone Notch */}
            {crop.aspect_ratio === '9:16' && (
              <div className="absolute top-5 z-30 w-24 h-4 bg-slate-900 rounded-full flex items-center justify-center">
                <div className="w-2.5 h-2.5 rounded-full bg-slate-800" />
              </div>
            )}

            {/* Video Viewport */}
            <div className="w-full h-full rounded-[26px] overflow-hidden relative bg-black flex items-center justify-center">
              {/* Blurred Background Video Layer if active */}
              {crop.mode === 'blur_bg' && (
                <video
                  ref={bgVideoRef}
                  src={project.video_url}
                  muted
                  playsInline
                  className="absolute inset-0 w-full h-full object-cover filter blur-lg brightness-75 scale-110 pointer-events-none"
                />
              )}

              {/* Primary Video Layer */}
              <video
                ref={videoRef}
                src={project.video_url}
                playsInline
                onTimeUpdate={handleTimeUpdate}
                onClick={togglePlay}
                className={`relative z-10 w-full h-full cursor-pointer ${
                  crop.mode === 'smart_crop'
                    ? 'object-cover'
                    : 'object-contain'
                }`}
                style={{
                  objectPosition: `${crop.center_x_percent}% center`,
                }}
              />

              {/* Personal Blur Mask Region if enabled */}
              {crop.blur_region && crop.blur_region.width > 0 && (
                <div
                  className="absolute z-20 backdrop-blur-md bg-white/10 border border-dashed border-red-500/50 pointer-events-none rounded-md"
                  style={{
                    left: `${crop.blur_region.x}%`,
                    top: `${crop.blur_region.y}%`,
                    width: `${crop.blur_region.width}%`,
                    height: `${crop.blur_region.height}%`,
                  }}
                >
                  <span className="text-[9px] font-bold text-red-400 bg-black/60 px-1 rounded">Private Mask</span>
                </div>
              )}

              {/* Live Styled Subtitle Overlay */}
              {captions.enabled && activeSubText && (
                <div
                  className={`absolute z-20 w-full px-6 text-center pointer-events-none transition-all duration-100 ${
                    captions.position === 'top'
                      ? 'top-10'
                      : captions.position === 'center'
                      ? 'top-1/2 -translate-y-1/2'
                      : 'bottom-16'
                  }`}
                  style={{
                    ...(captions.position === 'custom' ? { top: `${captions.y_percent}%` } : {}),
                  }}
                >
                  <span style={getSubtitleStyles()} className="inline-block leading-tight font-black tracking-wide">
                    {activeSubText}
                  </span>
                </div>
              )}

              {/* Play / Pause Center Overlay */}
              {!isPlaying && (
                <div
                  onClick={togglePlay}
                  className="absolute z-30 inset-0 bg-black/30 flex items-center justify-center cursor-pointer"
                >
                  <div className="w-14 h-14 rounded-full bg-violet-600/90 text-white flex items-center justify-center shadow-xl hover:scale-110 transition">
                    <Play className="w-6 h-6 ml-1 fill-current" />
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Bottom Live Scrubber Bar */}
          <div className="w-full max-w-xl mt-6 p-4 rounded-2xl bg-[#0F1422] border border-slate-800 flex items-center gap-4">
            <button
              onClick={togglePlay}
              className="p-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white transition cursor-pointer"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
            </button>

            <div className="flex-1 space-y-1">
              <input
                type="range"
                min={currentClip.start_time}
                max={currentClip.end_time}
                step="0.05"
                value={currentTime}
                onChange={(e) => {
                  const t = Number(e.target.value);
                  if (videoRef.current) videoRef.current.currentTime = t;
                  if (bgVideoRef.current) bgVideoRef.current.currentTime = t;
                  setCurrentTime(t);
                }}
                className="w-full accent-violet-500 cursor-pointer"
              />
              <div className="flex justify-between text-[11px] font-mono text-slate-400">
                <span>{currentTime.toFixed(1)}s</span>
                <span>Clip: {currentClip.duration}s</span>
                <span>End: {currentClip.end_time.toFixed(1)}s</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Configuration Inspector Panel */}
        <div className="w-96 border-l border-slate-800/80 bg-[#0D121F] flex flex-col h-full overflow-hidden">
          {/* Tab Navigation */}
          <div className="flex border-b border-slate-800 px-3 pt-3 gap-1 shrink-0">
            {[
              { id: 'framing', label: 'Framing', icon: Crop },
              { id: 'captions', label: 'Captions', icon: Type },
              { id: 'trim', label: 'Trimming', icon: Scissors },
              { id: 'privacy', label: 'Masking', icon: ShieldAlert },
            ].map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex-1 pb-3 text-xs font-bold flex items-center justify-center gap-1.5 transition cursor-pointer border-b-2 ${
                    activeTab === tab.id
                      ? 'border-violet-500 text-violet-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Tab Content */}
          <div className="flex-1 p-5 overflow-y-auto space-y-6">
            {/* 1. FRAMING TAB */}
            {activeTab === 'framing' && (
              <div className="space-y-5">
                {/* Aspect Ratio */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-300">Format Ratio</label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { id: '9:16', label: '9:16', icon: Smartphone },
                      { id: '1:1', label: '1:1', icon: Square },
                      { id: '16:9', label: '16:9', icon: Monitor },
                    ].map((item) => (
                      <button
                        key={item.id}
                        onClick={() =>
                          handleUpdateClip({
                            ...currentClip,
                            crop_config: { ...crop, aspect_ratio: item.id as any },
                          })
                        }
                        className={`p-2.5 rounded-xl border text-xs font-bold flex flex-col items-center gap-1 transition cursor-pointer ${
                          crop.aspect_ratio === item.id
                            ? 'border-violet-500 bg-violet-500/10 text-white'
                            : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-white'
                        }`}
                      >
                        <item.icon className="w-4 h-4" />
                        <span>{item.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Framing Mode */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-300">Composition Mode</label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { id: 'smart_crop', label: 'Smart Crop' },
                      { id: 'blur_bg', label: 'Blur Stack' },
                      { id: 'fit', label: 'Letterbox' },
                    ].map((m) => (
                      <button
                        key={m.id}
                        onClick={() =>
                          handleUpdateClip({
                            ...currentClip,
                            crop_config: { ...crop, mode: m.id as any },
                          })
                        }
                        className={`p-2 rounded-xl border text-xs font-bold transition cursor-pointer text-center ${
                          crop.mode === m.id
                            ? 'border-violet-500 bg-violet-500/10 text-white'
                            : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-white'
                        }`}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Center X Slider for Manual Framing */}
                {crop.mode === 'smart_crop' && (
                  <div className="space-y-2 p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
                    <div className="flex justify-between text-xs font-semibold">
                      <span className="text-slate-300">Horizontal Pan / Center X</span>
                      <span className="text-violet-400 font-mono">{Math.round(crop.center_x_percent)}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={crop.center_x_percent}
                      onChange={(e) =>
                        handleUpdateClip({
                          ...currentClip,
                          crop_config: { ...crop, center_x_percent: Number(e.target.value) },
                        })
                      }
                      className="w-full accent-violet-500 cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-slate-400">
                      <span>Left Subject</span>
                      <span>Center</span>
                      <span>Right Subject</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 2. CAPTIONS TAB */}
            {activeTab === 'captions' && (
              <div className="space-y-5">
                {/* Enable Subtitles Toggle */}
                <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
                  <span className="text-xs font-semibold text-white">Enable Subtitles</span>
                  <input
                    type="checkbox"
                    checked={captions.enabled}
                    onChange={(e) =>
                      handleUpdateClip({
                        ...currentClip,
                        caption_config: { ...captions, enabled: e.target.checked },
                      })
                    }
                    className="w-4 h-4 accent-violet-500 cursor-pointer"
                  />
                </div>

                {captions.enabled && (
                  <>
                    {/* Font Family & Size */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <label className="text-[11px] font-semibold text-slate-400">Font</label>
                        <select
                          value={captions.font_family}
                          onChange={(e) =>
                            handleUpdateClip({
                              ...currentClip,
                              caption_config: { ...captions, font_family: e.target.value },
                            })
                          }
                          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white"
                        >
                          <option value="Impact">Impact (Viral)</option>
                          <option value="Montserrat">Montserrat</option>
                          <option value="Arial">Arial Bold</option>
                          <option value="Roboto">Roboto</option>
                        </select>
                      </div>

                      <div className="space-y-1">
                        <label className="text-[11px] font-semibold text-slate-400">
                          Size: {captions.font_size}px
                        </label>
                        <input
                          type="range"
                          min="16"
                          max="44"
                          value={captions.font_size}
                          onChange={(e) =>
                            handleUpdateClip({
                              ...currentClip,
                              caption_config: { ...captions, font_size: Number(e.target.value) },
                            })
                          }
                          className="w-full accent-violet-500 mt-2"
                        />
                      </div>
                    </div>

                    {/* Color Presets */}
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold text-slate-400">Text Color</label>
                      <div className="flex items-center gap-2">
                        {['#FFD700', '#FFFFFF', '#00F0FF', '#00FF66', '#FF007F'].map((c) => (
                          <button
                            key={c}
                            onClick={() =>
                              handleUpdateClip({
                                ...currentClip,
                                caption_config: { ...captions, text_color: c },
                              })
                            }
                            className={`w-7 h-7 rounded-full border-2 transition cursor-pointer ${
                              captions.text_color === c ? 'border-white scale-110 shadow-md' : 'border-transparent'
                            }`}
                            style={{ backgroundColor: c }}
                          />
                        ))}
                      </div>
                    </div>

                    {/* Vertical Placement */}
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold text-slate-400">Position</label>
                      <div className="grid grid-cols-3 gap-2">
                        {['bottom', 'center', 'top'].map((pos) => (
                          <button
                            key={pos}
                            onClick={() =>
                              handleUpdateClip({
                                ...currentClip,
                                caption_config: { ...captions, position: pos },
                              })
                            }
                            className={`py-1.5 rounded-lg border text-xs font-semibold capitalize transition cursor-pointer ${
                              captions.position === pos
                                ? 'border-violet-500 bg-violet-500/10 text-white'
                                : 'border-slate-800 bg-slate-900 text-slate-400'
                            }`}
                          >
                            {pos}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Subtitle Dialogue Items Inline Editor */}
                    <div className="space-y-2 pt-2 border-t border-slate-800">
                      <label className="text-xs font-semibold text-slate-300">Edit Caption Lines</label>
                      <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                        {currentClip.subtitles.map((sub, i) => (
                          <div key={sub.id} className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5">
                            <div className="flex justify-between text-[10px] font-mono text-slate-400">
                              <span>#{i + 1}</span>
                              <span>{sub.start_time}s - {sub.end_time}s</span>
                            </div>
                            <input
                              type="text"
                              value={sub.text}
                              onChange={(e) => {
                                const newSubs = [...currentClip.subtitles];
                                newSubs[i] = { ...sub, text: e.target.value };
                                handleUpdateClip({ ...currentClip, subtitles: newSubs });
                              }}
                              className="w-full px-2.5 py-1.5 rounded-lg bg-black/60 border border-slate-800 text-xs text-white"
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* 3. TRIMMING TAB */}
            {activeTab === 'trim' && (
              <div className="space-y-5">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-300">Reel Title</label>
                  <input
                    type="text"
                    value={currentClip.title}
                    onChange={(e) => handleUpdateClip({ ...currentClip, title: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-white"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400">Start Time (sec)</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max={currentClip.end_time - 1}
                      value={currentClip.start_time}
                      onChange={(e) => {
                        const start = Number(e.target.value);
                        handleUpdateClip({
                          ...currentClip,
                          start_time: start,
                          duration: round(currentClip.end_time - start, 2),
                        });
                      }}
                      className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-white font-mono"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400">End Time (sec)</label>
                    <input
                      type="number"
                      step="0.1"
                      min={currentClip.start_time + 1}
                      max={project.metadata.duration}
                      value={currentClip.end_time}
                      onChange={(e) => {
                        const end = Number(e.target.value);
                        handleUpdateClip({
                          ...currentClip,
                          end_time: end,
                          duration: round(end - currentClip.start_time, 2),
                        });
                      }}
                      className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-white font-mono"
                    />
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-violet-500/10 border border-violet-500/20 text-xs text-violet-300 space-y-1">
                  <div className="flex justify-between font-bold">
                    <span>Viral Quality Score</span>
                    <span>{Math.round(currentClip.score * 100)}%</span>
                  </div>
                  <p className="text-[11px] text-violet-400/80">
                    High engagement probability based on dialogue presence and pacing.
                  </p>
                </div>
              </div>
            )}

            {/* 4. PRIVACY MASKING TAB */}
            {activeTab === 'privacy' && (
              <div className="space-y-4">
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 space-y-1">
                  <p className="font-bold text-white">Creator Privacy Mask</p>
                  <p className="text-slate-400 text-[11px]">
                    Blur sensitive personal regions (e.g. personal contact numbers, private dates, or own license plates) in your footage.
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-300">Enable Region Blur</span>
                    <input
                      type="checkbox"
                      checked={!!crop.blur_region && crop.blur_region.width > 0}
                      onChange={(e) => {
                        if (e.target.checked) {
                          handleUpdateClip({
                            ...currentClip,
                            crop_config: {
                              ...crop,
                              blur_region: { x: 30, y: 30, width: 40, height: 20 },
                            },
                          });
                        } else {
                          handleUpdateClip({
                            ...currentClip,
                            crop_config: { ...crop, blur_region: undefined },
                          });
                        }
                      }}
                      className="w-4 h-4 accent-violet-500 cursor-pointer"
                    />
                  </div>

                  {crop.blur_region && crop.blur_region.width > 0 && (
                    <div className="space-y-3 pt-2 text-xs">
                      <div>
                        <label className="text-[11px] text-slate-400">Position X: {crop.blur_region.x}%</label>
                        <input
                          type="range"
                          min="0"
                          max="80"
                          value={crop.blur_region.x}
                          onChange={(e) =>
                            handleUpdateClip({
                              ...currentClip,
                              crop_config: {
                                ...crop,
                                blur_region: { ...crop.blur_region!, x: Number(e.target.value) },
                              },
                            })
                          }
                          className="w-full accent-violet-500"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400">Position Y: {crop.blur_region.y}%</label>
                        <input
                          type="range"
                          min="0"
                          max="80"
                          value={crop.blur_region.y}
                          onChange={(e) =>
                            handleUpdateClip({
                              ...currentClip,
                              crop_config: {
                                ...crop,
                                blur_region: { ...crop.blur_region!, y: Number(e.target.value) },
                              },
                            })
                          }
                          className="w-full accent-violet-500"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400">Width: {crop.blur_region.width}%</label>
                        <input
                          type="range"
                          min="10"
                          max="80"
                          value={crop.blur_region.width}
                          onChange={(e) =>
                            handleUpdateClip({
                              ...currentClip,
                              crop_config: {
                                ...crop,
                                blur_region: { ...crop.blur_region!, width: Number(e.target.value) },
                              },
                            })
                          }
                          className="w-full accent-violet-500"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

function round(val: number, decimals: number): number {
  return Number(val.toFixed(decimals));
}
