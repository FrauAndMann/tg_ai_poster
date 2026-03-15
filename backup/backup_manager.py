"""
Backup Manager for TG AI Poster.

Creates automated backups of:
- SQLite database
- ChromaDB vector store
- Configuration files
- Session files
"""

from __future__ import annotations

import gzip
import hashlib
import logging
import os
import shutil
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from core.config import Settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BackupManager:
    """
    Manages backup creation and rotation.

    Creates compressed tar.gz archives containing:
    - Database file(s)
    - ChromaDB directory (optional)
    - Configuration files
    - Session files (optional)
    """

    def __init__(
        self,
        settings: Settings,
        backup_dir: str = "./backups",
    ):
        """
        Initialize Backup Manager.

        Args:
            settings: Application settings
            backup_dir: Directory for storing backups
        """
        self.settings = settings
        self.backup_dir = Path(backup_dir)

        # Backup paths
        self.db_path = self._extract_db_path()
        self.chroma_path = Path("./data/chroma")
        self.config_path = Path("config.yaml")
        self.config_dir = Path("config")
        self.sessions_dir = Path("sessions")

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _extract_db_path(self) -> Path:
        """Extract database path from database URL."""
        db_url = self.settings.database.url
        if db_url.startswith("sqlite"):
            # Extract path from sqlite URL
            # sqlite:///./data/tg_poster.db -> ./data/tg_poster.db
            path = db_url.replace("sqlite:///", "").replace("sqlite+aiosqlite:///", "")
            return Path(path)
        return Path("./data/tg_poster.db")

    async def create_backup(
        self,
        include_chroma: bool = True,
        include_sessions: bool = True,
        backup_type: str = "manual",
    ) -> str:
        """
        Create a backup archive.

        Args:
            include_chroma: Include ChromaDB in backup
            include_sessions: Include session files in backup
            backup_type: Type of backup (manual, scheduled, daily, weekly, monthly)

        Returns:
            str: Path to created backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{backup_type}_{timestamp}.tar.gz"
        backup_path = self.backup_dir / backup_name

        logger.info(f"Creating backup: {backup_name}")

        try:
            # Create temporary staging directory
            staging_dir = self.backup_dir / f"staging_{timestamp}"
            staging_dir.mkdir(exist_ok=True)

            try:
                # Copy database
                if self.db_path.exists():
                    db_copy = staging_dir / self.db_path.name
                    shutil.copy2(self.db_path, db_copy)
                    logger.debug(f"Copied database: {self.db_path}")

                # Copy ChromaDB (optional)
                if include_chroma and self.chroma_path.exists():
                    chroma_copy = staging_dir / "chroma"
                    shutil.copytree(self.chroma_path, chroma_copy)
                    logger.debug(f"Copied ChromaDB: {self.chroma_path}")

                # Copy configuration
                if self.config_path.exists():
                    shutil.copy2(self.config_path, staging_dir / "config.yaml")
                    logger.debug(f"Copied config: {self.config_path}")

                if self.config_dir.exists():
                    config_copy = staging_dir / "config"
                    shutil.copytree(self.config_dir, config_copy)
                    logger.debug(f"Copied config dir: {self.config_dir}")

                # Copy sessions (optional)
                if include_sessions and self.sessions_dir.exists():
                    sessions_copy = staging_dir / "sessions"
                    shutil.copytree(self.sessions_dir, sessions_copy)
                    logger.debug(f"Copied sessions: {self.sessions_dir}")

                # Create manifest
                manifest = self._create_manifest(
                    include_chroma=include_chroma,
                    include_sessions=include_sessions,
                )
                manifest_path = staging_dir / "manifest.json"
                with open(manifest_path, "w", encoding="utf-8") as f:
                    import json
                    json.dump(manifest, f, indent=2)

                # Create compressed archive
                with tarfile.open(backup_path, "w:gz") as tar:
                    tar.add(staging_dir, arcname="backup")

                logger.info(f"Backup created successfully: {backup_path}")

            finally:
                # Clean up staging directory
                if staging_dir.exists():
                    shutil.rmtree(staging_dir)

            return str(backup_path)

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise

    def _create_manifest(
        self,
        include_chroma: bool,
        include_sessions: bool,
    ) -> dict:
        """Create backup manifest with metadata."""
        manifest = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "tg_poster_version": "1.0.0",
            "components": {
                "database": str(self.db_path),
                "chroma": include_chroma and self.chroma_path.exists(),
                "config": True,
                "sessions": include_sessions and self.sessions_dir.exists(),
            },
            "checksums": {},
        }

        # Add database checksum
        if self.db_path.exists():
            manifest["checksums"]["database"] = self._calculate_checksum(self.db_path)

        return manifest

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def get_backup_size(self, backup_path: str) -> float:
        """
        Get backup file size in MB.

        Args:
            backup_path: Path to backup file

        Returns:
            float: Size in MB
        """
        path = Path(backup_path)
        if path.exists():
            return path.stat().st_size / (1024 * 1024)
        return 0.0

    def list_backups(self) -> list[dict]:
        """
        List all available backups.

        Returns:
            list: List of backup info dictionaries
        """
        backups = []

        for backup_file in self.backup_dir.glob("backup_*.tar.gz"):
            try:
                stat = backup_file.stat()
                backups.append({
                    "path": str(backup_file),
                    "name": backup_file.name,
                    "size_mb": stat.st_size / (1024 * 1024),
                    "created_at": datetime.fromtimestamp(stat.st_ctime),
                    "type": self._extract_backup_type(backup_file.name),
                })
            except Exception as e:
                logger.warning(f"Error reading backup {backup_file}: {e}")

        # Sort by creation time, newest first
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups

    def _extract_backup_type(self, filename: str) -> str:
        """Extract backup type from filename."""
        # backup_manual_20240101_120000.tar.gz -> manual
        parts = filename.replace("backup_", "").replace(".tar.gz", "").split("_")
        if len(parts) >= 1:
            return parts[0]
        return "unknown"

    def rotate_backups(
        self,
        daily_keep: int = 30,
        weekly_keep: int = 12,
        monthly_keep: int = 12,
    ) -> int:
        """
        Rotate backups according to retention policy.

        Args:
            daily_keep: Number of daily backups to keep
            weekly_keep: Number of weekly backups to keep
            monthly_keep: Number of monthly backups to keep

        Returns:
            int: Number of backups deleted
        """
        backups = self.list_backups()
        deleted_count = 0

        # Group backups by type
        daily_backups = [b for b in backups if b["type"] == "daily"]
        weekly_backups = [b for b in backups if b["type"] == "weekly"]
        monthly_backups = [b for b in backups if b["type"] == "monthly"]
        manual_backups = [b for b in backups if b["type"] == "manual"]

        # Delete old daily backups
        for backup in daily_backups[daily_keep:]:
            self._delete_backup(backup["path"])
            deleted_count += 1

        # Delete old weekly backups
        for backup in weekly_backups[weekly_keep:]:
            self._delete_backup(backup["path"])
            deleted_count += 1

        # Delete old monthly backups
        for backup in monthly_backups[monthly_keep:]:
            self._delete_backup(backup["path"])
            deleted_count += 1

        # Keep all manual backups (they don't expire)

        if deleted_count > 0:
            logger.info(f"Rotated {deleted_count} old backups")

        return deleted_count

    def _delete_backup(self, backup_path: str) -> bool:
        """Delete a backup file."""
        try:
            Path(backup_path).unlink()
            logger.info(f"Deleted backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete backup {backup_path}: {e}")
            return False

    def cleanup_old_backups(self, max_age_days: int = 90) -> int:
        """
        Delete backups older than specified age.

        Args:
            max_age_days: Maximum age in days

        Returns:
            int: Number of backups deleted
        """
        backups = self.list_backups()
        cutoff = datetime.now() - timedelta(days=max_age_days)
        deleted_count = 0

        for backup in backups:
            # Don't delete manual backups
            if backup["type"] == "manual":
                continue

            if backup["created_at"] < cutoff:
                self._delete_backup(backup["path"])
                deleted_count += 1

        return deleted_count

    def get_total_backup_size(self) -> float:
        """Get total size of all backups in MB."""
        backups = self.list_backups()
        return sum(b["size_mb"] for b in backups)
