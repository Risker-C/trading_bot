"""
配置模块汇总（Phase 1）

从各个子模块导入所有配置，并统一导出。
这样可以保持向后兼容：from config import XXX
"""

# 导入所有配置模块
from .paths import *
from .db import *
from .runtime import *
from .ml import *
from .ai import *
from .strategies import *

# 注：原config.py中的其他配置（交易参数、风控参数等）
# 暂时保留在原config.py中，待后续逐步迁移
