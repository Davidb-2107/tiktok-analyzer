---
status: accepted
---

# Keep regular sampling and add scene detection

TikTok Analyzer keeps its regular sampled frames as the canonical stream for OCR, hook analysis, and short-lived visual changes, and adds PySceneDetect as a complementary best-effort layer for technical shot boundaries. Scenes use `ContentDetector`, expose one midpoint keyframe in a separate R2 prefix, retain all time intervals while capping keyframes at 120, and are displayed through the existing frontend; the feature is disabled for the first deployment until its quality and latency are benchmarked.
