import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DashboardView } from './components/DashboardView';
import { UploadModal } from './components/UploadModal';
import { SceneInspector } from './components/SceneInspector';
import { StudioView } from './components/StudioView';
import { ReelGeneratorModal } from './components/ReelGeneratorModal';
import { BatchExportModal } from './components/BatchExportModal';
import { ProjectsView } from './components/ProjectsView';
import { VideoLibraryView } from './components/VideoLibraryView';
import { SettingsView } from './components/SettingsView';
import { VideoPreviewModal } from './components/VideoPreviewModal';

import { Project, DashboardStats, GenerateReelsParams, ClipConfig } from './types';
import { api } from './services/api';

export function App() {
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);

  // Studio Sub-view: "scenes" (AI Scene Inspector) vs "editor" (Vertical Studio)
  const [studioSubView, setStudioSubView] = useState<'scenes' | 'editor'>('scenes');

  // Modals state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isReelGenOpen, setIsReelGenOpen] = useState(false);
  const [isBatchExportOpen, setIsBatchExportOpen] = useState(false);
  const [previewModalData, setPreviewModalData] = useState<{ url: string; title: string } | null>(null);

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isGeneratingReels, setIsGeneratingReels] = useState(false);

  // Initial Data Fetch
  const loadInitialData = async () => {
    try {
      const [s, p] = await Promise.all([api.getStats(), api.listProjects()]);
      setStats(s);
      setProjects(p);

      // If no project active yet, default to most recent if available
      if (!currentProject && p.length > 0) {
        setCurrentProject(p[0]);
      }
    } catch (err) {
      console.error('Failed to load initial data:', err);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  // Poll active project if analyzing or exporting
  useEffect(() => {
    if (!currentProject) return;
    if (currentProject.status === 'analyzing' || currentProject.status === 'exporting') {
      const interval = setInterval(async () => {
        try {
          const updated = await api.getProject(currentProject.id);
          setCurrentProject(updated);
          if (updated.status !== 'analyzing') {
            setIsAnalyzing(false);
          }
          // Refresh list as well
          const p = await api.listProjects();
          setProjects(p);
        } catch (e) {
          console.error(e);
        }
      }, 1500);
      return () => clearInterval(interval);
    }
  }, [currentProject?.id, currentProject?.status]);

  // Handler when a video is freshly uploaded
  const handleProjectUploaded = (project: Project) => {
    setCurrentProject(project);
    setProjects((prev) => [project, ...prev.filter((p) => p.id !== project.id)]);
    setCurrentTab('studio');
    setStudioSubView('scenes');
    // Trigger automatic AI scene analysis
    handleStartAnalysis(project.id);
  };

  const handleStartAnalysis = async (projectId?: string) => {
    const id = projectId || currentProject?.id;
    if (!id) return;
    try {
      setIsAnalyzing(true);
      await api.triggerAnalysis(id);
      const updated = await api.getProject(id);
      setCurrentProject(updated);
    } catch (err: any) {
      console.error('Analysis trigger failed:', err);
      setIsAnalyzing(false);
    }
  };

  const handleGenerateReels = async (params: GenerateReelsParams) => {
    if (!currentProject) return;
    try {
      setIsGeneratingReels(true);
      const updated = await api.generateReels(currentProject.id, params);
      setCurrentProject(updated);
      setIsGeneratingReels(false);
      setIsReelGenOpen(false);
      // Switch directly to Vertical Studio editor
      setStudioSubView('editor');
      // Refresh stats
      api.getStats().then(setStats);
    } catch (err: any) {
      console.error('Reel generation failed:', err);
      setIsGeneratingReels(false);
    }
  };

  const handleOpenProject = (project: Project) => {
    setCurrentProject(project);
    setCurrentTab('studio');
    // If clips already generated, open editor directly, otherwise scene inspector
    if (project.clips && project.clips.length > 0) {
      setStudioSubView('editor');
    } else {
      setStudioSubView('scenes');
    }
  };

  // Get current header title
  const getHeaderInfo = () => {
    switch (currentTab) {
      case 'dashboard':
        return { title: 'Dashboard', subtitle: 'Overview of videos and viral shorts performance' };
      case 'studio':
        return {
          title: currentProject ? `Studio • ${currentProject.name}` : 'Reel Studio',
          subtitle:
            studioSubView === 'scenes'
              ? 'Multi-Modal Scene Detection & Moment Selection'
              : 'Interactive 9:16 Vertical Video & Subtitles Editor',
        };
      case 'projects':
        return { title: 'My Projects', subtitle: 'Manage locally saved video reels projects' };
      case 'library':
        return { title: 'Video Library', subtitle: 'All source videos and exported reels' };
      case 'settings':
        return { title: 'Settings', subtitle: 'Local FFmpeg and AI processing parameters' };
      default:
        return { title: 'AI Reel Maker', subtitle: '' };
    }
  };

  const headerInfo = getHeaderInfo();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#090D16] text-slate-100 font-sans">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onTabChange={(tab) => {
          setCurrentTab(tab);
          if (tab === 'studio' && currentProject) {
            if (currentProject.clips && currentProject.clips.length > 0) {
              setStudioSubView('editor');
            } else {
              setStudioSubView('scenes');
            }
          }
        }}
        activeProjectName={currentProject?.name}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Global Header */}
        <Header
          title={headerInfo.title}
          subtitle={headerInfo.subtitle}
          onNewProject={() => setIsUploadOpen(true)}
          isProcessing={isAnalyzing || isGeneratingReels}
        />

        {/* Dynamic Views */}
        <main className="flex-1 overflow-y-auto">
          {currentTab === 'dashboard' && (
            <DashboardView
              stats={stats}
              onNewProject={() => setIsUploadOpen(true)}
              onOpenProject={handleOpenProject}
            />
          )}

          {currentTab === 'studio' && (
            <div className="h-full">
              {!currentProject ? (
                <div className="p-12 text-center text-slate-400 space-y-4">
                  <p className="text-base font-bold text-white">No Active Video Project Selected</p>
                  <p className="text-xs">Upload a video or choose an existing project to start creating reels.</p>
                  <button
                    onClick={() => setIsUploadOpen(true)}
                    className="px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs transition cursor-pointer"
                  >
                    Upload Video
                  </button>
                </div>
              ) : studioSubView === 'scenes' ? (
                /* Scene Inspector Sub-View */
                <div className="p-8 max-w-7xl mx-auto">
                  <SceneInspector
                    project={currentProject}
                    onSelectScene={(sceneId, selected) => {
                      const updatedScenes = currentProject.scenes.map((s) =>
                        s.scene_id === sceneId ? { ...s, selected } : s
                      );
                      const updated = { ...currentProject, scenes: updatedScenes };
                      setCurrentProject(updated);
                      api.updateClip(currentProject.id, '', {} as any).catch(() => {});
                    }}
                    onSelectAll={(selected) => {
                      const updatedScenes = currentProject.scenes.map((s) => ({ ...s, selected }));
                      setCurrentProject({ ...currentProject, scenes: updatedScenes });
                    }}
                    onPreviewScene={(scene) => {
                      setPreviewModalData({
                        url: currentProject.video_url,
                        title: `${currentProject.name} - ${scene.scene_id}`,
                      });
                    }}
                    onOpenReelGenerator={() => setIsReelGenOpen(true)}
                    onReAnalyze={() => handleStartAnalysis()}
                    isAnalyzing={isAnalyzing}
                  />
                </div>
              ) : (
                /* Vertical Video Studio Editor Sub-View */
                <StudioView
                  project={currentProject}
                  onUpdateProject={(p) => setCurrentProject(p)}
                  onOpenBatchExport={() => setIsBatchExportOpen(true)}
                  onBackToScenes={() => setStudioSubView('scenes')}
                />
              )}
            </div>
          )}

          {currentTab === 'projects' && (
            <ProjectsView
              projects={projects}
              onOpenProject={handleOpenProject}
              onRefreshProjects={loadInitialData}
            />
          )}

          {currentTab === 'library' && (
            <VideoLibraryView
              projects={projects}
              onPreviewVideo={(url, title) => setPreviewModalData({ url, title })}
            />
          )}

          {currentTab === 'settings' && <SettingsView />}
        </main>
      </div>

      {/* Global Modals */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onProjectUploaded={handleProjectUploaded}
      />

      <ReelGeneratorModal
        isOpen={isReelGenOpen}
        onClose={() => setIsReelGenOpen(false)}
        onGenerate={handleGenerateReels}
        isGenerating={isGeneratingReels}
        totalScenes={currentProject?.scenes?.length || 0}
      />

      {currentProject && (
        <BatchExportModal
          isOpen={isBatchExportOpen}
          onClose={() => setIsBatchExportOpen(false)}
          project={currentProject}
          onUpdateProject={(p) => setCurrentProject(p)}
          onPreviewClip={(clip) =>
            setPreviewModalData({
              url: clip.output_url,
              title: `${currentProject.name} - ${clip.title}`,
            })
          }
        />
      )}

      <VideoPreviewModal
        isOpen={!!previewModalData}
        onClose={() => setPreviewModalData(null)}
        videoUrl={previewModalData?.url || null}
        title={previewModalData?.title || 'Video Preview'}
      />
    </div>
  );
}

export default App;
