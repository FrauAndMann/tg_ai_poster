# Production Audit: 100 Improvement Points

This document provides a pragmatic production audit of the repository. It separates:

- **Implemented now** — changes delivered in this revision.
- **Recommended next** — high-value backlog items for future iterations.

## Status legend

- `[x]` implemented in this revision
- `[ ]` recommended backlog

---

## 1. Content quality and editorial safety

1. [x] Dynamic CJK glitch detection.
2. [x] Mixed-script anomaly detection for RU/EN posts.
3. [x] Invisible character detection.
4. [x] Repeated punctuation detection.
5. [x] Repeated-line detection.
6. [x] Raw-response sanitation support.
7. [ ] Enforce stricter JSON schema with typed objects.
8. [ ] Validate source citation count per post.
9. [ ] Require at least one concrete metric in analytical posts.
10. [ ] Penalize unsupported superlatives.
11. [ ] Detect title-body contradiction.
12. [ ] Detect unsupported causal claims.
13. [ ] Detect speculative future statements without evidence.
14. [ ] Add language consistency score.
15. [ ] Add named-entity consistency checks.
16. [ ] Detect contradiction across key facts and TL;DR.
17. [ ] Reject duplicate bullets in key facts.
18. [ ] Require unique source domains for controversial topics.
19. [ ] Add sentiment-balance scoring.
20. [ ] Add concise headline optimizer.

## 2. News collection and freshness

21. [x] RSS feed cache with TTL.
22. [x] Event-loop safe feed parsing using worker threads.
23. [x] Fetch concurrency limiter.
24. [x] Freshness-based ranking.
25. [x] Metadata-richness ranking.
26. [x] Domain-weight ranking.
27. [x] URL normalization for deduplication.
28. [x] Stronger deduplication by normalized URL.
29. [x] Configurable max article age.
30. [ ] Add ETag/Last-Modified support per feed.
31. [ ] Persist feed fetch fingerprints in storage.
32. [ ] Track per-feed success/error rates.
33. [ ] Auto-disable chronically broken feeds.
34. [ ] Add per-source latency metrics.
35. [ ] Add source health dashboard output.
36. [ ] Prioritize first-party vendor sources over aggregators.
37. [ ] Add canonical-link extraction for syndicated feeds.
38. [ ] Add content language detection before ranking.
39. [ ] Add duplicate-title clustering across feeds.
40. [ ] Add source-category weighting by channel niche.

## 3. Breaking-news monitor

41. [x] Compatibility fallback from `content` to `summary`.
42. [x] Real-time source-trust bonus.
43. [x] Summary-richness bonus for alerts.
44. [x] Title-signature deduplication.
45. [ ] Add alert-cooldown per entity.
46. [ ] Add multi-source corroboration bonus.
47. [ ] Add duplicate alert collapse across windows.
48. [ ] Add persistent processed-alert storage.
49. [ ] Add region/topic-specific breaking-news profiles.
50. [ ] Add event severity class labels.

## 4. Performance and reliability

51. [x] Reduced redundant HTTP work via RSS caching.
52. [x] Avoided blocking RSS parse calls on main event loop.
53. [x] Bounded external fetch parallelism.
54. [ ] Add async connection pool tuning.
55. [ ] Add explicit close lifecycle for all collector sessions.
56. [ ] Add cache hit/miss telemetry.
57. [ ] Add benchmark command for source collection latency.
58. [ ] Add memory-pressure guardrails for pending alerts.
59. [ ] Add bounded retries with jitter for feed fetches.
60. [ ] Add per-stage timeout budgets.
61. [ ] Add structured performance spans.
62. [ ] Add backpressure when autopost queue is saturated.
63. [ ] Cache source ranking calculations.
64. [ ] Add database query profiling in debug mode.
65. [ ] Add startup warm caches for hot feeds.

## 5. Configuration and operability

66. [x] Added source performance/ranking options to config.
67. [x] Restored YAML loading for `realtime` section.
68. [x] Restored YAML loading for `media` section.
69. [ ] Add config schema export command.
70. [ ] Add startup config diff against defaults.
71. [ ] Validate impossible or conflicting config combinations.
72. [ ] Add secrets redaction in all config logs.
73. [ ] Add env var documentation generator.
74. [ ] Add sample configs for RU/EN channels.
75. [ ] Add production/staging/dev profile presets.

## 6. Quality assurance and test depth

76. [x] Added tests for new source normalization behavior.
77. [x] Added tests for new ranking behavior.
78. [x] Added tests for expanded YAML config coverage.
79. [ ] Add feed-cache TTL tests.
80. [ ] Add concurrency-bound tests.
81. [ ] Add monitor signature-dedup tests.
82. [ ] Add end-to-end dry-run regression snapshots.
83. [ ] Add fixtures for malformed RSS feeds.
84. [ ] Add benchmark tests for hot paths.
85. [ ] Add contract tests for LLM JSON outputs.

## 7. Documentation and developer experience

86. [x] Full README rewrite.
87. [x] Added production audit document.
88. [ ] Add architecture sequence diagrams.
89. [ ] Add onboarding guide for prompt tuning.
90. [ ] Add runbook for common incidents.
91. [ ] Add monitoring/alerting examples.
92. [ ] Add deployment hardening guide.
93. [ ] Add source selection best-practices.
94. [ ] Add editor-review rubric documentation.
95. [ ] Add release checklist.

## 8. Product maturity roadmap

96. [ ] Human-in-the-loop moderation dashboard.
97. [ ] Multi-channel topic personalization.
98. [ ] Cost-aware model routing.
99. [ ] Automatic source trust learning from outcomes.
100. [ ] Closed-loop post-performance optimization.

---

## Suggested next milestone

If continuing toward true production level, the next highest-value batch is:

1. Persistent dedup/state for alerts and feeds.
2. Source health telemetry and circuit-breaking at feed level.
3. End-to-end contract tests for generation -> validation -> formatting.
4. Multi-source corroboration in breaking-news scoring.
5. More rigid factuality and citation requirements in post generation.
