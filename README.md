# 完整量化交易机器人

## 1. 项目结构

```
trading_bot/
├── config.py           # 配置文件
├── indicators.py       # 技术指标
├── strategies.py       # 交易策略(含布林带双策略)
├── market_regime.py    # 市场状态检测(新增)
├── risk_manager.py     # 风险管理
├── trader.py           # 交易执行
├── bot.py              # 交易机器人主程序
├── backtest.py         # 回测模块
├── logger_utils.py     # 日志工具
├── main.py             # 主入口
├── requirements.txt    # 依赖
├── .env                # 环境变量（API密钥）
├── logs/               # 日志目录
└── scripts/            # 测试和诊断脚本
    ├── test_dynamic_strategy.py    # 动态策略测试
    ├── diagnose_bollinger.py       # 布林带诊断
    ├── compare_data_sources.py     # 数据源对比
    └── test_fix.py                 # 修复验证测试
```

---

## 2. 环境准备

### 2.1 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2.2 安装依赖

```bash
pip install -r requirements.txt
```

### 2.3 配置 API 密钥

创建 `.env` 文件：

```bash
# .env
BITGET_API_KEY=your_api_key_here
BITGET_SECRET=your_secret_here
BITGET_PASSWORD=your_password_here

# 可选：Telegram 通知
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 3. 启动命令

### 3.1 使用 main.py（推荐）

```bash
# 实盘交易
python main.py live

# 回测
python main.py backtest --symbol BTC/USDT --timeframe 15m --limit 1000

# 策略对比回测
python main.py backtest --compare --strategies macd_cross,ema_cross,bollinger_breakthrough

# 使用共识信号回测
python main.py backtest --consensus --plot equity.png --export trades.csv

# 参数优化
python main.py optimize --strategy rsi_divergence

# 查看状态
python main.py status
```

### 3.2 直接运行 trader.py

```bash
# 直接启动实盘交易
python trader.py
```

### 3.3 单独运行回测

```bash
python backtest.py
```

---

## 4. 快速启动脚本

### 4.1 Windows - `start.bat`

```batch
@echo off
echo ========================================
echo 量化交易机器人
echo ========================================
echo.
echo 1. 实盘交易
echo 2. 回测
echo 3. 查看状态
echo 4. 退出
echo.
set /p choice=请选择: 

if "%choice%"=="1" (
    python main.py live
) else if "%choice%"=="2" (
    python main.py backtest --limit 1000
) else if "%choice%"=="3" (
    python main.py status
) else (
    exit
)
pause
```

### 4.2 macOS/Linux - `start.sh`

```bash
#!/bin/bash

echo "========================================"
echo "量化交易机器人"
echo "========================================"
echo ""
echo "1. 实盘交易"
echo "2. 回测"
echo "3. 查看状态"
echo "4. 退出"
echo ""
read -p "请选择: " choice

case $choice in
    1) python main.py live ;;
    2) python main.py backtest --limit 1000 ;;
    3) python main.py status ;;
    *) exit ;;
esac
```

运行前授权：

```bash
chmod +x start.sh
./start.sh
```

---

## 5. 后台运行（生产环境）

### 5.1 使用 nohup（Linux/macOS）

```bash
# 后台运行
nohup python main.py live > output.log 2>&1 &

# 查看进程
ps aux | grep "main.py"

# 停止
kill <pid>
```

### 5.2 使用 screen

```bash
# 创建会话
screen -S trading_bot

# 运行
python main.py live

# 分离会话（Ctrl+A, 然后按 D）

# 恢复会话
screen -r trading_bot
```

### 5.3 使用 systemd 服务（推荐生产环境）

创建 `/etc/systemd/system/trading_bot.service`：

```ini
[Unit]
Description=Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/trading_bot
Environment=PATH=/path/to/trading_bot/venv/bin
ExecStart=/path/to/trading_bot/venv/bin/python main.py live
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 启用并启动
sudo systemctl daemon-reload
sudo systemctl enable trading_bot
sudo systemctl start trading_bot

# 查看状态
sudo systemctl status trading_bot

# 查看日志
sudo journalctl -u trading_bot -f

# 停止
sudo systemctl stop trading_bot
```

---

## 6. 验证启动

### 6.1 检查配置

```bash
python config.py
```

输出示例：

```
==================================================
当前配置
==================================================
交易对: BTCUSDT
时间周期: 15m
杠杆: 10x
保证金模式: crossed
仓位比例: 10%
止损: 2.0%
止盈: 4.0%
策略: ['bollinger_breakthrough', 'rsi_divergence', 'macd_cross', 'ema_cross', 'composite_score']
Kelly公式: 启用
ATR止损: 启用
分批建仓: 启用
多时间周期: 启用
==================================================
```

### 6.2 测试连接

```python
# test_connection.py
import ccxt

exchange = ccxt.bitget({
    'apiKey': 'your_key',
    'secret': 'your_secret',
    'password': 'your_password',
})

# 测试公共API
ticker = exchange.fetch_ticker('BTC/USDT:USDT')
print(f"BTC价格: {ticker['last']}")

# 测试私有API
balance = exchange.fetch_balance()
print(f"USDT余额: {balance['USDT']['free']}")
```

```bash
python test_connection.py
```

---

## 7. 常见问题

| 问题                    | 解决方案                                          |
| --------------------- | --------------------------------------------- |
| `ModuleNotFoundError` | 确认激活虚拟环境，运行 `pip install -r requirements.txt` |
| API 连接失败              | 检查 `.env` 文件中的 API 密钥是否正确                     |
| 权限不足                  | Bitget API 需要开启合约交易权限                         |
| 日志目录不存在               | 程序会自动创建，或手动 `mkdir logs`                      |

---

## 8. 推荐启动流程

```bash
# 1. 进入项目目录
cd trading_bot

# 2. 激活虚拟环境
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows

# 3. 检查配置
python config.py

# 4. 先运行回测验证策略
python main.py backtest --limit 500

# 5. 确认无误后启动实盘
python main.py live
```

**启动成功后会看到类似输出：**

```
==================================================
交易机器人启动
交易对: BTCUSDT
时间周期: 15m
策略: ['bollinger_breakthrough', 'rsi_divergence', 'macd_cross', 'ema_cross', 'composite_score']
杠杆: 10x
==================================================
2024-01-15 10:30:00 [INFO] 获取K线数据...
2024-01-15 10:30:01 [INFO] 余额: 1000.00 USDT
2024-01-15 10:30:01 [INFO] 无持仓
2024-01-15 10:30:01 [INFO] 策略信号: HOLD
```
## 9. 监控与维护

### 9.1 使用监控脚本

```bash
# 单次健康检查
python monitor.py --check

# 生成报告
python monitor.py --report

# 持续监控（每5分钟检查一次）
python monitor.py --interval 300
```

---

## 10. Docker 部署

### 10.1 Docker 使用命令

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f trading-bot

# 停止服务
docker-compose down

# 重启
docker-compose restart trading-bot
```

---

## 11. 新功能: 市场状态感知与动态策略选择

### 11.1 功能概述

系统现在支持**市场状态感知**,能够自动识别市场处于震荡、过渡还是趋势状态,并根据市场状态动态选择最合适的交易策略。

### 11.2 市场状态分类

| 市场状态 | 判断条件 | 特征 |
|---------|---------|------|
| **震荡市 (RANGING)** | ADX < 20 或 布林带宽度 < 2% | 价格在区间内波动,无明确方向 |
| **过渡市 (TRANSITIONING)** | 20 ≤ ADX < 30 | 市场状态不明确,可能变盘 |
| **趋势市 (TRENDING)** | ADX ≥ 30 且 布林带宽度 > 3% | 单边上涨或下跌,方向明确 |

### 11.3 动态策略选择

系统根据市场状态自动选择策略组:

**震荡市策略组** (均值回归):
- `bollinger_breakthrough` - 布林带均值回归(突破下轨做多,突破上轨做空)
- `rsi_divergence` - RSI背离策略
- `kdj_cross` - KDJ交叉策略

**过渡市策略组** (综合评分):
- `composite_score` - 综合评分策略
- `multi_timeframe` - 多时间周期策略

**趋势市策略组** (趋势跟踪):
- `bollinger_trend` - 布林带趋势突破(突破上轨做多,突破下轨做空)
- `ema_cross` - EMA均线交叉
- `macd_cross` - MACD交叉
- `adx_trend` - ADX趋势跟踪
- `volume_breakout` - 成交量突破

### 11.4 布林带双策略

系统现在支持两种布林带策略:

**均值回归版** (`bollinger_breakthrough`):
- 适用场景: 震荡市
- 交易逻辑: 突破下轨→做多(超卖反弹), 突破上轨→做空(超买回落)
- 理论依据: 价格偏离均值后大概率回归

**趋势突破版** (`bollinger_trend`):
- 适用场景: 趋势市
- 交易逻辑: 突破上轨→做多(顺势追涨), 突破下轨→做空(顺势追跌)
- 理论依据: 强势行情中价格沿布林带边缘运行

### 11.5 配置选项

在 `config.py` 中启用动态策略选择:

```python
# 动态策略选择配置
USE_DYNAMIC_STRATEGY = True  # 启用市场状态感知的动态策略选择

# 当启用时,系统会根据市场状态自动选择合适的策略
# 当禁用时,使用 ENABLE_STRATEGIES 中的固定策略列表
```

### 11.6 运行示例

启动机器人后,日志会显示市场状态和选择的策略:

```
2024-01-15 10:30:00 [INFO] 市场状态: TRENDING (ADX=34.5, 宽度=0.52%)
                           → 策略: bollinger_trend, ema_cross, macd_cross, adx_trend, volume_breakout
```

---

## 12. 测试与诊断脚本

### 12.1 动态策略系统测试

测试市场状态检测和动态策略选择功能:

```bash
python scripts/test_dynamic_strategy.py
```

输出示例:
```
测试1: 市场状态检测
  当前市场状态: TRENDING
  置信度: 100%
  ADX: 34.6
  布林带宽度: 0.57%
  ✅ 市场状态检测测试通过

测试2: 动态策略选择
  市场状态: TRENDING
  推荐策略: bollinger_trend, ema_cross, macd_cross, adx_trend, volume_breakout
  ✅ 动态策略选择测试通过

测试3: 布林带策略对比
  均值回归: hold (突破下轨→做多, 突破上轨→做空)
  趋势突破: hold (突破上轨→做多, 突破下轨→做空)
  ✅ 布林带策略对比测试通过

🎉 所有测试通过! 动态策略系统运行正常!
```

### 12.2 布林带宽度诊断

诊断布林带计算是否正确:

```bash
python scripts/diagnose_bollinger.py
```

输出示例:
```
布林带数值 (最新):
  上轨 (upper):  90463.01 USDT
  中轨 (middle): 90206.49 USDT
  下轨 (lower):  89949.97 USDT
  收盘价:        90157.00 USDT

计算明细:
  上下轨距离: 513.05 USDT
  距离/中轨:   0.0057 (0.57%)
  带宽(公式):  (upper-lower)/middle*100 = 0.57%

诊断结果:
  ✅ 带宽计算正确
  ℹ️  带宽 0.57% 很窄,市场处于低波动状态
```

### 12.3 数据源对比分析

对比不同数据源的计算结果:

```bash
python scripts/compare_data_sources.py
```

### 12.4 数据库日志修复测试

测试numpy类型转换修复:

```bash
python scripts/test_fix.py
```

---

## 13. 测试脚本

### 11.1 test_all.py - 完整测试

### 11.2 运行测试

```bash
python test_all.py
```

输出示例：

```
==================================================
交易机器人测试
==================================================
测试模块导入...
  ✅ config
  ✅ indicators
  ✅ strategies
  ✅ risk_manager
  ✅ trader
  ✅ backtest
  ✅ logger_utils

测试配置...
  ✅ 配置有效

测试指标计算...
  ✅ 指标计算成功 (28 列)

测试策略...
  ✅ bollinger_breakthrough
  ✅ rsi_divergence
  ✅ macd_cross
  ✅ ema_cross
  ✅ composite_score

测试风险管理...
  ✅ 仓位计算: 0.000200
  ✅ 开仓记录
  ✅ 止损检查: should_stop=True
  ✅ 平仓记录

测试数据库...
  ✅ 写入交易记录: ID=1
  ✅ 读取交易记录: 1 条
  ✅ 统计查询: 1 笔交易
  ✅ 清理测试数据库

测试 API 连接...
  ✅ 公共 API: BTC = 67890.5
  ✅ 私有 API: USDT = 1000.0

==================================================
测试结果汇总
==================================================
  模块导入: ✅ 通过
  配置验证: ✅ 通过
  指标计算: ✅ 通过
  策略测试: ✅ 通过
  风险管理: ✅ 通过
  数据库: ✅ 通过
  API连接: ✅ 通过

==================================================
✅ 所有测试通过！可以启动交易机器人。
==================================================
```

---

## 12. 完整启动流程总结

```bash
# 1. 克隆/准备项目
cd trading_bot

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 .env 文件
cp .env.example .env
# 编辑 .env 填入 API 密钥

# 5. 运行测试
python test_all.py

# 6. 检查配置
python config.py

# 7. 运行回测验证
python main.py backtest --limit 500

# 8. 启动实盘交易
python main.py live

# 9. 可选：启动监控
python monitor.py &
```

**现在你可以运行 `python test_all.py` 来验证所有模块是否正常工作，然后使用 `python main.py live` 启动实盘交易。**
