import { Project, DashboardStats, GenerateReelsParams, ClipConfig, CleanupParams } from '../types';

const API_BASE = 'https://hariomslap.tail074e1a.ts.net';

const normalizeMediaUrls = <T,>(value: T): T => {
  if (typeof value === 'string') {
    return (value.startsWith('/media/')
      ? `${API_BASE}${value}`
      : value) as T;
  }

  if (Array.isArray(value)) {
    return value.map(normalizeMediaUrls) as T;
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, val]) => [
        key,
        normalizeMediaUrls(val),
      ])
    ) as T;
  }

  return value;
};
export const api = {
  async getStats(): Promise<DashboardStats> {
    const res = await fetch(`${API_BASE}/stats`);
    if (!res.ok) throw new Error('Failed to fetch dashboard stats');
    return normalizeMediaUrls(await res.json());
  },
  

  async listProjects(): Promise<Project[]> {
    const res = await fetch(`${API_BASE}/projects`);
    if (!res.ok) throw new Error('Failed to fetch projects');
    return normalizeMediaUrls(await res.json());
  },

  async getProject(id: string): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${id}`);
    if (!res.ok) throw new Error('Failed to fetch project');
    return normalizeMediaUrls(await res.json());
  },

  async renameProject(id: string, name: string): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) throw new Error('Failed to rename project');
    return normalizeMediaUrls(await res.json());
  },

  async deleteProject(id: string): Promise<boolean> {
    const res = await fetch(`${API_BASE}/projects/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete project');
    return true;
  },

  uploadVideo(
    file: File,
    name?: string,
    onProgress?: (pct: number) => void
  ): Promise<Project> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file);
      if (name) formData.append('name', name);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          const percent = Math.round((event.loaded / event.total) * 100);
          onProgress(percent);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(normalizeMediaUrls(JSON.parse(xhr.responseText)));
          } catch (e) {
            reject(new Error('Invalid response from server'));
          }
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.detail || 'Upload failed'));
          } catch {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      };

      xhr.onerror = () => reject(new Error('Network error during upload'));
      xhr.open('POST', `${API_BASE}/upload`);
      xhr.send(formData);
    });
  },

  async triggerAnalysis(id: string): Promise<{ success: boolean; message: string; project: Project }> {
    const res = await fetch(`${API_BASE}/projects/${id}/analyze`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to trigger analysis');
    return normalizeMediaUrls(await res.json());
  },

  async generateReels(
    id: string,
    params: GenerateReelsParams
  ): Promise<{ success: boolean; message: string; project: Project }> {
    const res = await fetch(`${API_BASE}/projects/${id}/generate-reels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error('Failed to generate reels');
    return normalizeMediaUrls(await res.json());
  },

  async updateClip(id: string, clipId: string, clip: ClipConfig): Promise<ClipConfig> {
    const res = await fetch(`${API_BASE}/projects/${id}/clips/${clipId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(clip),
    });
    if (!res.ok) throw new Error('Failed to update clip');
    return normalizeMediaUrls(await res.json());
  },

  async renderClip(id: string, clipId: string): Promise<ClipConfig> {
    const res = await fetch(`${API_BASE}/projects/${id}/clips/${clipId}/render`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to render clip');
    return normalizeMediaUrls(await res.json());
  },

  async exportBatch(id: string, clipIds: string[]): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/projects/${id}/export-batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clip_ids: clipIds, quality: 'high', fps: 30, resolution: '1080x1920' }),
    });
    if (!res.ok) throw new Error('Failed to start batch export');
    return normalizeMediaUrls(await res.json());
  },

  async getDownloadZip(id: string): Promise<{ download_url: string }> {
    const res = await fetch(`${API_BASE}/projects/${id}/download-all`);
    if (!res.ok) throw new Error('Failed to get download zip');
    return normalizeMediaUrls(await res.json());
  },

  async triggerCleanup(id: string, params: CleanupParams): Promise<{ success: boolean; message: string; project: Project }> {
    const res = await fetch(`${API_BASE}/projects/${id}/cleanup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to start video cleanup');
    }
    return normalizeMediaUrls(await res.json());
  },

  async saveCleanupRegions(id: string, regions: CleanupParams['regions']): Promise<CleanupParams['regions']> {
    const res = await fetch(`${API_BASE}/projects/${id}/cleanup-regions`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ regions }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to save cleanup regions');
    }
    const data: { regions: CleanupParams['regions'] } = await res.json();
    return data.regions;
  },

  async previewCleanupFrame(id: string, params: CleanupParams, timestamp: number = 2.0): Promise<{ preview_url: string }> {
    const res = await fetch(`${API_BASE}/projects/${id}/cleanup/preview?timestamp=${timestamp}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error('Failed to render cleanup preview frame');
    return normalizeMediaUrls(await res.json());
  },

  async cancelJob(id: string): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/projects/${id}/cancel`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to cancel job');
    return normalizeMediaUrls(await res.json());
  },
};
