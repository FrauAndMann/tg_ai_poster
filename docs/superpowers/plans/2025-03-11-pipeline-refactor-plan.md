# TG AI Poster: Implementation Plan

**Date:** 2025-03-11
**Design Spec:** [2025-03-11-pipeline-refactor-design.md](../docs/superpowers/specs/2025-03-11-pipeline-refactor-design.md)

---

## Overview

This plan transforms TG AI Poster from a monolithic orchestrator to an event-driven pipeline with plugin architecture for media providers and formatters.

**Total Estimated Tasks:** 87
**Estimated Files Changed:** ~25
**Estimated Files Created:** ~15

---

## Phase 1: Foundation (Events + Domain)

### 1.1 Create Event System
**File:** `core/events.py` (NEW)
**Dependencies:** `pyee>=11.0.0`

Tasks:
- [ ] Add `pyee` to requirements.txt
- [ ] Create `EventType` enum with all pipeline events
- [ ] Create `PipelineEvent` dataclass
- [ ] Create global `event_bus` singleton
- [ ] Write unit tests for event emission/handling

### 1.2 Create Domain Models
**Files:** `domain/` (NEW DIRECTORY)

Tasks:
- [ ] Create `domain/__init__.py`
- [ ] Create `domain/post.py` with `PostType`, `PostTypeConfig`, `PostContent`, `PostMetadata`, `Post`
- [ ] Create `domain/source.py` with `Source` value object
- [ ] Create `domain/media.py` with `Media` value object
- [ ] Create `POST_TYPE_CONFIGS` dictionary
- [ ] Write unit tests for domain models

### 1.3 Update Configuration
**File:** `core/config.py` (MODIFY)

Tasks:
- [ ] Add `PostTypeSettings` dataclass
- [ ] Add `MediaSettings` dataclass
- [ ] Add `FormattingSettings` dataclass
- [ ] Add `post_types`, `media`, `formatting` fields to `Settings`
- [ ] Add `get_post_type_config()` method
- [ ] Add `select_random_post_type()` method
- [ ] Update `config.yaml` with new sections
- [ ] Write tests for config loading

---

## Phase 2: Pipeline Refactor

### 2.1 Create Pipeline Stages
**Directory:** `pipeline/stages/` (NEW)

Tasks:
- [ ] Create `pipeline/stages/__init__.py`
- [ ] Create `pipeline/stages/collection.py` - wrap existing SourceCollector
- [ ] Create `pipeline/stages/selection.py` - wrap existing TopicSelector
- [ ] Create `pipeline/stages/generation.py` - wrap existing LLMGenerator
- [ ] Create `pipeline/stages/review.py` - wrap existing EditorReviewer
- [ ] Create `pipeline/stages/quality.py` - wrap existing QualityChecker
- [ ] Create `pipeline/stages/media.py` - NEW media fetching
- [ ] Create `pipeline/stages/formatting.py` - wrap existing formatter
- [ ] Write unit tests for each stage

### 2.2 Create Pipeline Coordinator
**File:** `pipeline/coordinator.py` (NEW)

Tasks:
- [ ] Create `PipelineCoordinator` class
- [ ] Implement event subscription setup
- [ ] Implement async state machine for stage transitions
- [ ] Implement `_on_*` handlers for each stage event
- [ ] Implement `run()` method with Future-based completion
- [ ] Write integration tests for coordinator

### 2.3 Deprecate Old Orchestrator
**File:** `pipeline/orchestrator.py` (MODIFY)

Tasks:
- [ ] Add deprecation warning to `PipelineOrchestrator`
- [ ] Update imports in `main.py` to use coordinator
- [ ] Keep old file for rollback capability

---

## Phase 3: Media Plugin System

### 3.1 Create Media Plugin Interface
**Directory:** `plugins/media/` (NEW)

Tasks:
- [ ] Create `plugins/__init__.py`
- [ ] Create `plugins/media/__init__.py`
- [ ] Create `plugins/media/base.py` with `MediaProvider` interface
- [ ] Create `MediaSearchResult` dataclass
- [ ] Write unit tests for interface compliance

### 3.2 Implement Unsplash Provider
**File:** `plugins/media/unsplash.py` (NEW)

Tasks:
- [ ] Create `UnsplashProvider` class
- [ ] Implement `search()` method with httpx
- [ ] Implement `get_random()` method
- [ ] Implement `_extract_keywords()` helper
- [ ] Implement rate limit tracking
- [ ] Add `UNSPLASH_ACCESS_KEY` to `.env.example`
- [ ] Write unit tests with mocked API responses
- [ ] Write integration tests (optional, requires API key)

### 3.3 Implement Pexels Provider (Fallback)
**File:** `plugins/media/pexels.py` (NEW)

Tasks:
- [ ] Create `PexelsProvider` class following same pattern
- [ ] Implement all interface methods
- [ ] Add `PEXELS_API_KEY` to `.env.example`
- [ ] Write unit tests

### 3.4 Create Media Stage
**File:** `pipeline/stages/media.py` (MODIFY - created in Phase 2)

Tasks:
- [ ] Import media providers
- [ ] Implement provider fallback chain (sorted by remaining rate limit)
- [ ] Emit `MEDIA_FETCHED` event on success
- [ ] Handle provider failures gracefully
- [ ] Write tests for media stage

---

## Phase 4: Formatting Plugin

### 4.1 Create Formatter Interface
**Directory:** `plugins/formatters/` (NEW)

Tasks:
- [ ] Create `plugins/formatters/__init__.py`
- [ ] Create `plugins/formatters/base.py` with `PostFormatter` interface

### 4.2 Migrate Telegram Formatter
**File:** `plugins/formatters/telegram.py` (NEW)

Tasks:
- [ ] Extract formatting logic from `pipeline/formatter.py`
- [ ] Create `TelegramFormatter` class implementing interface
- [ ] Implement `format()` method
- [ ] Implement `format_sources()` method with clickable links
- [ ] Implement `_escape()` helper (MarkdownV2)
- [ ] Implement `validate()` method
- [ ] Write comprehensive unit tests

### 4.3 Update Formatting Stage
**File:** `pipeline/stages/formatting.py` (MODIFY)

Tasks:
- [ ] Import `TelegramFormatter` from plugins
- [ ] Use formatter plugin instead of direct formatter
- [ ] Add formatted content to event data

---

## Phase 5: Database Migration

### 5.1 Update Post Model
**File:** `memory/models.py` (MODIFY)

Tasks:
- [ ] Add `media_url` field (String(1000), nullable)
- [ ] Add `media_source` field (String(50), nullable)
- [ ] Add `media_photographer` field (String(200), nullable)
- [ ] Add `sources_json` field (Text, nullable)
- [ ] Update `to_dict()` method with new fields

### 5.2 Create Alembic Migration
**File:** `migrations/versions/xxx_add_media_fields.py` (NEW)

Tasks:
- [ ] Create migration with `upgrade()` function
- [ ] Add all new columns
- [ ] Migrate existing `source`/`source_url` to `sources_json`
- [ ] Create `downgrade()` function
- [ ] Test migration on copy of database

### 5.3 Update PostStore
**File:** `memory/post_store.py` (MODIFY)

Tasks:
- [ ] Add `create_with_media()` method
- [ ] Add `get_by_type()` method
- [ ] Update existing methods to handle new fields

### 5.4 Create Domain Mapper
**File:** `memory/mappers.py` (NEW)

Tasks:
- [ ] Create `PostMapper` class
- [ ] Implement `to_domain()` static method
- [ ] Implement `to_model()` static method
- [ ] Write unit tests for mapper

---

## Phase 6: Integration

### 6.1 Create PipelineResult
**File:** `core/result.py` (NEW)

Tasks:
- [ ] Create `PipelineResult` dataclass
- [ ] Add all required fields per design spec
- [ ] Write tests

### 6.2 Wire Components in main.py
**File:** `main.py` (MODIFY)

Tasks:
- [ ] Import new coordinator
- [ ] Initialize event bus
- [ ] Initialize media providers based on config
- [ ] Initialize formatter plugin
- [ ] Wire all stages to coordinator
- [ ] Update CLI arguments if needed

### 6.3 Update Publisher for Media
**File:** `publisher/bot_publisher.py` (MODIFY)

Tasks:
- [ ] Update `send_post` to check for media
- [ ] Call `send_post_with_image` when media exists
- [ ] Handle media attribution in logs

### 6.4 End-to-End Testing
Tasks:
- [ ] Create `tests/integration/test_pipeline_flow.py`
- [ ] Test full pipeline with mocked LLM
- [ ] Test full pipeline with mocked media providers
- [ ] Test event flow end-to-end
- [ ] Test error recovery

### 6.5 Documentation Update
Tasks:
- [ ] Update `README.md` with new architecture
- [ ] Update `USER_GUIDE.md` with new configuration options
- [ ] Add API keys setup instructions
- [ ] Update `CLAUDE.md` with new module structure

---

## Dependency Matrix

```
Phase 1 (Events + Domain)
    └── Phase 2 (Pipeline Stages + Coordinator)
            └── Phase 3 (Media Plugins)
                    └── Phase 4 (Formatter Plugin)
                            └── Phase 5 (Database)
                                └── Phase 6 (Integration)
```

---

## Rollback Strategy

Each phase can be rolled back independently:
- **Phase 1:** Remove `domain/` and `core/events.py`, restore original imports
- **Phase 2:** Keep old `PipelineOrchestrator`, update `main.py` imports
- **Phase 3-4:** Remove `plugins/`, stages continue working without media
- **Phase 5:** Run Alembic downgrade
- **Phase 6:** Revert `main.py` changes

---

## Verification Checkpoints

| Phase | Verification |
|-------|---------------|
| 1 | All domain tests pass, event bus works |
| 2 | Coordinator runs stages in order, events fire correctly |
| 3 | Media providers return images, fallback chain works |
| 4 | Posts format correctly, links are clickable |
| 5 | Migration runs without errors, new fields populated |
| 6 | Full pipeline runs end-to-end, posts publish with media |

---

## Task Summary

| Phase | Tasks | Files |
|-------|-------|-------|
| 1 | 15 | 4 new, 1 modify |
| 2 | 18 | 8 new, 2 modify |
| 3 | 15 | 4 new |
| 4 | 10 | 3 new, 1 modify |
| 5 | 12 | 2 new, 2 modify |
| 6 | 17 | 1 new, 4 modify |
| **Total** | **87** | **22 new, 10 modify** |
