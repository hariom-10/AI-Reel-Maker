import React, { useState } from 'react';
import { Library, Film, Download, Play, Video, Eye } from 'lucide-react';
import { Project, ClipConfig } from '../types';

interface VideoLibraryViewProps {
  projects: Project[];
  onPreviewVideo: (url: string, title: string) => void;
}

export const VideoLibraryView: React.FC<VideoLibraryViewProps> = ({ projects, onPreviewVideo }) => {
  const [filter, setFilter] = useState<'all' | 'sources' | 'reels'>('all');

  // Collect all source videos
  const sources = projects.map((p) => ({
    id: `src_${p.id}`,
    title: p.name,
    type: 'source' as const,
    url: p.video_url,
    duration: p.metadata.duration,
    resolution: `${p.metadata.width}x${p.metadata.height}`,
    createdAt: p.created_at,
    thumbnail: p.scenes?.[0]?.thumbnail_url,
  }));

  // Collect all exported reels
  const reels: any[] = [];
  projects.forEach((p) => {
    p.clips?.forEach((c) => {
      if (c.output_url) {
        reels.push({
          id: `reel_${c.clip_id}`,
          title: `${p.name} - ${c.title}`,
          type: 'reel' as const,
          url: c.output_url,
          duration: c.duration,
          resolution: '1080x1920 (9:16)',
          createdAt: p.updated_at,
          thumbnail: c.thumbnail_url,
        });
      }
    });
  });

  const allItems = [...sources, ...reels];
  const filtered =
    filter === 'all'
      ? allItems
      : filter === 'sources'
      ? sources
      : reels;

  const formatDuration = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${mins}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Library className="w-5 h-5 text-violet-400" />
            Media & Video Library
          </h2>
          <p className="text-xs text-slate-400">
            Browse all uploaded master videos and rendered viral short reels.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {(['all', 'sources', 'reels'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold capitalize transition cursor-pointer ${
                filter === tab
                  ? 'bg-violet-600 text-white shadow-md'
                  : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {tab === 'sources' ? 'Source Videos' : tab === 'reels' ? 'Exported Reels' : 'All Media'}
            </button>
          ))}
        </div>
      </div>

      {filtered.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 sm:gap-5">
          {filtered.map((item) => (
            <div
              key={item.id}
              className="group p-3.5 rounded-2xl bg-[#0F1422] border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between space-y-3"
            >
              <div className="relative aspect-video rounded-xl bg-slate-900 overflow-hidden border border-slate-800">
                {item.thumbnail ? (
                  <img
                    src={item.thumbnail}
                    alt={item.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-400">
                    <Film className="w-7 h-7" />
                  </div>
                )}

                <button
                  onClick={() => onPreviewVideo(item.url, item.title)}
                  className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition cursor-pointer"
                >
                  <div className="w-9 h-9 rounded-full bg-violet-600 text-white flex items-center justify-center shadow-lg">
                    <Play className="w-4 h-4 ml-0.5 fill-current" />
                  </div>
                </button>

                <div className="absolute bottom-1.5 right-1.5 px-2 py-0.5 rounded bg-black/80 text-[10px] font-mono text-white">
                  {formatDuration(item.duration)}
                </div>

                <div className="absolute top-1.5 left-1.5">
                  <span
                    className={`px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wider uppercase ${
                      item.type === 'reel'
                        ? 'bg-violet-500/20 text-violet-300 border border-violet-500/30'
                        : 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                    }`}
                  >
                    {item.type === 'reel' ? 'Short Reel' : 'Source'}
                  </span>
                </div>
              </div>

              <div className="space-y-0.5">
                <h4 className="text-xs font-bold text-white truncate" title={item.title}>
                  {item.title}
                </h4>
                <p className="text-[11px] text-slate-400 font-mono">{item.resolution}</p>
              </div>

              <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
                <button
                  onClick={() => onPreviewVideo(item.url, item.title)}
                  className="text-xs text-slate-400 hover:text-white flex items-center gap-1 cursor-pointer"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>Preview</span>
                </button>
                <a
                  href={item.url}
                  download
                  className="text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1 cursor-pointer font-semibold"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download</span>
                </a>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-12 text-center rounded-2xl bg-[#0F1422] border border-slate-800 text-slate-400">
          <p>No media files found in this category.</p>
        </div>
      )}
    </div>
  );
};
