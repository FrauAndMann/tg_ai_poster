# Phase 2 Implementation Plan

**Version:** 1.0
**Date:** 2025-03-15
**Status:** Ready for Execution

---

## Overview

This plan details the step-by-step implementation of Phase 2 features for TG AI Poster.

**Total Duration:** 8 weeks
**Features:** 8 major features
**Priority:** Content Quality > Analytics > Sources > Infrastructure

---

## Phase 2.1: Thread Mode (Week 1-2)

### Goal
Enable automatic splitting of long-form content into thread (thread/tlaps) format.

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `memory/models.py` | Modify | Add Thread, update Post |
| `pipeline/thread_builder.py` | Create | ThreadBuilder class |
| `pipeline/thread_publisher.py` | Create | Sequential publishing |
| `pipeline/orchestrator.py` | Modify | Thread integration |
| `config.yaml` | Modify | Thread configuration |
| `tests/test_thread.py` | Create | Unit tests |

### Implementation Steps

#### Step 1: Database Models (Day 1)
```python
# 1. Add Thread model
# 2. Add thread_id, thread_position, is_thread_part to Post
# 3. Create migration script
```

#### Step 2: ThreadBuilder Core (Day 2-3)
```python
# 1. Implement ParagraphSplitter
# 2. Implement SentenceSplitter
# 3. Implement ThreadBuilder.should_create_thread()
# 4. Implement ThreadBuilder.build_thread()
```

#### Step 3: AI-Powered Splitting (Day 4)
```python
# 1. Implement AIContentSplitter
# 2. Add LLM prompt for logical breaks
# 3. Fallback to force split
```

#### Step 4: Thread Publishing (Day 5)
```python
# 1. Implement ThreadPublisher
# 2. Handle rate limiting
# 3. Failure recovery
```

#### Step 5: Integration & Testing (Day 6-7)
```python
# 1. Update orchestrator
# 2. Add thread detection
# 3. Write tests
# 4. Manual testing
```

### Acceptance Criteria

- [ ] Content > 2000 chars automatically splits
- [ ] Thread navigation (X/Y) added correctly
- [ ] Posts publish sequentially with delay
- [ ] Failure at any point is recoverable
- [ ] Tests pass with > 90% coverage

---

## Phase 2.2: Smart Queue Management (Week 2-3)

### Goal
Intelligent post queue with priorities, expiration, and conflict resolution.

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `memory/models.py` | Modify | Add PostQueue, QueueStats |
| `pipeline/queue_manager.py` | Create | QueueManager class |
| `admin_bot/handlers/queue.py` | Create | Queue commands |
| `config.yaml` | Modify | Queue configuration |
| `tests/test_queue.py` | Create | Unit tests |

### Implementation Steps

#### Step 1: Database Models (Day 1)
```python
# 1. Add PostQueue model
# 2. Add QueueStats model
# 3. Create migration
```

#### Step 2: QueueManager Core (Day 2-3)
```python
# 1. Implement enqueue()
# 2. Implement dequeue()
# 3. Implement peek()
# 4. Priority ordering
```

#### Step 3: Advanced Features (Day 4)
```python
# 1. Implement reprioritize()
# 2. Implement detect_conflicts()
# 3. Implement resolve_conflict()
```

#### Step 4: Expiration & Cleanup (Day 5)
```python
# 1. Implement _cleanup_expired()
# 2. Implement get_stats()
# 3. Health calculation
```

#### Step 5: Admin Integration (Day 6-7)
```python
# 1. Add /queue command
# 2. Add /prioritize command
# 3. Write tests
```

### Acceptance Criteria

- [ ] Posts can be queued with priorities
- [ ] Expired posts are cleaned up
- [ ] Conflicts are detected and resolved
- [ ] Admin can view and manage queue
- [ ] Tests pass with > 90% coverage

---

## Phase 2.3: Engagement Tracker (Week 3-4)

### Goal
Collect and analyze engagement metrics for published posts.

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `memory/models.py` | Modify | Add PostEngagement, EngagementHistory |
| `analytics/__init__.py` | Create | Analytics module |
| `analytics/engagement_tracker.py` | Create | EngagementTracker class |
| `config.yaml` | Modify | Engagement configuration |
| `tests/test_engagement.py` | Create | Unit tests |

### Implementation Steps

#### Step 1: Database Models (Day 1)
```python
# 1. Add PostEngagement model
# 2. Add EngagementHistory model
# 3. Create migration
```

#### Step 2: Engagement Sources (Day 2)
```python
# 1. Implement EngagementSource protocol
# 2. Implement TelegramEngagementSource
# 3. Implement TelethonEngagementSource
```

#### Step 3: Tracker Core (Day 3-4)
```python
# 1. Implement track_post()
# 2. Implement _track_all()
# 3. Score calculations
```

#### Step 4: Alerts & Stats (Day 5)
```python
# 1. Implement _check_alerts()
# 2. Implement get_top_posts()
# 3. Implement get_aggregate_stats()
```

#### Step 5: Integration (Day 6-7)
```python
# 1. Start tracker in main.py
# 2. Track after publishing
# 3. Write tests
```

### Acceptance Criteria

- [ ] Views, reactions, forwards tracked
- [ ] Engagement rate calculated correctly
- [ ] Time-series data stored
- [ ] Alerts generated for notable engagement
- [ ] Tests pass with > 85% coverage

---

## Phase 2.4: Enhanced RSS Parser (Week 4-5)

### Goal
Improved RSS parsing with full-text extraction.

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `memory/models.py` | Modify | Add RSSSource, RSSArticle |
| `pipeline/enhanced_rss_parser.py` | Create | Enhanced parser |
| `pipeline/source_collector.py` | Modify | Use enhanced parser |
| `config.yaml` | Modify | RSS configuration |
| `tests/test_rss_enhanced.py` | Create | Unit tests |

### Implementation Steps

#### Step 1: Database Models (Day 1)
```python
# 1. Add RSSSource model
# 2. Add RSSArticle model
# 3. Create migration
```

#### Step 2: Full-Text Extractor (Day 2)
```python
# 1. Implement FullTextExtractor
# 2. Use readability-lxml
# 3. Error handling
```

#### Step 3: Enhanced Parser (Day 3-4)
```python
# 1. Implement fetch_source()
# 2. Implement _parse_entry()
# 3. Deduplication via hash
```

#### Step 4: Source Management (Day 5)
```python
# 1. Implement get_eligible_sources()
# 2. Error tracking per source
# 3. Auto-disable failing sources
```

#### Step 5: Integration (Day 6-7)
```python
# 1. Replace old parser
# 2. Store articles
# 3. Write tests
```

### Acceptance Criteria

- [ ] Full-text extracted from articles
- [ ] Sources managed in database
- [ ] Duplicates detected
- [ ] Failing sources auto-disabled
- [ ] Tests pass with > 80% coverage

---

## Phase 2.5: Hashtag Analytics (Week 5)

### Goal
Track and analyze hashtag performance.

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `memory/models.py` | Modify | Add HashtagStats, PostHashtag |
| `analytics/hashtag_analyzer.py` | Create | HashtagAnalyzer class |
| `tests/test_hashtags.py` | Create | Unit tests |

### Implementation Steps

#### Step 1: Database Models (Day 1)
```python
# 1. Add HashtagStats model
# 2. Add PostHashtag model
```

#### Step 2: Analyzer Core (Day 2-3)
```python
# 1. Implement record_usage()
# 2. Implement update_performance()
# 3. Score calculation
```

#### Step 3: Recommendations (Day 4-5)
```python
# 1. Implement get_recommendations()
# 2. Implement suggest_for_topic()
# 3. Integration with tracker
```

### Acceptance Criteria

- [ ] Hashtags tracked per post
- [ ] Performance calculated correctly
- [ ] Recommendations generated
- [ ] Tests pass with > 80% coverage

---

## Phase 2.6: Reddit Integration (Week 5-6)

### Goal
Monitor Reddit for trending AI/tech content.

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `sources/__init__.py` | Create | Sources module |
| `sources/reddit_client.py` | Create | RedditClient class |
| `pipeline/source_collector.py` | Modify | Add Reddit source |
| `config.yaml` | Modify | Reddit configuration |
| `.env.example` | Modify | Reddit credentials |
| `tests/test_reddit.py` | Create | Unit tests |

### Implementation Steps

#### Step 1: Reddit Client (Day 1-2)
```python
# 1. Set up PRAW
# 2. Implement get_trending()
# 3. Implement search()
```

#### Step 2: Filtering (Day 3)
```python
# 1. Score filtering
# 2. NSFW filtering
# 3. Deduplication
```

#### Step 3: Integration (Day 4-5)
```python
# 1. Add to source collector
# 2. Convert RedditPost to Article
# 3. Write tests
```

### Acceptance Criteria

- [ ] Reddit posts fetched from subreddits
- [ ] Score filtering works
- [ ] Posts converted to articles
- [ ] Tests pass with > 75% coverage

---

## Phase 2.7: Predictive Analytics (Week 6-7)

### Goal
Predict engagement before publishing.

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `analytics/engagement_predictor.py` | Create | EngagementPredictor class |
| `config.yaml` | Modify | Predictive config |
| `tests/test_predictor.py` | Create | Unit tests |
| `models/` | Create | Model storage directory |

### Implementation Steps

#### Step 1: Feature Extraction (Day 1)
```python
# 1. Define PostFeatures
# 2. Implement _extract_features()
```

#### Step 2: Model Training (Day 2-3)
```python
# 1. Implement _get_training_data()
# 2. Implement train()
# 3. Save/load model
```

#### Step 3: Prediction (Day 4)
```python
# 1. Implement predict()
# 2. Integrate with orchestrator
```

#### Step 4: Feature Importance (Day 5)
```python
# 1. Implement get_feature_importance()
# 2. Admin display
```

### Acceptance Criteria

- [ ] Model trains on historical data
- [ ] Predictions are reasonable
- [ ] Feature importance available
- [ ] Tests pass with > 80% coverage

---

## Phase 2.8: Multi-channel Publishing (Week 7-8)

### Goal
Publish to multiple Telegram channels.

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `publisher/multi_publisher.py` | Create | MultiPublisher class |
| `config.yaml` | Modify | Multi-channel config |
| `tests/test_multi_publisher.py` | Create | Unit tests |

### Implementation Steps

#### Step 1: Configuration (Day 1)
```python
# 1. Define ChannelConfig
# 2. Define format configs
```

#### Step 2: MultiPublisher Core (Day 2-3)
```python
# 1. Implement publish_to_all()
# 2. Parallel publishing
# 3. Result aggregation
```

#### Step 3: Format Handling (Day 4)
```python
# 1. Format per channel
# 2. Length limits
# 3. Content adaptation
```

#### Step 4: Integration & Testing (Day 5-7)
```python
# 1. Update orchestrator
# 2. Admin commands
# 3. Write tests
```

### Acceptance Criteria

- [ ] Publishes to multiple channels
- [ ] Format per channel works
- [ ] Failures handled gracefully
- [ ] Tests pass with > 85% coverage

---

## Dependencies

### External Dependencies

```
# requirements.txt additions
praw>=7.7.0              # Reddit API
readability-lxml>=0.8.1  # Full-text extraction
scikit-learn>=1.3.0      # ML predictions
joblib>=1.3.0            # Model persistence
```

### Internal Dependencies

```
Thread Mode → None
Smart Queue → None
Engagement Tracker → None
Enhanced RSS → None
Hashtag Analytics → Engagement Tracker
Reddit Integration → None
Predictive Analytics → Engagement Tracker
Multi-channel → None
```

---

## Testing Strategy

### Unit Tests
- Each module has dedicated test file
- Minimum coverage: 75%
- Use pytest-asyncio for async tests

### Integration Tests
- Test feature interactions
- Test with real API mocks
- Test database migrations

### Manual Testing
- Thread publishing end-to-end
- Queue management via admin bot
- Engagement tracking over time

---

## Rollback Plan

Each feature is behind a config flag:

```yaml
thread:
  enabled: false  # Disable if issues

queue:
  enabled: false  # Fall back to direct publishing

engagement:
  enabled: false  # Stop tracking

rss:
  enhanced_mode: false  # Use old parser

predictive:
  enabled: false  # Skip predictions

multi_channel:
  enabled: false  # Single channel only
```

---

## Monitoring

### Health Checks
- Queue size alert (> 50 items)
- Engagement tracking lag (> 1 hour)
- RSS source failures (> 3 consecutive)

### Metrics to Track
- Threads published per day
- Average queue wait time
- Engagement rate trends
- Prediction accuracy

---

*Plan Version: 1.0*
*Created: 2025-03-15*
*Estimated Completion: 2025-05-10*
