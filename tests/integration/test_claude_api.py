"""
测试 Claude API 连接
"""
import os
import sys

try:
    import anthropic
    print("✅ anthropic 库已安装")
except ImportError:
    print("❌ anthropic 库未安装")
    sys.exit(1)

# 读取配置
api_key = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
base_url = os.getenv("ANTHROPIC_BASE_URL", "")

print(f"\n配置信息:")
print(f"API Key: {api_key[:20]}..." if api_key else "API Key: 未设置")
print(f"Base URL: {base_url}")

if not api_key:
    print("\n❌ 未设置 ANTHROPIC_AUTH_TOKEN 环境变量")
    sys.exit(1)

# 测试1: 简单的 API 调用
print("\n" + "="*80)
print("测试1: 发送简单的测试请求")
print("="*80)

try:
    if base_url:
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "User-Agent": "claude-code-cli",
                "X-Claude-Code": "1"
            }
        )
        print(f"✅ 客户端初始化成功 (自定义端点: {base_url})")
    else:
        client = anthropic.Anthropic(
            api_key=api_key,
            default_headers={
                "User-Agent": "claude-code-cli",
                "X-Claude-Code": "1"
            }
        )
        print("✅ 客户端初始化成功 (默认端点)")

    # 发送简单请求
    print("\n发送测试消息: 'Hello, Claude!'")
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=100,
        timeout=30,
        messages=[
            {"role": "user", "content": "Hello, Claude! Please respond with 'Hello, World!'"}
        ]
    )

    print(f"✅ API 调用成功!")
    print(f"响应: {response.content[0].text}")

except anthropic.BadRequestError as e:
    print(f"❌ 请求错误: {e}")
    print(f"状态码: {e.status_code}")
    print(f"响应: {e.response}")
except anthropic.AuthenticationError as e:
    print(f"❌ 认证错误: {e}")
    print("可能的原因:")
    print("  1. API Key 无效或已过期")
    print("  2. API Key 格式不正确")
except anthropic.PermissionDeniedError as e:
    print(f"❌ 权限错误: {e}")
    print("可能的原因:")
    print("  1. API Key 没有访问该模型的权限")
    print("  2. 账户被限制")
except anthropic.RateLimitError as e:
    print(f"❌ 速率限制: {e}")
except anthropic.APIError as e:
    print(f"❌ API 错误: {e}")
    print(f"错误类型: {type(e).__name__}")
    print(f"错误信息: {str(e)}")
except Exception as e:
    print(f"❌ 未知错误: {e}")
    print(f"错误类型: {type(e).__name__}")
    import traceback
    print("\n完整错误堆栈:")
    traceback.print_exc()

# 测试2: 测试不同的端点
print("\n" + "="*80)
print("测试2: 测试默认端点（不使用自定义端点）")
print("="*80)

try:
    client_default = anthropic.Anthropic(
        api_key=api_key,
        default_headers={
            "User-Agent": "claude-code-cli",
            "X-Claude-Code": "1"
        }
    )
    print("✅ 默认端点客户端初始化成功")

    print("\n发送测试消息到默认端点...")
    response = client_default.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=100,
        timeout=30,
        messages=[
            {"role": "user", "content": "Hello!"}
        ]
    )

    print(f"✅ 默认端点 API 调用成功!")
    print(f"响应: {response.content[0].text}")

except Exception as e:
    print(f"❌ 默认端点调用失败: {e}")
    print(f"错误类型: {type(e).__name__}")

print("\n" + "="*80)
print("测试完成")
print("="*80)
