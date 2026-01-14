#!/bin/bash

# 交易机器人停止脚本

BOT_DIR="/root/trading_bot"
PID_FILE="$BOT_DIR/bot.pid"

cd $BOT_DIR

# 查找所有运行中的 bot.py 进程
BOT_PIDS=$(pgrep -f "python3 bot.py" || true)

if [ -z "$BOT_PIDS" ]; then
    echo "✅ 没有运行中的机器人进程"
    # 清理可能存在的旧PID文件
    if [ -f "$PID_FILE" ]; then
        echo "🧹 清理旧的PID文件..."
        rm -f $PID_FILE
    fi
    exit 0
fi

echo "🔍 发现运行中的机器人进程:"
echo "$BOT_PIDS" | while read pid; do
    echo "   PID: $pid"
done

# 停止所有进程
echo ""
echo "🛑 停止所有机器人进程..."
for PID in $BOT_PIDS; do
    echo "   停止 PID: $PID"
    kill $PID 2>/dev/null || true
done

# 等待进程结束
echo "⏳ 等待进程结束..."
for i in {1..10}; do
    REMAINING=$(pgrep -f "python3 bot.py" || true)
    if [ -z "$REMAINING" ]; then
        echo "✅ 所有机器人进程已停止"
        rm -f $PID_FILE
        exit 0
    fi
    sleep 1
done

# 如果还有进程未停止,强制结束
REMAINING=$(pgrep -f "python3 bot.py" || true)
if [ -n "$REMAINING" ]; then
    echo "⚠️  部分进程未响应,强制结束..."
    for PID in $REMAINING; do
        echo "   强制停止 PID: $PID"
        kill -9 $PID 2>/dev/null || true
    done
    sleep 1
fi

# 最终检查
REMAINING=$(pgrep -f "python3 bot.py" || true)
if [ -z "$REMAINING" ]; then
    echo "✅ 所有机器人进程已强制停止"
    rm -f $PID_FILE
    exit 0
else
    echo "❌ 仍有进程无法停止:"
    echo "$REMAINING" | while read pid; do
        echo "   PID: $pid"
    done
    echo "请手动处理: kill -9 <PID>"
    exit 1
fi
