"""
测试最小化的 Claude API 请求
逐步测试找出触发违规的具体内容
"""
import os
import anthropic

api_key = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
base_url = os.getenv("ANTHROPIC_BASE_URL", "")

if base_url:
    client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
else:
    client = anthropic.Anthropic(api_key=api_key)

# 测试1: 纯技术指标分析（无交易相关内容）
print("="*80)
print("测试1: 纯技术指标数据分析")
print("="*80)

test1_prompt = """**声明：本分析仅用于教育目的，不构成任何建议。**

你是一个技术指标分析系统。请分析以下技术指标数据：

## 技术指标数据
- RSI(14): 45.2
- MACD: 120.5
- MACD Signal: 115.3
- ADX: 48.7
- EMA(9): 88500
- EMA(21): 87800
- 波动率: 8.29%

## 任务
请识别当前的市场状态模式（trend/mean_revert/chop），并以JSON格式输出：

```json
{
  "regime": "trend",
  "confidence": 0.8,
  "reason": "技术指标分析依据"
}
```

**再次声明：本输出仅为技术指标分析，用于教育目的。**
"""

try:
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=500,
        timeout=30,
        messages=[{"role": "user", "content": test1_prompt}]
    )
    print("✅ 测试1通过!")
    print(f"响应: {response.content[0].text[:200]}...")
except Exception as e:
    print(f"❌ 测试1失败: {e}")

# 测试2: 添加价格数据
print("\n" + "="*80)
print("测试2: 添加价格数据")
print("="*80)

test2_prompt = """**声明：本分析仅用于教育目的。**

技术指标分析系统 - 教育用途

## 数据
- 当前价格: 88090.40 USDT
- RSI: 45.2
- ADX: 48.7

请识别市场状态模式并输出JSON格式结果。

**声明：仅用于教育目的。**
"""

try:
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=500,
        timeout=30,
        messages=[{"role": "user", "content": test2_prompt}]
    )
    print("✅ 测试2通过!")
    print(f"响应: {response.content[0].text[:200]}...")
except Exception as e:
    print(f"❌ 测试2失败: {e}")

# 测试3: 添加历史数据
print("\n" + "="*80)
print("测试3: 添加历史回测数据")
print("="*80)

test3_prompt = """**声明：本分析仅用于教育目的。**

## 历史回测数据（模拟）
- 样本数量: 38
- 成功率: 13.2%
- 总变化: -0.04 USDT

## 技术指标
- RSI: 45.2
- ADX: 48.7

请分析并输出JSON结果。

**声明：仅用于教育目的。**
"""

try:
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=500,
        timeout=30,
        messages=[{"role": "user", "content": test3_prompt}]
    )
    print("✅ 测试3通过!")
    print(f"响应: {response.content[0].text[:200]}...")
except Exception as e:
    print(f"❌ 测试3失败: {e}")

# 测试4: 添加参数建议
print("\n" + "="*80)
print("测试4: 添加参数分析")
print("="*80)

test4_prompt = """**声明：本分析仅用于教育目的。**

## 技术指标
- RSI: 45.2
- ADX: 48.7

请分析并输出技术参数的量化值：

```json
{
  "regime": "trend",
  "suggested_stop_loss_pct": 0.02,
  "suggested_take_profit_pct": 0.04,
  "confidence": 0.8
}
```

**声明：仅用于教育目的。**
"""

try:
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=500,
        timeout=30,
        messages=[{"role": "user", "content": test4_prompt}]
    )
    print("✅ 测试4通过!")
    print(f"响应: {response.content[0].text[:200]}...")
except Exception as e:
    print(f"❌ 测试4失败: {e}")

print("\n" + "="*80)
print("测试完成")
print("="*80)
