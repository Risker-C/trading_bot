"""
机器学习配置模块（Phase 1）
"""

# ==================== ML信号过滤器配置 ====================

ENABLE_ML_FILTER = True
ML_USE_LITE_VERSION = True  # 使用优化版（内存占用低60-70%）
ML_MODE = "shadow"  # shadow/filter/off

# 模型路径（从paths.py导入，这里保留兼容性）
# ML_MODEL_PATH 已在 paths.py 中定义

# ==================== ML参数 ====================

ML_QUALITY_THRESHOLD = 0.35  # 质量分数阈值
ML_MIN_SIGNALS = 1
ML_LOG_PREDICTIONS = True
ML_VERBOSE_LOGGING = True
ML_FEATURE_LOOKBACK = 20

# ==================== 自动训练 ====================

ML_AUTO_RETRAIN = False
ML_RETRAIN_INTERVAL_DAYS = 30
ML_MIN_TRAINING_SAMPLES = 100

# ==================== Phase 0: ML强制轻量化 ====================

ML_FORCE_LITE = False  # 生产环境推荐启用

# ==================== Phase 2: 模型卸载策略 ====================

ML_UNLOAD_AFTER_IDLE_SECONDS = 600  # 空闲600秒（10分钟）后卸载模型以释放内存
