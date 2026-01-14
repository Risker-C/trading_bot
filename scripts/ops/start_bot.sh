#!/bin/bash

# 交易机器人启动脚本

BOT_DIR="/root/trading_bot"
PID_FILE="$BOT_DIR/bot.pid"
LOG_FILE="$BOT_DIR/logs/bot_runtime.log"

cd $BOT_DIR

# 检查是否有任何 bot.py 进程在运行
BOT_PIDS=$(pgrep -f "python3 bot.py" || true)

if [ -n "$BOT_PIDS" ]; then
    echo "❌ 发现运行中的机器人进程:"
    echo "$BOT_PIDS" | while read pid; do
        echo "   PID: $pid"
    done
    echo ""
    echo "如需重启,请先运行: ./stop_bot.sh"
    exit 1
fi

# 清理可能存在的旧PID文件
if [ -f "$PID_FILE" ]; then
    echo "🧹 清理旧的PID文件..."
    rm -f $PID_FILE
fi

# 确保logs目录存在
mkdir -p logs

# 启动机器人
echo "🚀 启动交易机器人..."
nohup python3 bot.py > $LOG_FILE 2>&1 &
PID=$!

# 保存PID
echo $PID > $PID_FILE

# 等待2秒检查是否启动成功
sleep 2

if ps -p $PID > /dev/null 2>&1; then
    echo "✅ 机器人启动成功!"
    echo "   PID: $PID"
    echo "   PID文件: $PID_FILE"
    echo "   日志文件: $LOG_FILE"
    echo ""
    echo "📋 常用命令:"
    echo "   查看日志: tail -f $LOG_FILE"
    echo "   查看状态: ps -p $PID"
    echo "   停止机器人: ./stop_bot.sh"
    echo ""
    echo "💡 提示: 建议监控日志确保正常运行"
else
    echo "❌ 机器人启动失败,请检查日志: $LOG_FILE"
    echo ""
    echo "常见问题排查:"
    echo "   1. 检查日志: tail -50 $LOG_FILE"
    echo "   2. 检查配置: python3 -c 'import config; print(config.validate_config())'"
    echo "   3. 检查API连接: python3 -c 'from trader import BitgetTrader; t=BitgetTrader(); print(t.exchange)'"
    rm -f $PID_FILE
    exit 1
fi
