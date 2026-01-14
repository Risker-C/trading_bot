#!/bin/bash
# Trading Bot 停止脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# PID文件
TRADER_PID_FILE="$PROJECT_ROOT/.trader.pid"
API_PID_FILE="$PROJECT_ROOT/.api.pid"

echo -e "${YELLOW}正在停止所有服务...${NC}\n"

STOPPED=0

# 停止交易机器人
if [ -f "$TRADER_PID_FILE" ]; then
    TRADER_PID=$(cat "$TRADER_PID_FILE")
    if kill -0 "$TRADER_PID" 2>/dev/null; then
        echo -e "${YELLOW}停止交易机器人 (PID: $TRADER_PID)${NC}"
        kill -TERM "$TRADER_PID" 2>/dev/null || true
        # 等待最多10秒
        for i in {1..10}; do
            if ! kill -0 "$TRADER_PID" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        # 强制杀死
        if kill -0 "$TRADER_PID" 2>/dev/null; then
            echo -e "${RED}强制停止交易机器人${NC}"
            kill -9 "$TRADER_PID" 2>/dev/null || true
        fi
        STOPPED=$((STOPPED + 1))
    fi
    rm -f "$TRADER_PID_FILE"
fi

# 停止API服务
if [ -f "$API_PID_FILE" ]; then
    API_PID=$(cat "$API_PID_FILE")
    if kill -0 "$API_PID" 2>/dev/null; then
        echo -e "${YELLOW}停止API服务 (PID: $API_PID)${NC}"
        kill -TERM "$API_PID" 2>/dev/null || true
        # 等待最多10秒
        for i in {1..10}; do
            if ! kill -0 "$API_PID" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        # 强制杀死
        if kill -0 "$API_PID" 2>/dev/null; then
            echo -e "${RED}强制停止API服务${NC}"
            kill -9 "$API_PID" 2>/dev/null || true
        fi
        STOPPED=$((STOPPED + 1))
    fi
    rm -f "$API_PID_FILE"
fi

# 清理可能遗留的进程
pkill -f "uvicorn apps.api.main:app" 2>/dev/null || true
pkill -f "python.*main.py live" 2>/dev/null || true

if [ $STOPPED -eq 0 ]; then
    echo -e "${YELLOW}没有运行中的服务${NC}"
else
    echo -e "\n${GREEN}✓ 已停止 $STOPPED 个服务${NC}"
fi
