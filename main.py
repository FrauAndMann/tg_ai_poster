#!/usr/bin/env python3
"""
TG AI Poster - Main Entry Point

Autonomous AI-powered Telegram channel management system.

Usage:
    python main.py              # Start the application
    python main.py --dry-run    # Run without publishing
    python main.py --once       # Run pipeline once and exit
    python main.py --init-db    # Initialize database and exit
    python main.py --backup     # Create backup and exit
    python main.py --restore backup_file.tar.gz  # Restore from backup
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from typing import Optional

from core.config import Settings
from core.logger import setup_logger, logger
from core.scheduler import Scheduler
from memory.database import Database, init_database, close_database
from pipeline.orchestrator import PipelineOrchestrator, PipelineResult
from publisher import get_publisher
from publisher.base import BasePublisher
from backup.backup_manager import BackupManager
from backup.restore_manager import RestoreManager

# Global state
_shutdown_event: Optional[asyncio.Event] = None
_scheduler: Optional[Scheduler] = None
_publisher: Optional[BasePublisher] = None
_db: Optional[Database] = None


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="TG AI Poster - Autonomous Telegram posting system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                    Start scheduled posting
    python main.py --dry-run          Test without publishing
    python main.py --once             Run once and exit
    python main.py --config my.yaml   Use custom config file
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Run without actually publishing posts",
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run pipeline once and exit (no scheduling)",
    )

    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database tables and exit",
    )

    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--backup",
        "-b",
        action="store_true",
        help="Create backup and exit",
    )

    parser.add_argument(
        "--restore",
        "-r",
        type=str,
        help="Restore from backup file",
    )

    return parser.parse_args()


async def create_backup(settings: Settings) -> str:
    """Create backup using BackupManager."""
    from backup.backup_manager import BackupManager

    backup_manager = BackupManager(settings)
    backup_file = await backup_manager.create_backup()
    return backup_file


async def restore_backup(settings: Settings, backup_path: str) -> bool:
    """Restore from backup using RestoreManager."""

    restore_manager = RestoreManager(settings)
    result = await restore_manager.restore(backup_path)
    return result.get("success", False)


async def initialize(settings: Settings) -> tuple[Database, BasePublisher]:
    """
    Initialize all components.

    Args:
        settings: Application settings

    Returns:
        tuple: (database, publisher)
    """
    logger.info("Initializing TG AI Poster...")

    # Initialize database
    db = await init_database(
        db_url=settings.database.url,
        echo=settings.database.echo or settings.debug,
    )
    logger.info("Database initialized")

    # Initialize publisher
    publisher = get_publisher(
        mode=settings.telegram.posting_mode,
        bot_token=settings.telegram.bot_token,
        channel_id=settings.telegram.channel_id,
        telethon_api_id=settings.telethon.api_id,
        telethon_api_hash=settings.telethon.api_hash,
        telethon_phone=settings.telethon.phone,
        telethon_session_path=settings.telethon.session_path,
    )

    await publisher.start()
    logger.info(f"Publisher initialized (mode: {settings.telegram.posting_mode})")

    return db, publisher


async def shutdown() -> None:
    """Gracefully shutdown all components."""
    global _shutdown_event, _scheduler, _publisher, _db

    logger.info("Shutting down...")

    # Stop scheduler
    if _scheduler:
        _scheduler.stop(wait=True)
        logger.info("Scheduler stopped")

    # Stop publisher
    if _publisher:
        await _publisher.stop()
        logger.info("Publisher stopped")

    # Close database
    await close_database()
    logger.info("Database closed")

    # Signal completion
    if _shutdown_event:
        _shutdown_event.set()

    logger.info("Shutdown complete")


def signal_handler(sig, frame) -> None:
    """Handle shutdown signals."""
    global _shutdown_event

    logger.info(f"Received signal {sig}, initiating shutdown...")

    if _shutdown_event:
        _shutdown_event.set()
    else:
        # Force exit if event not initialized
        sys.exit(0)


async def run_pipeline_once(
    orchestrator: PipelineOrchestrator,
    dry_run: bool = False,
) -> PipelineResult:
    """
    Run the pipeline once.

    Args:
        orchestrator: Pipeline orchestrator
        dry_run: Don't actually publish

    Returns:
        PipelineResult: Execution result
    """
    logger.info("Running pipeline once...")
    result = await orchestrator.run(dry_run=dry_run)

    if result.success:
        logger.info(
            f"Pipeline completed successfully. "
            f"Post ID: {result.post_id}, "
            f"Quality: {result.quality_score:.1f}, "
            f"Duration: {result.duration:.2f}s"
        )
    else:
        logger.error(f"Pipeline failed: {result.error}")

    return result


async def run_scheduled(
    orchestrator: PipelineOrchestrator,
    settings: Settings,
    dry_run: bool = False,
) -> None:
    """
    Run with scheduling.

    Args:
        orchestrator: Pipeline orchestrator
        settings: Application settings
        dry_run: Don't actually publish
    """
    global _shutdown_event, _scheduler

    _shutdown_event = asyncio.Event()

    # Create scheduler job function
    async def job_func() -> None:
        try:
            result = await orchestrator.run(dry_run=dry_run)

            if result.success:
                logger.info(
                    f"Scheduled post completed. "
                    f"Post ID: {result.post_id}"
                )

                # Notify admin if configured
                if settings.admin.notify_on_post and settings.admin.telegram_id:
                    # TODO: Send notification to admin
                    pass

            else:
                logger.error(f"Scheduled post failed: {result.error}")

                # Notify admin on error
                if settings.admin.notify_on_error and settings.admin.telegram_id:
                    # TODO: Send error notification to admin
                    pass

        except Exception as e:
            logger.exception(f"Pipeline execution error: {e}")

    # Create and start scheduler
    _scheduler = Scheduler(settings, job_func)
    _scheduler.start()

    logger.info(
        f"Scheduler started. Next runs: {_scheduler.get_next_run_times()}"
    )

    # Wait for shutdown signal
    await _shutdown_event.wait()

    # Cleanup
    await shutdown()


async def async_main(args: argparse.Namespace) -> int:
    """
    Main async entry point.

    Args:
        args: Command line arguments

    Returns:
        int: Exit code
    """
    global _publisher, _db

    try:
        # Load settings
        settings = Settings.create(args.config)

        # Override with command line args
        if args.dry_run:
            settings.dry_run = True
        if args.debug:
            settings.debug = True

        # Setup logging
        log_level = "DEBUG" if settings.debug else "INFO"
        setup_logger(
            log_level=log_level,
            log_dir="logs",
        )

        logger.info(f"TG AI Poster starting (dry_run={settings.dry_run})")

        # Initialize database only
        if args.init_db:
            logger.info("Initializing database...")
            await init_database(
                db_url=settings.database.url,
                echo=settings.debug,
            )
            logger.info("Database initialized successfully")
            return 0

        # Create backup
        if args.backup:
            logger.info("Creating backup...")
            try:
                backup_file = await create_backup(settings)
                backup_manager = BackupManager(settings)
                size_mb = backup_manager.get_backup_size(backup_file)
                logger.info(f"Backup created: {backup_file} ({size_mb:.2f} MB)")
            except Exception as e:
                logger.error(f"Backup failed: {e}")
                return 1
            return 0

        # Restore from backup
        if args.restore:
            logger.info(f"Restoring from backup: {args.restore}")
            try:
                success = await restore_backup(settings, args.restore)
                if success:
                    logger.info("Restore completed successfully")
                else:
                    logger.error("Restore failed")
                    return 1
            except Exception as e:
                logger.error(f"Restore failed: {e}")
                return 1
            return 0

        # Full initialization
        _db, _publisher = await initialize(settings)

        # Create orchestrator
        orchestrator = PipelineOrchestrator(
            settings=settings,
            db=_db,
            publisher=_publisher,
        )

        # Run once mode
        if args.once:
            result = await run_pipeline_once(orchestrator, dry_run=settings.dry_run)
            await shutdown()
            return 0 if result.success else 1

        # Scheduled mode
        await run_scheduled(orchestrator, settings, dry_run=settings.dry_run)

        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        await shutdown()
        return 130

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        await shutdown()
        return 1


def main() -> int:
    """Main entry point."""
    # Parse arguments
    args = parse_args()

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run async main
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
