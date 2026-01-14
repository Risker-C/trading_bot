#!/usr/bin/env python3
"""
测试通知功能 - 详细版本
"""
from config.settings import settings as config
from utils.logger_utils import get_logger, FeishuNotifier, EmailNotifier

logger = get_logger("test_notification")

print("=" * 60)
print("🧪 测试通知功能（详细版）")
print("=" * 60)

# 测试飞书通知
print("\n📱 测试飞书通知...")
feishu = FeishuNotifier()
print(f"   启用状态: {feishu.enabled}")
print(f"   Webhook URL: {feishu.webhook_url[:50]}..." if feishu.webhook_url else "   Webhook URL: 未配置")

if feishu.enabled:
    print("   正在发送测试消息...")
    result = feishu.send_message("🧪 测试消息：交易机器人通知功能测试")
    print(f"   发送结果: {'✅ 成功' if result else '❌ 失败'}")
else:
    print("   ⚠️  飞书通知未启用")

# 测试邮件通知
print("\n📧 测试邮件通知...")
email = EmailNotifier()
print(f"   启用状态: {email.enabled}")
print(f"   SMTP服务器: {email.smtp_server}:{email.smtp_port}")
print(f"   发件人: {email.sender_email}")
print(f"   收件人: {email.receiver_email}")

if email.enabled:
    print("   正在发送测试邮件...")
    result = email.send_message(
        subject="🧪 交易机器人通知测试",
        body="<h2>测试消息</h2><p>这是一封测试邮件，用于验证交易机器人的邮件通知功能。</p>",
        html=True
    )
    print(f"   发送结果: {'✅ 成功' if result else '❌ 失败'}")
else:
    print("   ⚠️  邮件通知未启用")

# 测试交易通知
print("\n📤 测试交易通知（完整流程）...")
feishu.notify_trade(
    action='open',
    symbol='BTCUSDT',
    side='long',
    amount=0.001,
    price=90000.0,
    reason='测试通知功能'
)

print("\n✅ 测试完成！")
print("请检查：")
print("  1. 飞书群是否收到消息")
print("  2. 邮箱是否收到邮件（可能在垃圾邮件中）")
print("  3. 查看上面的发送结果")
