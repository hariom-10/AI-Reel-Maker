import React from 'react';
import { X, Download, Film } from 'lucide-react';

interface VideoPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  videoUrl: string | null;
  title: string;
}

export const VideoPreviewModal: React.FC<VideoPreviewModalProps> = ({
  isOpen,
  onClose,
  videoUrl,
  title,
}) => {
  if (!isOpen || !videoUrl) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur-md animate-in fade-in duration-200 sm:p-4">
      <div className="flex max-h-[calc(100dvh-1rem)] w-full max-w-lg flex-col overflow-hidden rounded-3xl border border-slate-800 bg-[#0F1422] shadow-2xl sm:max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3.5 sm:px-5">
          <div className="flex items-center gap-2 truncate">
            <Film className="w-4 h-4 text-violet-400 shrink-0" />
            <h3 className="text-xs font-bold text-white truncate">{title}</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Player Viewport */}
        <div className="bg-black flex items-center justify-center p-2">
          <video
            src={videoUrl}
            controls
            autoPlay
            loop
            className="h-auto max-h-[65dvh] w-full rounded-2xl object-contain shadow-2xl sm:max-h-[70vh]"
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 border-t border-slate-800 bg-[#0B0F17] px-4 py-3 sm:px-5">
          <span className="text-[11px] text-slate-400">High Definition 1080x1920 MP4</span>
          <a
            href={videoUrl}
            download
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs tracking-wide shadow-md transition"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download Reel</span>
          </a>
        </div>
      </div>
    </div>
  );
};
