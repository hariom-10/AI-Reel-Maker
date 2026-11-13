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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-[#0F1422] border border-slate-800 rounded-3xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-slate-800 flex items-center justify-between">
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
            className="max-h-[70vh] rounded-2xl object-contain shadow-2xl"
          />
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-800 bg-[#0B0F17] flex items-center justify-between">
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
