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
# from .strategies import *  # Phase 2: 已合并到主config.py，移除此导入

# 导入原config.py中的其他配置（交易参数、风控参数等）
# 使用相对导入从父目录导入
import sys
import os
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# 从父目录的config.py导入所有其他配置
import importlib.util
_config_path = os.path.join(_parent_dir, 'config.py')
_spec = importlib.util.spec_from_file_location("_config_legacy", _config_path)
_config_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_config_legacy)

# 导入所有不在当前命名空间的配置
for _attr in dir(_config_legacy):
    if not _attr.startswith('_') and _attr not in globals():
        globals()[_attr] = getattr(_config_legacy, _attr)
