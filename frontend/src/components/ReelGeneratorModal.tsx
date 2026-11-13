import React, { useState } from 'react';
import { X, Sparkles, Clock, Sliders, Smartphone, Square, Monitor, Type, CheckCircle } from 'lucide-react';
import { GenerateReelsParams } from '../types';

interface ReelGeneratorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onGenerate: (params: GenerateReelsParams) => void;
  isGenerating: boolean;
  totalScenes: number;
}

export const ReelGeneratorModal: React.FC<ReelGeneratorModalProps> = ({
  isOpen,
  onClose,
  onGenerate,
  isGenerating,
  totalScenes,
}) => {
  const [durationMode, setDurationMode] = useState<number | 'custom'>(30);
  const [customDuration, setCustomDuration] = useState<number>(25);
  const [targetCount, setTargetCount] = useState<number>(5);
  const [aspectRatio, setAspectRatio] = useState<'9:16' | '16:9' | '1:1'>('9:16');
  const [mode, setMode] = useState<'smart_crop' | 'blur_bg' | 'fit'>('smart_crop');
  const [autoCaptions, setAutoCaptions] = useState<boolean>(true);
  const [captionLanguage, setCaptionLanguage] = useState<string>('en');
  const [captionStyle, setCaptionStyle] = useState<string>('bold_outline');

  if (!isOpen) return null;

  const actualDuration = durationMode === 'custom' ? customDuration : durationMode;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onGenerate({
      clip_duration: actualDuration,
      target_count: targetCount,
      aspect_ratio: aspectRatio,
      mode: mode,
      auto_captions: autoCaptions,
      caption_language: captionLanguage,
      caption_style: captionStyle,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-xl bg-[#0F1422] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-violet-500/10 text-violet-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Generate Viral Reels</h3>
              <p className="text-xs text-slate-400 font-medium">Automatic multi-clip extraction with smart timing</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-6">
          {/* Target Reel Duration */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-violet-400" />
              Reel Duration
            </label>
            <div className="grid grid-cols-5 gap-2">
              {[15, 30, 45, 60].map((dur) => (
                <button
                  type="button"
                  key={dur}
                  onClick={() => setDurationMode(dur)}
                  className={`py-2 px-3 rounded-xl text-xs font-bold transition cursor-pointer ${
                    durationMode === dur
                      ? 'bg-violet-600 text-white shadow-md shadow-violet-600/30'
                      : 'bg-slate-900 border border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  {dur}s
                </button>
              ))}
              <button
                type="button"
                onClick={() => setDurationMode('custom')}
                className={`py-2 px-3 rounded-xl text-xs font-bold transition cursor-pointer ${
                  durationMode === 'custom'
                    ? 'bg-violet-600 text-white shadow-md shadow-violet-600/30'
                    : 'bg-slate-900 border border-slate-800 text-slate-300 hover:border-slate-700'
                }`}
              >
                Custom
              </button>
            </div>

            {durationMode === 'custom' && (
              <div className="pt-2 flex items-center gap-4 p-3 rounded-xl bg-slate-900 border border-slate-800">
                <input
                  type="range"
                  min="5"
                  max="120"
                  value={customDuration}
                  onChange={(e) => setCustomDuration(Number(e.target.value))}
                  className="flex-1 accent-violet-500"
                />
                <span className="text-xs font-mono font-bold text-violet-400 w-12 text-right">
                  {customDuration}s
                </span>
              </div>
            )}
          </div>

          {/* Target Clip Count */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-semibold">
              <span className="text-slate-300 flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-indigo-400" />
                Number of Reels to Generate
              </span>
              <span className="text-violet-400 font-mono font-bold">{targetCount} clips</span>
            </div>
            <input
              type="range"
              min="1"
              max={Math.max(10, Math.min(25, totalScenes))}
              value={targetCount}
              onChange={(e) => setTargetCount(Number(e.target.value))}
              className="w-full accent-violet-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-400">
              AI will rank top {targetCount} candidate moments from {totalScenes} detected scenes.
            </p>
          </div>

          {/* Aspect Ratio */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300">Aspect Ratio</label>
            <div className="grid grid-cols-3 gap-3">
              <button
                type="button"
                onClick={() => setAspectRatio('9:16')}
                className={`p-3 rounded-xl border text-left transition cursor-pointer flex items-center gap-3 ${
                  aspectRatio === '9:16'
                    ? 'border-violet-500 bg-violet-500/10 text-white'
                    : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-white'
                }`}
              >
                <Smartphone className="w-5 h-5 text-violet-400 shrink-0" />
                <div>
                  <p className="text-xs font-bold">9:16 Vertical</p>
                  <p className="text-[10px] text-slate-400">Reels / Shorts / TikTok</p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setAspectRatio('1:1')}
                className={`p-3 rounded-xl border text-left transition cursor-pointer flex items-center gap-3 ${
                  aspectRatio === '1:1'
                    ? 'border-violet-500 bg-violet-500/10 text-white'
                    : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-white'
                }`}
              >
                <Square className="w-5 h-5 text-indigo-400 shrink-0" />
                <div>
                  <p className="text-xs font-bold">1:1 Square</p>
                  <p className="text-[10px] text-slate-400">Feed / LinkedIn</p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setAspectRatio('16:9')}
                className={`p-3 rounded-xl border text-left transition cursor-pointer flex items-center gap-3 ${
                  aspectRatio === '16:9'
                    ? 'border-violet-500 bg-violet-500/10 text-white'
                    : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-white'
                }`}
              >
                <Monitor className="w-5 h-5 text-cyan-400 shrink-0" />
                <div>
                  <p className="text-xs font-bold">16:9 Landscape</p>
                  <p className="text-[10px] text-slate-400">Standard YouTube</p>
                </div>
              </button>
            </div>
          </div>

          {/* Framing / Crop Mode */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300">Framing & Background</label>
            <div className="grid grid-cols-3 gap-3">
              {[
                { id: 'smart_crop', label: 'Smart Crop', desc: 'Center subject crop' },
                { id: 'blur_bg', label: 'Blurred Stack', desc: 'Blurred background' },
                { id: 'fit', label: 'Fit Box', desc: 'Clean letterboxing' },
              ].map((item) => (
                <button
                  type="button"
                  key={item.id}
                  onClick={() => setMode(item.id as any)}
                  className={`p-3 rounded-xl border text-left transition cursor-pointer ${
                    mode === item.id
                      ? 'border-violet-500 bg-violet-500/10 text-white'
                      : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-white'
                  }`}
                >
                  <p className="text-xs font-bold">{item.label}</p>
                  <p className="text-[10px] text-slate-400">{item.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Automatic Captions & Language */}
          <div className="space-y-3 p-4 rounded-xl bg-slate-900/60 border border-slate-800">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Type className="w-4 h-4 text-violet-400" />
                <span className="text-xs font-bold text-white">Generate Synchronized Captions</span>
              </div>
              <input
                type="checkbox"
                checked={autoCaptions}
                onChange={(e) => setAutoCaptions(e.target.checked)}
                className="w-4 h-4 accent-violet-500 cursor-pointer"
              />
            </div>

            {autoCaptions && (
              <div className="grid grid-cols-2 gap-3 pt-2">
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-400">Language</label>
                  <select
                    value={captionLanguage}
                    onChange={(e) => setCaptionLanguage(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white focus:outline-none focus:border-violet-500"
                  >
                    <option value="en">English (Viral)</option>
                    <option value="hi">Hindi (हिंदी)</option>
                    <option value="hinglish">Hinglish (Mix)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-400">Caption Style</label>
                  <select
                    value={captionStyle}
                    onChange={(e) => setCaptionStyle(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white focus:outline-none focus:border-violet-500"
                  >
                    <option value="bold_outline">Bold Outline (Hormozi / Beast)</option>
                    <option value="clean_pill">Clean Dark Pill</option>
                    <option value="karaoke">Karaoke Highlight</option>
                    <option value="classic">Classic Minimal</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          {/* Modal Footer */}
          <div className="pt-2 flex items-center justify-between border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              disabled={isGenerating}
              className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isGenerating}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs tracking-wide shadow-lg shadow-violet-600/30 transition cursor-pointer disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{isGenerating ? 'Generating Reels...' : `Generate ${targetCount} Short Clips`}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
