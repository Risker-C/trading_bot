"""
测试通知功能
测试飞书和Telegram推送
"""
import os
from logger_utils import FeishuNotifier, TelegramNotifier, MultiNotifier

def test_feishu():
    """测试飞书通知"""
    print("=" * 50)
    print("测试飞书通知")
    print("=" * 50)

    # 从环境变量获取webhook URL
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "")

    if not webhook_url:
        print("❌ 未设置 FEISHU_WEBHOOK_URL 环境变量")
        print("请先设置: export FEISHU_WEBHOOK_URL='your_webhook_url'")
        return False

    print(f"✅ Webhook URL: {webhook_url[:50]}...")

    # 创建通知器
    notifier = FeishuNotifier(webhook_url=webhook_url)
    notifier.enabled = True  # 强制启用

    # 1. 测试基础消息
    print("\n1. 测试基础消息...")
    result = notifier.send_message("🤖 测试消息：飞书通知功能正常")
    print(f"   结果: {'✅ 成功' if result else '❌ 失败'}")

    # 2. 测试交易通知 - 开多
    print("\n2. 测试开多通知...")
    notifier.notify_trade(
        action='open',
        symbol='BTCUSDT',
        side='long',
        amount=0.001,
        price=95000.00,
        reason='布林带突破策略'
    )

    # 3. 测试交易通知 - 平仓
    print("\n3. 测试平仓通知...")
    notifier.notify_trade(
        action='close',
        symbol='BTCUSDT',
        side='long',
        amount=0.001,
        price=96000.00,
        pnl=10.00,
        reason='止盈触发'
    )

    # 4. 测试错误通知
    print("\n4. 测试错误通知...")
    notifier.notify_error("测试错误：API连接超时")

    # 5. 测试信号通知
    print("\n5. 测试信号通知...")
    notifier.notify_signal(
        strategy='布林带突破',
        signal='long',
        reason='价格突破上轨',
        strength=0.85,
        confidence=0.75
    )

    # 6. 测试风控事件通知
    print("\n6. 测试风控事件通知...")
    notifier.notify_risk_event(
        event_type='止损触发',
        description='价格跌破止损线，自动平仓'
    )

    # 7. 测试每日总结
    print("\n7. 测试每日总结...")
    notifier.notify_daily_summary({
        'total_trades': 10,
        'winning_trades': 6,
        'losing_trades': 4,
        'win_rate': 60.0,
        'total_pnl': 150.50,
        'profit_factor': 1.8
    })

    print("\n" + "=" * 50)
    print("✅ 飞书通知测试完成")
    print("=" * 50)
    return True


def test_telegram():
    """测试Telegram通知"""
    print("\n" + "=" * 50)
    print("测试Telegram通知")
    print("=" * 50)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        print("⚠️  未设置 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        print("跳过Telegram测试")
        return False

    print(f"✅ Bot Token: {bot_token[:20]}...")
    print(f"✅ Chat ID: {chat_id}")

    notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    notifier.enabled = True

    print("\n测试Telegram消息...")
    result = notifier.send_message("🤖 测试消息：Telegram通知功能正常")
    print(f"结果: {'✅ 成功' if result else '❌ 失败'}")

    return True


def test_multi_notifier():
    """测试多渠道通知"""
    print("\n" + "=" * 50)
    print("测试多渠道通知")
    print("=" * 50)

    # 设置环境变量
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "")
    if webhook_url:
        os.environ['FEISHU_WEBHOOK_URL'] = webhook_url

    # 创建多渠道通知器
    notifier = MultiNotifier()

    print("\n发送测试交易通知到所有渠道...")
    notifier.notify_trade(
        action='open',
        symbol='ETHUSDT',
        side='short',
        amount=0.1,
        price=3500.00,
        reason='多渠道测试'
    )

    print("\n✅ 多渠道通知测试完成")
    return True


def main():
    """主函数"""
    print("\n🚀 开始测试通知功能\n")

    # 测试飞书
    test_feishu()

    # 测试Telegram（如果配置了）
    test_telegram()

    # 测试多渠道
    test_multi_notifier()

    print("\n" + "=" * 50)
    print("🎉 所有测试完成")
    print("=" * 50)
    print("\n请检查飞书群和Telegram是否收到消息")


if __name__ == "__main__":
    main()
