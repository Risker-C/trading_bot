#!/bin/bash

# 交易机器人停止脚本

BOT_DIR="/root/trading_bot"
PID_FILE="$BOT_DIR/bot.pid"

cd $BOT_DIR

# 检查PID文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo "❌ 未找到PID文件,机器人可能未运行"
    exit 1
fi

PID=$(cat $PID_FILE)

# 检查进程是否存在
if ! ps -p $PID > /dev/null 2>&1; then
    echo "⚠️  进程不存在 (PID: $PID)"
    echo "清理PID文件..."
    rm -f $PID_FILE
    exit 1
fi

# 停止进程
echo "🛑 停止交易机器人 (PID: $PID)..."
kill $PID

# 等待进程结束
for i in {1..10}; do
    if ! ps -p $PID > /dev/null 2>&1; then
        echo "✅ 机器人已停止"
        rm -f $PID_FILE
        exit 0
    fi
    sleep 1
done

# 如果还没停止,强制结束
echo "⚠️  进程未响应,强制结束..."
kill -9 $PID
sleep 1

if ! ps -p $PID > /dev/null 2>&1; then
    echo "✅ 机器人已强制停止"
    rm -f $PID_FILE
else
    echo "❌ 无法停止进程,请手动处理: kill -9 $PID"
    exit 1
fi
