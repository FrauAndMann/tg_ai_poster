"""
FastAPI Webhook & API Server - External interface for TG AI Poster.

Exposes health, posts, analytics endpoints with API key authentication.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from core.logger import get_logger
from core.config import get_settings

logger = get_logger(__name__)


# Pydantic models for API
class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    database: bool = True
    llm_connected: bool = True
    scheduler_running: bool = True
    last_post: Optional[datetime] = None
    uptime_seconds: float = 0.0


    version: str = "1.0.0"


class PostResponse(BaseModel):
    """Single post response."""

    id: int
    content: str
    topic: str
    published_at: datetime
    views: int = 0
    engagement_score: float = 0.0
    status: str = "published"


    quality_score: float = 0.0


class PostsListResponse(BaseModel):
    """Paginated posts list."""

    posts: list[PostResponse]
    total: int
    page: int
    page_size: int


class JobResponse(BaseModel):
    """Job status response."""

    job_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class AnalyticsSummary(BaseModel):
    """Analytics summary response."""

    period: str
    total_posts: int
    avg_engagement: float
    top_performing_topics: list[str]
    quality_distribution: dict[str, int]
    cost_summary: dict[str, float]


# API Server
class APIServer:
    """
    FastAPI server for TG AI Poster.

    Endpoints:
    - GET /health - System health check
    - GET /posts - List posts
    - POST /posts/generate - Generate post
    - GET /jobs/{job_id} - Job status
    - POST /approve/{post_id} - Approve post
    - GET /analytics/summary - Analytics summary
    - POST /channels/{channel_id}/pause - Pause channel
    """

    def __init__(
        self,
        api_key: str,
        pipeline_orchestrator: Any,
        post_store: Any,
    ) -> None:
        """Initialize API server."""
        self.api_key = api_key
        self.orchestrator = pipeline_orchestrator
        self.post_store = post_store
        self._jobs: dict[str, JobResponse] = {}
        self._app: Optional[FastAPI] = None
        self._start_time: Optional[datetime] = None
    def create_app(self) -> FastAPI:
        """Create FastAPI application."""
        app = FastAPI(
            title="TG AI Poster API",
            description="API for managing Telegram posting automation",
            version="1.0.0",
        )
        # Add routes
        app.add_api_route("/health", methods=["GET"])(self.health_endpoint)
        app.add_api_route("/posts", methods=["GET"])(self.list_posts_endpoint)
        app.add_api_route("/posts/generate", methods=["POST"])(self.generate_post_endpoint)
        app.add_api_route("/jobs/{job_id}", methods=["GET"])(self.job_status_endpoint)
        app.add_api_route("/approve/{post_id}", methods=["POST"])(self.approve_post_endpoint)
        app.add_api_route("/analytics/summary", methods=["GET"])(self.analytics_summary_endpoint)
        app.add_api_route("/channels/{channel_id}/pause", methods=["POST"])(self.pause_channel_endpoint)
        # Add middleware
        app.middleware("http")(self.verify_api_key)
        return app
    async def start(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        """Start the API server."""
        import uvicorn
        self._app = self.create_app()
        self._start_time = datetime.now()
        config = uvicorn.Config(app=app, host=host, port=port)
        await config.setup()
        logger.info("API server started on %s:%d", host, port)
    async def stop(self) -> None:
        """Stop the API server."""
        if self._app:
            await self._app.shutdown()
        logger.info("API server stopped")
    # Authentication dependency
    def verify_api_key(
        self,
        credentials: HTTPAuthorizationCredentials = Depends,
    ):
        """Verify API key."""
        settings = get_settings()
        expected_key = settings.api.get("api_key", "")
        if not expected_key:
            raise HTTPException(status_code=401, detail="API key not configured")
        if credentials.credentials != expected_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return credentials.credentials
    # Endpoints
    async def health_endpoint(self) -> HealthResponse:
        """Health check endpoint."""
        # Check database
        db_healthy = True
        if self.post_store:
            try:
                await self.post_store.count()
            except Exception:
                db_healthy = False
        # Calculate uptime
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()
        return HealthResponse(
            status="ok" if db_healthy else "degraded",
            database=db_healthy,
            llm_connected=True,  # Would need actual check
            scheduler_running=True,
            uptime_seconds=uptime,
        )
    async def list_posts_endpoint(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> PostsListResponse:
        """List posts endpoint."""
        offset = (page - 1) * page_size
        if self.post_store:
            posts = await self.post_store.list(limit=page_size, offset=offset)
            total = await self.post_store.count()
            return PostsListResponse(
                posts=[
                    PostResponse(
                        id=p.id,
                        content=p.content,
                        topic=p.topic,
                        published_at=p.published_at,
                        views=p.views,
                        engagement_score=p.engagement_score,
                        status=p.status,
                        quality_score=p.quality_score,
                    )
                    for p in posts
                ],
                total=total,
                page=page,
                page_size=page_size,
            )
        return PostsListResponse(posts=[], total=0, page=page, page_size=page_size)
    async def generate_post_endpoint(self, background_tasks: bool = False) -> JobResponse:
        """Generate post endpoint."""
        if not self.orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not configured")
        import uuid
        job_id = str(uuid.uuid4())
        # Create job
        job = JobResponse(
            job_id=job_id,
            status="pending",
            created_at=datetime.now(),
        )
        self._jobs[job_id] = job
        # Run generation in background
        if background_tasks:
            asyncio.create_task(self._run_generation(job_id))
        return job
    async def _run_generation(self, job_id: str) -> None:
        """Run post generation."""
        job = self._jobs[job_id]
        try:
            job.status = "running"
            result = await self.orchestrator.run_once()
            job.status = "completed"
            job.completed_at = datetime.now()
            job.result = result
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            logger.error("Generation job %s failed: %s", job_id, e)
    async def job_status_endpoint(self, job_id: str) -> JobResponse:
        """Get job status endpoint."""
        if job_id not in self._jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        return self._jobs[job_id]
    async def approve_post_endpoint(self, post_id: int) -> dict:
        """Approve post endpoint."""
        if not self.post_store:
            raise HTTPException(status_code=503, detail="Post store not configured")
        post = await self.post_store.get(post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        # Update post status
        post.status = "approved"
        await self.post_store.update(post)
        return {"status": "approved", "post_id": post_id}
    async def analytics_summary_endpoint(self) -> AnalyticsSummary:
        """Analytics summary endpoint."""
        if not self.post_store:
            return AnalyticsSummary(
                period="7d",
                total_posts=0,
                avg_engagement=0.0,
                top_performing_topics=[],
                quality_distribution={},
                cost_summary={},
            )
        # Get analytics for last 7 days
        posts = await self.post_store.list(limit=100)
        recent = [
            p for p in posts
            if p.published_at and (datetime.now() - p.published_at).days <= 7
        ]
        avg_engagement = sum(p.engagement_score for p in recent) / len(recent) if recent else 0
        # Topic distribution
        topics = {}
        for p in recent:
            if p.topic:
                topics[p.topic] = topics.get(p.topic, 0) + 1
        # Quality distribution
        quality_dist = {
            "high": len([p for p in recent if p.quality_score >= 80]),
            "medium": len([p for p in recent if 40 <= p.quality_score < 80]),
            "low": len([p for p in recent if p.quality_score < 40]),
        }
        return AnalyticsSummary(
            period="7d",
            total_posts=len(recent),
            avg_engagement=avg_engagement,
            top_performing_topics=sorted(topics.keys(), key=lambda x: x[1], reverse=True)[:5],
            quality_distribution=quality_dist,
            cost_summary={},  # Would integrate with actual cost tracking
        )
    async def pause_channel_endpoint(self, channel_id: str) -> dict:
        """Pause channel endpoint."""
        # This would integrate with multi-channel manager
        return {"status": "paused", "channel_id": channel_id}


# Configuration schema
API_SERVER_CONFIG_SCHEMA = {
    "api": {
        "enabled": {
            "type": "bool",
            "default": False,
            "description": "Enable API server",
        },
        "api_key": {
            "type": "str",
            "default": "",
            "secret": True,
            "description": "API key for authentication",
        },
        "host": {
            "type": "str",
            "default": "0.0.0.0",
            "description": "Host to bind to",
        },
        "port": {
            "type": "int",
            "default": 8080,
            "description": "Port to listen on",
        },
    }
}
