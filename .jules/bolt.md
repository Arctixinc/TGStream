## 2024-05-23 - Double Transcoding in Pipeline
**Learning:** Pipelines that chain multiple FFmpeg processes (e.g. normalization -> packaging) can accidentally re-encode streams at every step.
**Action:** Always check the input format of downstream processes. If the upstream process already normalizes the codec (e.g. to AAC), use `-c copy` in the downstream process to avoid redundant CPU usage and latency.
