import React, { useState, useRef } from 'react';
import { X, UploadCloud, Film, CheckCircle2, AlertCircle, Play, Sparkles, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import { Project } from '../types';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProjectUploaded: (project: Project) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({ isOpen, onClose, onProjectUploaded }) => {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [projectName, setProjectName] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedProject, setUploadedProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelected = (selectedFile: File) => {
    setError(null);
    setFile(selectedFile);
    if (!projectName) {
      const cleanName = selectedFile.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ');
      setProjectName(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    try {
      setIsUploading(true);
      setError(null);
      setUploadProgress(0);

      const project = await api.uploadVideo(file, projectName, (pct) => {
        setUploadProgress(pct);
      });

      setUploadedProject(project);
      setIsUploading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to upload video');
      setIsUploading(false);
    }
  };

  const handleProceed = () => {
    if (uploadedProject) {
      onProjectUploaded(uploadedProject);
      handleReset();
      onClose();
    }
  };

  const handleReset = () => {
    setFile(null);
    setProjectName('');
    setUploadProgress(0);
    setIsUploading(false);
    setUploadedProject(null);
    setError(null);
  };

  const formatDuration = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hrs > 0) {
      return `${hrs}h ${mins}m ${secs}s`;
    }
    return `${mins}m ${secs}s`;
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-2xl bg-[#0F1422] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-violet-500/10 text-violet-400">
              <Film className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Upload Long Video</h3>
              <p className="text-xs text-slate-400 font-medium">MP4, MOV, MKV, WebM up to 50 GB</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isUploading}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5">
          {error && (
            <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!uploadedProject ? (
            <>
              {/* Drag & Drop Area */}
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => !isUploading && fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer ${
                  dragActive
                    ? 'border-violet-500 bg-violet-500/10 scale-[0.99]'
                    : file
                    ? 'border-indigo-500/60 bg-indigo-500/5'
                    : 'border-slate-700/80 hover:border-slate-600 bg-slate-900/40'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="video/mp4,video/quicktime,video/x-matroska,video/webm,video/avi"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && handleFileSelected(e.target.files[0])}
                />

                <div className="w-16 h-16 rounded-2xl bg-slate-800/80 border border-slate-700 flex items-center justify-center mx-auto mb-4 text-violet-400 shadow-inner">
                  <UploadCloud className="w-8 h-8" />
                </div>

                {file ? (
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-white truncate max-w-md mx-auto">{file.name}</p>
                    <p className="text-xs text-slate-400">{formatBytes(file.size)}</p>
                    <span className="inline-block mt-2 text-[11px] text-violet-400 bg-violet-500/10 px-2.5 py-0.5 rounded-full font-medium">
                      Click to change file
                    </span>
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <p className="text-sm font-semibold text-slate-200">
                      Drop your video here, or <span className="text-violet-400 underline">browse</span>
                    </p>
                    <p className="text-xs text-slate-400">
                      Supports high-resolution podcasts, lectures, vlogs, and gameplay
                    </p>
                  </div>
                )}
              </div>

              {/* Project Name Field */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Project Name</label>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="e.g., Tech Podcast Episode #42"
                  disabled={isUploading}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-sm text-white placeholder-slate-400 focus:outline-none focus:border-violet-500 transition"
                />
              </div>

              {/* Upload Progress Bar */}
              {isUploading && (
                <div className="space-y-2 p-4 rounded-xl bg-slate-900/70 border border-slate-800">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-300 flex items-center gap-2">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-violet-400" />
                      Uploading video locally...
                    </span>
                    <span className="text-violet-400 font-mono">{uploadProgress}%</span>
                  </div>
                  <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-150"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}
            </>
          ) : (
            /* Upload Success & Video Metadata Preview */
            <div className="space-y-5 animate-in fade-in duration-300">
              <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 shrink-0" />
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider">Video Uploaded Successfully</h4>
                  <p className="text-xs text-emerald-300/80">Analyzed and ready for AI scene segmentation</p>
                </div>
              </div>

              {/* Video Preview Player */}
              <div className="aspect-video bg-black rounded-xl overflow-hidden border border-slate-800 relative shadow-inner">
                <video
                  src={uploadedProject.video_url}
                  controls
                  className="w-full h-full object-contain"
                />
              </div>

              {/* Metadata Badges Grid */}
              <div className="grid grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-[11px] text-slate-400 uppercase font-semibold">Duration</span>
                  <p className="text-sm font-bold text-white mt-0.5">
                    {formatDuration(uploadedProject.metadata.duration)}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-[11px] text-slate-400 uppercase font-semibold">Resolution</span>
                  <p className="text-sm font-bold text-white mt-0.5">
                    {uploadedProject.metadata.width}x{uploadedProject.metadata.height}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-[11px] text-slate-400 uppercase font-semibold">Frame Rate</span>
                  <p className="text-sm font-bold text-white mt-0.5 font-mono">
                    {uploadedProject.metadata.fps} FPS
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-[11px] text-slate-400 uppercase font-semibold">File Size</span>
                  <p className="text-sm font-bold text-white mt-0.5 font-mono">
                    {formatBytes(uploadedProject.metadata.size_bytes)}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-[#0B0F17] flex items-center justify-between">
          <button
            onClick={onClose}
            disabled={isUploading}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition cursor-pointer"
          >
            Cancel
          </button>

          {!uploadedProject ? (
            <button
              onClick={handleUpload}
              disabled={!file || isUploading}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs tracking-wide shadow-md shadow-violet-600/20 transition cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-3.5 h-3.5" />
                  <span>Upload & Inspect Video</span>
                </>
              )}
            </button>
          ) : (
            <button
              onClick={handleProceed}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs tracking-wide shadow-lg shadow-violet-600/30 transition cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Open in Studio & Detect Scenes</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
