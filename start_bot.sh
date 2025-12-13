#!/bin/bash

# 交易机器人启动脚本

BOT_DIR="/root/trading_bot"
PID_FILE="$BOT_DIR/bot.pid"
LOG_FILE="$BOT_DIR/logs/bot_runtime.log"

cd $BOT_DIR

# 检查是否已经在运行
if [ -f "$PID_FILE" ]; then
    PID=$(cat $PID_FILE)
    if ps -p $PID > /dev/null 2>&1; then
        echo "❌ 机器人已在运行 (PID: $PID)"
        echo "如需重启,请先运行: ./stop_bot.sh"
        exit 1
    else
        echo "⚠️  发现旧的PID文件,清理中..."
        rm -f $PID_FILE
    fi
fi

# 确保logs目录存在
mkdir -p logs

# 启动机器人
echo "🚀 启动交易机器人..."
nohup python3 bot.py > $LOG_FILE 2>&1 &
PID=$!

# 保存PID
echo $PID > $PID_FILE

# 等待1秒检查是否启动成功
sleep 1

if ps -p $PID > /dev/null 2>&1; then
    echo "✅ 机器人启动成功!"
    echo "   PID: $PID"
    echo "   日志文件: $LOG_FILE"
    echo ""
    echo "📋 常用命令:"
    echo "   查看日志: tail -f $LOG_FILE"
    echo "   查看状态: ps -p $PID"
    echo "   停止机器人: ./stop_bot.sh"
else
    echo "❌ 机器人启动失败,请检查日志: $LOG_FILE"
    rm -f $PID_FILE
    exit 1
fi
