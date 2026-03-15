"""
Restore Manager for TG AI Poster.

Handles restoration of backups created by BackupManager.
"""

from __future__ import annotations

import json
import logging
import shutil
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import Settings

logger = logging.getLogger(__name__)


class RestoreManager:
    """
    Manages backup restoration.

    Provides safe restore with:
    - Pre-restore validation
    - Automatic backup of current state
    - Selective component restoration
    """

    def __init__(
        self,
        settings: Settings,
        backup_dir: str = "./backups",
    ):
        """
        Initialize Restore Manager.

        Args:
            settings: Application settings
            backup_dir: Directory containing backups
        """
        self.settings = settings
        self.backup_dir = Path(backup_dir)

        # Target paths
        self.db_path = self._extract_db_path()
        self.chroma_path = Path("./data/chroma")
        self.config_path = Path("config.yaml")
        self.config_dir = Path("config")
        self.sessions_dir = Path("sessions")

    def _extract_db_path(self) -> Path:
        """Extract database path from database URL."""
        db_url = self.settings.database.url
        if db_url.startswith("sqlite"):
            path = db_url.replace("sqlite:///", "").replace("sqlite+aiosqlite:///", "")
            return Path(path)
        return Path("./data/tg_poster.db")

    def validate_backup(self, backup_path: str) -> dict:
        """
        Validate backup file integrity.

        Args:
            backup_path: Path to backup file

        Returns:
            dict: Validation result with status and details
        """
        result = {
            "valid": False,
            "error": None,
            "manifest": None,
            "components": [],
        }

        path = Path(backup_path)
        if not path.exists():
            result["error"] = "Backup file not found"
            return result

        if not path.suffix == ".gz" and not path.name.endswith(".tar.gz"):
            result["error"] = "Invalid backup format (expected .tar.gz)"
            return result

        try:
            # Try to open and read manifest
            with tarfile.open(path, "r:gz") as tar:
                # Find manifest
                manifest_member = None
                for member in tar.getmembers():
                    if member.name.endswith("manifest.json"):
                        manifest_member = member
                        break

                if not manifest_member:
                    result["error"] = "Manifest not found in backup"
                    return result

                # Extract and parse manifest
                manifest_file = tar.extractfile(manifest_member)
                if manifest_file:
                    manifest_data = json.loads(manifest_file.read().decode("utf-8"))
                    result["manifest"] = manifest_data
                    result["components"] = list(manifest_data.get("components", {}).keys())

            result["valid"] = True
            return result

        except tarfile.TarError as e:
            result["error"] = f"Invalid archive: {e}"
            return result
        except json.JSONDecodeError as e:
            result["error"] = f"Invalid manifest: {e}"
            return result
        except Exception as e:
            result["error"] = f"Validation error: {e}"
            return result

    async def restore(
        self,
        backup_path: str,
        components: Optional[list[str]] = None,
        create_pre_backup: bool = True,
    ) -> dict:
        """
        Restore from backup.

        Args:
            backup_path: Path to backup file
            components: Components to restore (None = all)
            create_pre_backup: Create backup of current state before restore

        Returns:
            dict: Restore result with status and details
        """
        result = {
            "success": False,
            "error": None,
            "restored_components": [],
            "pre_backup_path": None,
        }

        # Validate backup first
        validation = self.validate_backup(backup_path)
        if not validation["valid"]:
            result["error"] = f"Invalid backup: {validation['error']}"
            return result

        # Create pre-restore backup if requested
        if create_pre_backup:
            try:
                from backup.backup_manager import BackupManager
                backup_manager = BackupManager(self.settings, str(self.backup_dir))
                result["pre_backup_path"] = await backup_manager.create_backup(
                    backup_type="pre_restore"
                )
                logger.info(f"Created pre-restore backup: {result['pre_backup_path']}")
            except Exception as e:
                logger.warning(f"Failed to create pre-restore backup: {e}")

        try:
            # Extract backup to temporary directory
            extract_dir = self.backup_dir / f"restore_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            extract_dir.mkdir(exist_ok=True)

            try:
                with tarfile.open(backup_path, "r:gz") as tar:
                    tar.extractall(extract_dir)

                # Find extracted backup directory
                extracted_dirs = list(extract_dir.iterdir())
                if not extracted_dirs:
                    result["error"] = "Empty backup archive"
                    return result

                backup_root = extracted_dirs[0]  # Usually 'backup' directory

                # Determine components to restore
                all_components = ["database", "chroma", "config", "sessions"]
                restore_components = components or all_components

                # Restore database
                if "database" in restore_components:
                    if await self._restore_database(backup_root):
                        result["restored_components"].append("database")

                # Restore ChromaDB
                if "chroma" in restore_components:
                    if await self._restore_chroma(backup_root):
                        result["restored_components"].append("chroma")

                # Restore config
                if "config" in restore_components:
                    if await self._restore_config(backup_root):
                        result["restored_components"].append("config")

                # Restore sessions
                if "sessions" in restore_components:
                    if await self._restore_sessions(backup_root):
                        result["restored_components"].append("sessions")

                result["success"] = True
                logger.info(f"Restore completed: {result['restored_components']}")

            finally:
                # Clean up extraction directory
                if extract_dir.exists():
                    shutil.rmtree(extract_dir)

            return result

        except Exception as e:
            result["error"] = f"Restore failed: {e}"
            logger.error(f"Restore failed: {e}")
            return result

    async def _restore_database(self, backup_root: Path) -> bool:
        """Restore database from backup."""
        try:
            # Find database file in backup
            db_files = list(backup_root.glob("**/*.db"))
            if not db_files:
                logger.warning("No database file found in backup")
                return False

            backup_db = db_files[0]

            # Ensure target directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy database file
            shutil.copy2(backup_db, self.db_path)
            logger.info(f"Restored database to {self.db_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False

    async def _restore_chroma(self, backup_root: Path) -> bool:
        """Restore ChromaDB from backup."""
        try:
            chroma_backup = backup_root / "chroma"
            if not chroma_backup.exists():
                logger.warning("No ChromaDB found in backup")
                return False

            # Remove existing ChromaDB
            if self.chroma_path.exists():
                shutil.rmtree(self.chroma_path)

            # Copy ChromaDB from backup
            shutil.copytree(chroma_backup, self.chroma_path)
            logger.info(f"Restored ChromaDB to {self.chroma_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore ChromaDB: {e}")
            return False

    async def _restore_config(self, backup_root: Path) -> bool:
        """Restore configuration from backup."""
        try:
            # Restore config.yaml
            backup_config = backup_root / "config.yaml"
            if backup_config.exists():
                shutil.copy2(backup_config, self.config_path)
                logger.info(f"Restored config.yaml")

            # Restore config directory
            backup_config_dir = backup_root / "config"
            if backup_config_dir.exists():
                if self.config_dir.exists():
                    shutil.rmtree(self.config_dir)
                shutil.copytree(backup_config_dir, self.config_dir)
                logger.info(f"Restored config directory")

            return True

        except Exception as e:
            logger.error(f"Failed to restore config: {e}")
            return False

    async def _restore_sessions(self, backup_root: Path) -> bool:
        """Restore sessions from backup."""
        try:
            sessions_backup = backup_root / "sessions"
            if not sessions_backup.exists():
                logger.warning("No sessions found in backup")
                return False

            # Remove existing sessions
            if self.sessions_dir.exists():
                shutil.rmtree(self.sessions_dir)

            # Copy sessions from backup
            shutil.copytree(sessions_backup, self.sessions_dir)
            logger.info(f"Restored sessions to {self.sessions_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore sessions: {e}")
            return False

    def list_available_backups(self) -> list[dict]:
        """List all available backups for restore."""
        from backup.backup_manager import BackupManager

        backup_manager = BackupManager(self.settings, str(self.backup_dir))
        return backup_manager.list_backups()
