import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from config import PROJECTS_DIR, UPLOADS_DIR, EXPORTS_DIR, THUMBNAILS_DIR
from models import Project

logger = logging.getLogger(__name__)

class ProjectStore:
    def __init__(self, storage_dir: Path = PROJECTS_DIR):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, project_id: str) -> Path:
        return self.storage_dir / f"{project_id}.json"

    def save_project(self, project: Project) -> Project:
        project.updated_at = datetime.now().isoformat()
        path = self._get_path(project.id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(project.model_dump_json(indent=2))
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        path = self._get_path(project_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Project(**data)
        except Exception as e:
            logger.error(f"Error loading project {project_id}: {e}")
            return None

    def list_projects(self) -> List[Project]:
        projects = []
        for file in sorted(self.storage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    projects.append(Project(**data))
            except Exception as e:
                logger.error(f"Failed to read project file {file}: {e}")
        return projects

    def delete_project(self, project_id: str) -> bool:
        project = self.get_project(project_id)
        path = self._get_path(project_id)
        if path.exists():
            path.unlink()
        
        # Cleanup associated video files if exists
        if project and project.video_path:
            video_file = Path(project.video_path)
            if video_file.exists() and video_file.is_file():
                try:
                    video_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete video file {video_file}: {e}")

        return True

    def get_stats(self) -> Dict[str, Any]:
        projects = self.list_projects()
        total_videos = len(projects)
        total_clips = sum(len(p.clips) for p in projects)
        processing = sum(1 for p in projects if p.status in ["analyzing", "exporting"])
        completed = sum(1 for p in projects if p.status in ["completed", "ready"])

        return {
            "total_videos": total_videos,
            "total_clips": total_clips,
            "processing_videos": processing,
            "completed_projects": completed,
            "recent_projects": [p.model_dump() for p in projects[:6]]
        }

project_store = ProjectStore()
