"""
Core constants for TG AI Poster.

Centralized location for all magic numbers, thresholds, and configuration defaults.
This module provides named constants grouped by domain for better maintainability.
"""

from __future__ import annotations

# =============================================================================
# POST CONTENT LIMITS
# =============================================================================

# Telegram message limits
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_MAX_CAPTION_LENGTH = 1024

# Post structure limits
MIN_TITLE_LENGTH = 20
MAX_TITLE_LENGTH = 120
MAX_TITLE_LENGTH_WITH_EMOJI = 120  # Title with 1-2 emojis

MIN_BODY_LENGTH = 200
MAX_BODY_LENGTH = 1500
IDEAL_BODY_LENGTH = 800

MIN_HOOK_LENGTH = 50
MAX_HOOK_LENGTH = 200

MIN_TLDR_LENGTH = 20
MAX_TLDR_LENGTH = 200

MIN_SUMMARY_LENGTH = 50
MAX_SUMMARY_LENGTH = 500

# Content element counts
MIN_EMOJIS_PER_POST = 1
MAX_EMOJIS_PER_POST = 20
IDEAL_EMOJIS_PER_POST = 3

MIN_HASHTAGS_PER_POST = 1
MAX_HASHTAGS_PER_POST = 10
IDEAL_HASHTAGS_PER_POST = 3

MIN_KEY_FACTS = 4
MAX_KEY_FACTS = 6
MAX_KEY_FACT_LENGTH = 150

MIN_SOURCES_REQUIRED = 2
MAX_SOURCES_PER_POST = 5

MIN_USEFUL_LINKS = 0
MAX_USEFUL_LINKS = 3

# =============================================================================
# QUALITY SCORING
# =============================================================================

# Quality score thresholds
MIN_QUALITY_SCORE = 60
QUALITY_SCORE_REGENERATION_THRESHOLD = 50
EXCELLENT_QUALITY_SCORE = 85

# Editor score thresholds
MIN_EDITOR_SCORE = 70
EDITOR_SCORE_REGENERATION_THRESHOLD = 60

# Verification score thresholds
MIN_VERIFICATION_SCORE = 60
EXCELLENT_VERIFICATION_SCORE = 80
MIN_CREDIBILITY_SCORE = 70

# Confidence thresholds
MIN_CONFIDENCE_SCORE = 0.5
HIGH_CONFIDENCE_SCORE = 0.8
PUBLICATION_READY_CONFIDENCE = 0.75

# Similarity thresholds (for duplicate detection)
SIMILARITY_THRESHOLD = 0.85
SIMILARITY_WARNING_THRESHOLD = 0.70
ENTITY_SIMILARITY_THRESHOLD = 0.82

# =============================================================================
# CONTENT FILTERING
# =============================================================================

# Content filter scoring
BASE_RELEVANCE_SCORE = 50.0
MIN_FILTER_SCORE = 30.0
KEYWORD_MATCH_SCORE = 5.0
MAX_KEYWORD_SCORE = 30.0
TITLE_QUALITY_SCORE = 5.0
SUMMARY_QUALITY_SCORE = 5.0
RECENCY_MAX_BONUS = 15.0
TAGS_MAX_BONUS = 10.0

# Topic selection
TOPIC_SIMILARITY_THRESHOLD = 0.6
FORBIDDEN_TOPIC_DAYS = 7

# =============================================================================
# SOURCE VERIFICATION
# =============================================================================

# Trust score tiers
TIER1_TRUST_SCORE = 100
TIER2_TRUST_SCORE = 80
TIER3_TRUST_SCORE = 50
DEFAULT_TRUST_SCORE = 40
MIN_TRUST_SCORE = 60

# Cross-reference scoring
CROSS_REF_BONUS_PER_SOURCE = 5
MAX_CROSS_REF_BONUS = 15

# Content similarity for cross-reference
CROSS_REFERENCE_SIMILARITY_THRESHOLD = 0.3

# =============================================================================
# PIPELINE TIMING & LIMITS
# =============================================================================

# Generation settings
MAX_GENERATION_ATTEMPTS = 3
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 2
RETRY_MAX_DELAY_SECONDS = 30

# Rate limiting
DEFAULT_FETCH_TIMEOUT = 30
DEFAULT_API_TIMEOUT = 60
CLI_TIMEOUT = 180

# Temperature presets by post type
TEMPERATURE_FACTUAL = 0.15  # For breaking news, tool_roundup
TEMPERATURE_ANALYTICAL = 0.4  # For deep_dive, analysis
TEMPERATURE_DEFAULT = 0.2

# Max tokens by task
MAX_TOKENS_POST_GENERATION = 2000
MAX_TOKENS_TOPIC_SELECTION = 500
MAX_TOKENS_EDITOR_REVIEW = 800
MAX_TOKENS_QUALITY_CHECK = 500

# =============================================================================
# SCHEDULING
# =============================================================================

# Posting limits
MAX_DAILY_POSTS = 12
MIN_INTERVAL_MINUTES = 30
MAX_INTERVAL_HOURS = 24

# Default posting times
DEFAULT_POSTING_TIMES = ["09:30", "14:00", "20:00"]

# Random window defaults
DEFAULT_WINDOW_START = "10:00"
DEFAULT_WINDOW_END = "22:00"

# =============================================================================
# DATABASE & STORAGE
# =============================================================================

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Retention
DEFAULT_AUDIT_RETENTION_DAYS = 90
DRAFT_AUTO_CLEANUP_DAYS = 30
TOPIC_FORBIDDEN_DAYS = 7
VERSION_HISTORY_DAYS = 30

# Version limits
MAX_POST_VERSIONS = 50

# =============================================================================
# A/B TESTING
# =============================================================================

# A/B test settings
DEFAULT_TRAFFIC_SPLIT = 0.5
MIN_AB_SAMPLE_SIZE = 100
AB_CONFIDENCE_THRESHOLD = 0.95

# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

# LLM circuit breaker
LLM_FAILURE_THRESHOLD = 5
LLM_RECOVERY_TIMEOUT_SECONDS = 60.0

# Telegram circuit breaker
TELEGRAM_FAILURE_THRESHOLD = 10
TELEGRAM_RECOVERY_TIMEOUT_SECONDS = 30.0

# Source collection circuit breaker
SOURCES_FAILURE_THRESHOLD = 3
SOURCES_RECOVERY_TIMEOUT_SECONDS = 120.0

# =============================================================================
# LEARNING & FEEDBACK
# =============================================================================

# Style learning
STYLE_UPDATE_INTERVAL_DAYS = 7
MIN_REACTIONS_TO_LEARN = 5
TOP_POSTS_IN_CONTEXT = 5
STYLE_PROFILE_MIN_POSTS = 10

# Feedback loop
ENGAGEMENT_UPDATE_INTERVAL_HOURS = 6
ENGAGEMENT_TRACKING_HOURS = 48

# =============================================================================
# CONTENT RECYCLING (Feature 1)
# =============================================================================

# Recycling thresholds
RECYCLING_MIN_AGE_DAYS = 30
RECYCLING_MIN_ENGAGEMENT_SCORE = 0.7
RECYCLING_CONTENT_REWRITE_THRESHOLD = 0.4  # 40% must be rewritten

# =============================================================================
# NARRATIVE ARCS (Feature 5)
# =============================================================================

# Story settings
MAX_ARC_LENGTH = 10
DEFAULT_ARC_CHAPTERS = 5

# =============================================================================
# HASHTAG INTELLIGENCE (Feature 6)
# =============================================================================

# Hashtag tracking
HASHTAG_MIN_IMPRESSIONS = 100
HASHTAG_BLACKLIST_THRESHOLD = 0.1  # Engagement rate below this

# =============================================================================
# WATCHDOG (Feature 20)
# =============================================================================

# Monitoring thresholds
WATCHDOG_ALERT_THRESHOLD_HOURS = 6
WATCHDOG_CHECK_INTERVAL_MINUTES = 30
WATCHDOG_SELF_TEST_INTERVAL_MINUTES = 60

# =============================================================================
# HTTP & API
# =============================================================================

# User agents
DEFAULT_USER_AGENT = "TG-AI-Poster/1.0"

# API endpoints
HN_TOPSTORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL_TEMPLATE = "https://hacker-news.firebaseio.com/v0/item/{}.json"
PRODUCTHUNT_RSS_URL = "https://www.producthunt.com/feed"

# API provider URLs
GLM_API_URL = "https://api.z.ai/api/paas/v4"
OPENAI_API_URL = "https://api.openai.com/v1"
CLAUDE_API_URL = "https://api.anthropic.com"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1"

# =============================================================================
# LOGGING & MONITORING
# =============================================================================

# Log levels
LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"

# Health check
HEALTH_CHECK_TIMEOUT_SECONDS = 10

# =============================================================================
# QUALITY RULES THRESHOLDS
# =============================================================================

# Sentence structure
MAX_SENTENCE_WORDS = 25
IDEAL_AVG_SENTENCE_WORDS = 15
MAX_SENTENCE_LENGTH_CHARS = 200

# Voice analysis
MIN_ACTIVE_VOICE_RATIO = 0.7
MAX_PASSIVE_CONSTRUCTIONS = 2

# Readability
MAX_AVG_SENTENCE_LENGTH_WORDS = 18
MAX_WORD_REPETITION_IN_WINDOW = 3
WORD_REPETITION_WINDOW_SIZE = 100

# =============================================================================
# SENTIMENT & EMOTIONS (Feature 9)
# =============================================================================

# Emotional dimensions for scoring
EMOTIONAL_DIMENSIONS = [
    "curiosity",
    "urgency",
    "empathy",
    "inspiration",
    "humor",
    "controversy",
]

# =============================================================================
# API SERVER (Feature 15)
# =============================================================================

# API defaults
API_DEFAULT_PORT = 8080
API_DEFAULT_HOST = "0.0.0.0"
API_KEY_HEADER = "X-API-Key"

# =============================================================================
# MEDIA GENERATION (Feature 11)
# =============================================================================

# Image generation
MAX_IMAGE_PROMPT_LENGTH = 500
IMAGE_VARIANTS_COUNT = 3

# Composition quality thresholds
MIN_CONTRAST_RATIO = 0.3
RULE_OF_THIRDS_TOLERANCE = 0.15

# =============================================================================
# BACKUP
# =============================================================================

# Backup defaults
DEFAULT_BACKUP_DIR = "./backups"
BACKUP_FILE_PREFIX = "tg_poster_backup"
BACKUP_FILE_EXTENSION = ".tar.gz"

# =============================================================================
# STATUS CONSTANTS
# =============================================================================


class PostStatus:
    """Post status lifecycle constants."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    NEEDS_REVISION = "needs_revision"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


class PostType:
    """Post type constants."""

    BREAKING = "breaking"
    DEEP_DIVE = "deep_dive"
    TOOL_ROUNDUP = "tool_roundup"
    ANALYSIS = "analysis"


class SourceType:
    """Source type constants."""

    RSS = "rss"
    API = "api"
    MANUAL = "manual"
    GENERATED = "generated"
    PUBLISHED = "published"


class Recommendation:
    """Verification recommendation constants."""

    PUBLISH = "publish"
    NEEDS_REVIEW = "needs_review"
    REJECT = "reject"


class EntityType:
    """Entity type constants for extraction."""

    COMPANY = "company"
    MODEL = "model"
    RESEARCHER = "researcher"
    BENCHMARK = "benchmark"
    TECHNOLOGY = "technology"
    METRIC = "metric"
