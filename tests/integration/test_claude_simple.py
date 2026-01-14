"""
测试最基本的 Claude API 请求
"""
import os
import anthropic

api_key = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
base_url = os.getenv("ANTHROPIC_BASE_URL", "")

print("="*80)
print("测试1: Hello World（使用自定义端点）")
print("="*80)
print(f"Base URL: {base_url}")

try:
    if base_url:
        client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
    else:
        client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=100,
        timeout=30,
        messages=[{"role": "user", "content": "Please say 'Hello, World!' and nothing else."}]
    )
    print("✅ 测试1通过!")
    print(f"响应: {response.content[0].text}")
except Exception as e:
    print(f"❌ 测试1失败: {e}")
    print(f"错误类型: {type(e).__name__}")

print("\n" + "="*80)
print("测试2: Hello World（不使用自定义端点）")
print("="*80)

try:
    client_default = anthropic.Anthropic(api_key=api_key)

    response = client_default.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=100,
        timeout=30,
        messages=[{"role": "user", "content": "Please say 'Hello, World!' and nothing else."}]
    )
    print("✅ 测试2通过!")
    print(f"响应: {response.content[0].text}")
except Exception as e:
    print(f"❌ 测试2失败: {e}")
    print(f"错误类型: {type(e).__name__}")

print("\n" + "="*80)
print("测试3: 数学问题（使用自定义端点）")
print("="*80)

try:
    if base_url:
        client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
    else:
        client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=100,
        timeout=30,
        messages=[{"role": "user", "content": "What is 2 + 2?"}]
    )
    print("✅ 测试3通过!")
    print(f"响应: {response.content[0].text}")
except Exception as e:
    print(f"❌ 测试3失败: {e}")
    print(f"错误类型: {type(e).__name__}")

print("\n" + "="*80)
print("测试完成")
print("="*80)
