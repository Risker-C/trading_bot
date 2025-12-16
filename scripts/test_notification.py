#!/usr/bin/env python3
"""
测试通知功能
"""
import config
from logger_utils import notifier

print("=" * 60)
print("🧪 测试通知功能")
print("=" * 60)

# 显示配置
print("\n📋 通知配置:")
print(f"   飞书通知: {'启用' if config.ENABLE_FEISHU else '禁用'}")
print(f"   飞书 Webhook: {config.FEISHU_WEBHOOK_URL[:50]}..." if config.FEISHU_WEBHOOK_URL else "   飞书 Webhook: 未配置")
print(f"   邮件通知: {'启用' if config.ENABLE_EMAIL else '禁用'}")
print(f"   邮件发件人: {config.EMAIL_SENDER}")
print(f"   邮件收件人: {config.EMAIL_RECEIVER}")
print(f"   Telegram通知: {'启用' if config.ENABLE_TELEGRAM else '禁用'}")

# 测试交易通知
print("\n📤 发送测试交易通知...")
notifier.notify_trade(
    action='open',
    symbol='BTCUSDT',
    side='long',
    amount=0.001,
    price=90000.0,
    reason='测试通知功能'
)

print("\n✅ 测试完成！请检查飞书和邮箱是否收到通知。")
