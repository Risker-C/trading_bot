# 完整量化交易机器人

## 1. 项目结构

```
trading_bot/
├── config.py           # 配置文件
├── indicators.py       # 技术指标
├── strategies.py       # 交易策略
├── risk_manager.py     # 风险管理
├── trader.py           # 交易执行
├── backtest.py         # 回测模块
├── logger_utils.py     # 日志工具
├── main.py             # 主入口
├── requirements.txt    # 依赖
├── .env                # 环境变量（API密钥）
└── logs/               # 日志目录
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

## 11. 测试脚本

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
