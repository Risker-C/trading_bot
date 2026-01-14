#!/usr/bin/env python3
"""Phase 0 测试脚本"""

import sys

print("=" * 50)
print("Phase 0 测试")
print("=" * 50)

# 测试1: 导入config
print("\n1. 测试config导入...")
try:
    from config.settings import settings as config
    print("✅ config导入成功")
except Exception as e:
    print(f"❌ config导入失败: {e}")
    sys.exit(1)

# 测试2: 检查特性开关
print("\n2. 测试特性开关...")
switches = [
    'ASYNC_AI_ENABLED',
    'DB_BATCH_WRITES_ENABLED',
    'ML_FORCE_LITE',
    'CONFIG_SPLIT_ENABLED'
]

for switch in switches:
    if hasattr(config, switch):
        value = getattr(config, switch)
        print(f"✅ {switch}: {value}")
    else:
        print(f"❌ {switch}: 不存在")

# 测试3: 导入MetricsLogger
print("\n3. 测试MetricsLogger导入...")
try:
    from utils.logger_utils import MetricsLogger
    print("✅ MetricsLogger导入成功")

    # 测试实例化
    metrics = MetricsLogger()
    print("✅ MetricsLogger实例化成功")
except Exception as e:
    print(f"❌ MetricsLogger测试失败: {e}")

print("\n" + "=" * 50)
print("测试完成")
print("=" * 50)
