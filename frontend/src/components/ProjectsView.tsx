import React, { useState } from 'react';
import { FolderKanban, Search, Film, Calendar, Trash2, Edit2, ArrowRight, Play } from 'lucide-react';
import { Project } from '../types';
import { api } from '../services/api';

interface ProjectsViewProps {
  projects: Project[];
  onOpenProject: (project: Project) => void;
  onRefreshProjects: () => void;
}

export const ProjectsView: React.FC<ProjectsViewProps> = ({
  projects,
  onOpenProject,
  onRefreshProjects,
}) => {
  const [search, setSearch] = useState('');
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase())
  );

  const handleStartRename = (project: Project, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingId(project.id);
    setRenameText(project.name);
  };

  const handleSaveRename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!renamingId || !renameText.trim()) return;
    try {
      await api.renameProject(renamingId, renameText.trim());
      setRenamingId(null);
      onRefreshProjects();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this project and all its generated reels?')) return;
    try {
      setDeletingId(id);
      await api.deleteProject(id);
      setDeletingId(null);
      onRefreshProjects();
    } catch (err) {
      console.error(err);
      setDeletingId(null);
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FolderKanban className="w-5 h-5 text-violet-400" />
            My Video Projects
          </h2>
          <p className="text-xs text-slate-400">
            Locally saved projects persisted on disk. Reopen, rename, or export anytime.
          </p>
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search projects..."
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-[#0F1422] border border-slate-800 text-xs text-white placeholder-slate-400 focus:outline-none focus:border-violet-500"
          />
        </div>
      </div>

      {/* Projects Grid */}
      {filtered.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((project) => (
            <div
              key={project.id}
              onClick={() => onOpenProject(project)}
              className="group p-4 rounded-2xl bg-[#0F1422] border border-slate-800 hover:border-violet-500/50 hover:bg-[#121929] transition-all duration-200 cursor-pointer shadow-lg flex flex-col justify-between space-y-4"
            >
              {/* Thumbnail Container */}
              <div className="relative aspect-video rounded-xl bg-slate-900 overflow-hidden border border-slate-800">
                {project.scenes?.[0]?.thumbnail_url ? (
                  <img
                    src={project.scenes[0].thumbnail_url}
                    alt={project.name}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-400">
                    <Film className="w-8 h-8" />
                  </div>
                )}
                <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-[10px] font-mono font-bold text-white">
                  {formatDuration(project.metadata.duration)}
                </div>
              </div>

              {/* Title & Info */}
              <div className="space-y-1">
                {renamingId === project.id ? (
                  <form onSubmit={handleSaveRename} onClick={(e) => e.stopPropagation()} className="flex gap-2">
                    <input
                      type="text"
                      value={renameText}
                      onChange={(e) => setRenameText(e.target.value)}
                      autoFocus
                      className="flex-1 px-2 py-1 rounded bg-slate-800 border border-violet-500 text-xs text-white"
                    />
                    <button type="submit" className="px-2 py-1 bg-violet-600 text-white text-xs rounded font-bold">
                      Save
                    </button>
                  </form>
                ) : (
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white group-hover:text-violet-300 transition truncate max-w-[200px]">
                      {project.name}
                    </h3>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => handleStartRename(project, e)}
                        className="p-1 rounded text-slate-400 hover:text-white"
                        title="Rename"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => handleDelete(project.id, e)}
                        className="p-1 rounded text-slate-400 hover:text-rose-400"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-2 text-xs text-slate-400 font-medium">
                  <span>{project.clips?.length ?? 0} Reels</span>
                  <span>•</span>
                  <span>{project.metadata.width}x{project.metadata.height}</span>
                  <span>•</span>
                  <span>{new Date(project.created_at).toLocaleDateString()}</span>
                </div>
              </div>

              {/* Action Bar */}
              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-semibold text-slate-400 group-hover:text-violet-400">
                <span>Open in Studio</span>
                <ArrowRight className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-12 text-center rounded-2xl bg-[#0F1422] border border-slate-800 text-slate-400">
          <p>No projects found matching your search.</p>
        </div>
      )}
    </div>
  );
};
