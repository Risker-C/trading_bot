# 测试和调试脚本

本目录包含用于测试和调试交易机器人的各种脚本。

## 通知测试

### test_notification.py
测试飞书、邮件和Telegram通知功能。

**用法:**
```bash
python scripts/test_notification.py
```

**要求:**
- 设置相应的环境变量(FEISHU_WEBHOOK_URL, EMAIL_SENDER等)

## 交易功能测试

### test_trading.py
测试完整的交易流程:开仓、持仓检查、平仓。

**用法:**
```bash
python scripts/test_trading.py
```

**警告:** 此脚本会使用真实资金进行交易,请谨慎使用。

## 持仓检查脚本

### check_status.py
快速检查账户余额、持仓和最近订单。

**用法:**
```bash
python scripts/check_status.py
```

### check_all_positions.py
详细检查所有持仓(包括双向持仓),显示原始API返回的完整信息。

**用法:**
```bash
python scripts/check_all_positions.py
```

## 平仓脚本

以下脚本用于在不同场景下平仓,主要用于调试和紧急情况:

### close_position.py
交互式平仓脚本,需要用户确认。

### close_position_now.py
直接平仓,无需确认(用于自动化)。

### close_both_positions.py
平掉所有持仓(双向持仓模式)。

### close_final.py
平掉最后的持仓。

### close_hedge_mode.py
使用双向持仓模式参数平仓(带holdSide参数)。

### close_one_way_mode.py
使用单向持仓模式平仓(tradeSide="open")。

### close_with_open.py
使用tradeSide="open"来平仓(通过开反向仓位)。

### close_raw_api.py
使用Bitget原始一键平仓API平仓(推荐方法)。

**用法:**
```bash
python scripts/close_raw_api.py
```

## 注意事项

1. **安全性:** 所有脚本都从环境变量或config.py读取配置,不包含硬编码的敏感信息。
2. **真实交易:** 标记为"交易"的脚本会使用真实资金,请谨慎使用。
3. **调试用途:** 这些脚本主要用于开发和调试,不建议在生产环境中频繁使用。
4. **环境要求:** 确保已正确设置所有必需的环境变量(参考.env.example)。

## 开发历史

这些脚本是在解决双向持仓模式平仓问题时创建的,用于测试不同的API调用方法和参数组合。最终发现使用Bitget的一键平仓API(`close_positions`)是最可靠的方法。
