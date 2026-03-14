"""
Scheduler module using APScheduler.

Manages posting schedule with support for interval, fixed, and random timing.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable, Optional

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pytz import timezone

from core.logger import get_logger

if TYPE_CHECKING:
    from core.config import Settings

logger = get_logger(__name__)


class Scheduler:
    """
    APScheduler-based posting scheduler.

    Supports three scheduling modes:
    - interval: Post every N hours
    - fixed: Post at specific times each day
    - random: Post at random times within a window
    """

    def __init__(self, settings: "Settings", job_func: Callable) -> None:
        """
        Initialize the scheduler.

        Args:
            settings: Application settings
            job_func: Async function to call on each scheduled job
        """
        self.settings = settings
        self.job_func = job_func
        self.timezone = timezone(settings.schedule.timezone)
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)
        self._is_running = False
        self._last_run: Optional[datetime] = None
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3

        # Connect event listeners
        self.scheduler.add_listener(
            self._on_job_executed, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

    def _on_job_executed(self, event: JobEvent) -> None:
        """Handle job execution events."""
        if event.exception:
            logger.error(
                f"Job {event.job_id} failed with exception: {event.exception}",
                extra={"job_id": event.job_id, "exception": str(event.exception)},
            )
            self._consecutive_failures += 1

            if self._consecutive_failures >= self._max_consecutive_failures:
                logger.critical(
                    f"Job failed {self._consecutive_failures} times consecutively. "
                    "Consider manual intervention."
                )
                self._notify_admin_of_failure(event.exception)
        else:
            logger.info(f"Job {event.job_id} executed successfully")
            self._consecutive_failures = 0
            self._last_run = datetime.now(self.timezone)

    def _notify_admin_of_failure(self, exception: Optional[Exception]) -> None:
        """Notify admin about job failures (placeholder for actual notification)."""
        # This will be implemented to send Telegram message to admin
        logger.warning(
            f"Admin notification: Job failed. Exception: {exception}"
        )

    def _setup_interval_trigger(self) -> None:
        """Set up interval-based scheduling."""
        interval_hours = self.settings.schedule.interval_hours
        logger.info(f"Setting up interval trigger: every {interval_hours} hours")

        self.scheduler.add_job(
            self.job_func,
            trigger=IntervalTrigger(hours=interval_hours),
            id="post_job",
            name="Generate and publish post",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,  # 1 hour grace period for missed jobs
        )

    def _setup_fixed_trigger(self) -> None:
        """Set up fixed-time scheduling using cron."""
        times = self.settings.schedule.fixed_times
        logger.info(f"Setting up fixed time trigger: {times}")

        for i, time_str in enumerate(times):
            hour, minute = map(int, time_str.split(":"))

            self.scheduler.add_job(
                self.job_func,
                trigger=CronTrigger(
                    hour=hour,
                    minute=minute,
                    timezone=self.timezone,
                ),
                id=f"post_job_{i}",
                name=f"Generate and publish post at {time_str}",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=1800,  # 30 minutes grace period
            )

    def _setup_random_trigger(self) -> None:
        """
        Set up random-time scheduling.

        Posts at random times within the configured window.
        Uses a dynamic approach where each job schedules the next random job.
        """
        window_start = self.settings.schedule.random_window_start
        window_end = self.settings.schedule.random_window_end

        start_hour, start_minute = map(int, window_start.split(":"))
        end_hour, end_minute = map(int, window_end.split(":"))

        logger.info(
            f"Setting up random trigger: between {window_start} and {window_end}"
        )

        # Schedule initial job
        self._schedule_next_random_job(start_hour, start_minute, end_hour, end_minute)

    def _schedule_next_random_job(
        self,
        start_hour: int,
        start_minute: int,
        end_hour: int,
        end_minute: int,
    ) -> None:
        """Schedule the next random job within the window."""
        # Calculate random time within window
        now = datetime.now(self.timezone)

        # Convert window to minutes from midnight
        start_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute

        # Generate random time
        random_minutes = random.randint(start_minutes, end_minutes)
        random_hour = random_minutes // 60
        random_minute = random_minutes % 60

        # Create datetime for today
        run_time = now.replace(
            hour=random_hour,
            minute=random_minute,
            second=0,
            microsecond=0,
        )

        # If time has passed today, schedule for tomorrow
        if run_time <= now:
            run_time += timedelta(days=1)

        logger.info(f"Scheduling next random post for: {run_time}")

        # Remove existing random job if any
        try:
            self.scheduler.remove_job("post_job_random")
        except Exception:
            pass

        # Add new job
        self.scheduler.add_job(
            self._random_job_wrapper,
            trigger="date",
            run_date=run_time,
            id="post_job_random",
            name=f"Random post at {run_time.strftime('%H:%M')}",
            kwargs={
                "start_hour": start_hour,
                "start_minute": start_minute,
                "end_hour": end_hour,
                "end_minute": end_minute,
            },
        )

    async def _random_job_wrapper(
        self,
        start_hour: int,
        start_minute: int,
        end_hour: int,
        end_minute: int,
    ) -> None:
        """Wrapper for random jobs that schedules the next job after execution."""
        try:
            await self.job_func()
        finally:
            # Schedule next random job
            self._schedule_next_random_job(
                start_hour, start_minute, end_hour, end_minute
            )

    def setup(self) -> None:
        """Set up the scheduler based on configuration."""
        schedule_type = self.settings.schedule.type

        logger.info(f"Setting up scheduler with type: {schedule_type}")

        if schedule_type == "interval":
            self._setup_interval_trigger()
        elif schedule_type == "fixed":
            self._setup_fixed_trigger()
        elif schedule_type == "random":
            self._setup_random_trigger()
        else:
            raise ValueError(f"Unknown schedule type: {schedule_type}")

        logger.info("Scheduler setup complete")

    def start(self) -> None:
        """Start the scheduler."""
        if self._is_running:
            logger.warning("Scheduler is already running")
            return

        self.setup()
        self.scheduler.start()
        self._is_running = True
        logger.info(
            f"Scheduler started. Next jobs: "
            f"{[job.next_run_time for job in self.scheduler.get_jobs()]}"
        )

    def stop(self, wait: bool = True) -> None:
        """
        Stop the scheduler.

        Args:
            wait: Whether to wait for running jobs to complete
        """
        if not self._is_running:
            logger.warning("Scheduler is not running")
            return

        self.scheduler.shutdown(wait=wait)
        self._is_running = False
        logger.info("Scheduler stopped")

    def pause(self) -> None:
        """Pause the scheduler."""
        self.scheduler.pause()
        logger.info("Scheduler paused")

    def resume(self) -> None:
        """Resume the scheduler."""
        self.scheduler.resume()
        logger.info("Scheduler resumed")

    def get_next_run_times(self) -> list[dict]:
        """
        Get the next scheduled run times.

        Returns:
            List of dictionaries with job info and next run time
        """
        jobs = self.scheduler.get_jobs()
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in jobs
            if job.next_run_time
        ]

    async def run_job_now(self) -> None:
        """Manually trigger a job execution immediately."""
        logger.info("Manually triggering job execution")
        try:
            await self.job_func()
            logger.info("Manual job execution completed")
        except Exception as e:
            logger.exception(f"Manual job execution failed: {e}")
            raise

    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._is_running

    def get_status(self) -> dict:
        """
        Get scheduler status information.

        Returns:
            Dictionary with scheduler status details
        """
        return {
            "is_running": self._is_running,
            "schedule_type": self.settings.schedule.type,
            "timezone": str(self.timezone),
            "next_runs": self.get_next_run_times(),
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "consecutive_failures": self._consecutive_failures,
        }
