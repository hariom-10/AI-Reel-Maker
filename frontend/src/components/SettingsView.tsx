import React, { useState } from 'react';
import { Settings, Cpu, HardDrive, Sparkles, CheckCircle2, ShieldCheck, RefreshCw, Folder } from 'lucide-react';

export const SettingsView: React.FC = () => {
  const [cleared, setCleared] = useState(false);

  const handleClearCache = () => {
    setCleared(true);
    setTimeout(() => setCleared(false), 3000);
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Settings className="w-5 h-5 text-violet-400" />
          System Settings & Performance
        </h2>
        <p className="text-xs text-slate-400">
          Configure local video processing, hardware acceleration, and AI models.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Hardware & FFmpeg Engine */}
        <div className="p-6 rounded-2xl bg-[#0F1422] border border-slate-800 space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">FFmpeg Video Engine</h3>
              <p className="text-xs text-slate-400">FFmpeg 8.1 full build (gyan.dev)</p>
            </div>
          </div>

          <div className="space-y-2.5 text-xs text-slate-300">
            <div className="flex justify-between py-1.5 border-b border-slate-800/80">
              <span className="text-slate-400">Hardware Accel:</span>
              <span className="flex items-center gap-1 text-right font-semibold text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" /> D3D11 / NVENC / OpenCL
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/80">
              <span className="text-slate-400">Video Codec:</span>
              <span className="break-words text-right font-mono text-white">libx264 (H.264 High Profile)</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/80">
              <span className="text-slate-400">Audio Codec:</span>
              <span className="break-words text-right font-mono text-white">AAC Stereo 192 kbps 48kHz</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/80">
              <span className="text-slate-400">Subtitles Engine:</span>
              <span className="break-words text-right font-mono text-white">libass + FreeType + HarfBuzz</span>
            </div>
          </div>
        </div>

        {/* AI Models & Speech Engine */}
        <div className="p-6 rounded-2xl bg-[#0F1422] border border-slate-800 space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-violet-500/10 text-violet-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">AI Scene & Speech Pipeline</h3>
              <p className="text-xs text-slate-400">Multi-modal visual & acoustic heuristics</p>
            </div>
          </div>

          <div className="space-y-2.5 text-xs text-slate-300">
            <div className="flex justify-between py-1.5 border-b border-slate-800/80">
              <span className="text-slate-400">Scene Detector:</span>
              <span className="flex items-center gap-1 text-right font-semibold text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" /> FFmpeg Native + ContentDetector
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/80">
              <span className="text-slate-400">Audio Activity Engine:</span>
              <span className="break-words text-right font-mono text-white">Acoustic Silence & Peak Meter</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/80">
              <span className="text-slate-400">Speech Transcription:</span>
              <span className="break-words text-right font-mono text-white">Whisper Local + Smart Aligner</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/80">
              <span className="text-slate-400">Supported Languages:</span>
              <span className="break-words text-right font-mono text-white">English, Hindi, Hinglish</span>
            </div>
          </div>
        </div>

        {/* Local Storage & Cache */}
        <div className="p-4 sm:p-6 rounded-2xl bg-[#0F1422] border border-slate-800 space-y-4 md:col-span-2">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-400">
                <HardDrive className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Local Workspace & Data Storage</h3>
                <p className="text-xs text-slate-400">Stored safely on local laptop disk (no cloud uploads)</p>
              </div>
            </div>

            <button
              onClick={handleClearCache}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 transition cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
              <span>{cleared ? 'Cache Cleaned!' : 'Clean Temp Cache'}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Uploads Directory</span>
              <p className="text-xs font-mono text-slate-200 truncate">backend/data/uploads/</p>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Exports Directory</span>
              <p className="text-xs font-mono text-slate-200 truncate">backend/data/exports/</p>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Projects Metadata</span>
              <p className="text-xs font-mono text-slate-200 truncate">backend/data/projects/</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
