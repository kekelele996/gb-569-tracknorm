"""算法阈值、限流与 mock 边界常量（算法口径写死在这里，README/TESTING 引用）。"""
from __future__ import annotations

# 算法 1：轨迹归一
DEDUPE_WINDOW_MINUTES = 30        # 同状态同地点 30 分钟窗口内的重复回推
MAPPING_MIN_SCORE = 0.5           # 低于该分数视为未命中（未命中 = 覆盖率缺口）
EXACT_SCORE = 1.0
ALIAS_SCORE = 0.8
FUZZY_MIN_SCORE = 0.5
FUZZY_MAX_SCORE = 0.7

# 算法 2：停滞检测
Z_WARN = 3.5                      # |稳健 z| >= 3.5 判停滞
Z_ALERT = 5.0
Z_CRITICAL = 8.0
MIN_BASELINE_SAMPLES = 5          # 段基线样本 < 5 → insufficient_baseline
MAD_FLOOR_MINUTES = 1.0           # MAD 下限，避免除零
ROBUST_Z_K = 0.6745

# 限流（HTTP 中间件）
RATE_WINDOW_SECONDS = 60
PULL_BUCKET_KEY = "pull"
PULL_PATHS = ("/api/tracks/pull", "/api/tracks/normalize")

# 承运商 mock
MOCK_429_BUDGET = 2
MOCK_BACKOFF_MS = (180, 420)
MOCK_429_RETRY_MESSAGE = "carrier api rate limited (mock)"

# 数据质量报表
QUALITY_COVERAGE_WEIGHT = 0.5
QUALITY_DUP_WEIGHT = 0.2
QUALITY_CONFLICT_WEIGHT = 0.3
