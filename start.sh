#!/bin/bash
# Trading Bot 统一启动脚本
# 同时启动量化交易机器人和API服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# PID文件
TRADER_PID_FILE="$PROJECT_ROOT/.trader.pid"
API_PID_FILE="$PROJECT_ROOT/.api.pid"

# 日志目录
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}正在停止所有服务...${NC}"

    # 停止交易机器人
    if [ -f "$TRADER_PID_FILE" ]; then
        TRADER_PID=$(cat "$TRADER_PID_FILE")
        if kill -0 "$TRADER_PID" 2>/dev/null; then
            echo -e "${YELLOW}停止交易机器人 (PID: $TRADER_PID)${NC}"
            kill -TERM "$TRADER_PID" 2>/dev/null || true
            wait "$TRADER_PID" 2>/dev/null || true
        fi
        rm -f "$TRADER_PID_FILE"
    fi

    # 停止API服务
    if [ -f "$API_PID_FILE" ]; then
        API_PID=$(cat "$API_PID_FILE")
        if kill -0 "$API_PID" 2>/dev/null; then
            echo -e "${YELLOW}停止API服务 (PID: $API_PID)${NC}"
            kill -TERM "$API_PID" 2>/dev/null || true
            wait "$API_PID" 2>/dev/null || true
        fi
        rm -f "$API_PID_FILE"
    fi

    echo -e "${GREEN}所有服务已停止${NC}"
    exit 0
}

# 捕获退出信号
trap cleanup SIGINT SIGTERM EXIT

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Trading Bot 启动中...${NC}"
echo -e "${GREEN}========================================${NC}"

# 启动API服务
echo -e "\n${YELLOW}[1/2] 启动API服务...${NC}"
cd "$PROJECT_ROOT"
nohup python3 -m uvicorn apps.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    > "$LOG_DIR/api.log" 2>&1 &
API_PID=$!
echo $API_PID > "$API_PID_FILE"
echo -e "${GREEN}✓ API服务已启动 (PID: $API_PID)${NC}"
echo -e "  日志: $LOG_DIR/api.log"
echo -e "  访问: http://localhost:8000/docs"

# 等待API服务就绪
sleep 2

# 启动交易机器人
echo -e "\n${YELLOW}[2/2] 启动交易机器人...${NC}"
nohup python3 main.py live \
    > "$LOG_DIR/trader.log" 2>&1 &
TRADER_PID=$!
echo $TRADER_PID > "$TRADER_PID_FILE"
echo -e "${GREEN}✓ 交易机器人已启动 (PID: $TRADER_PID)${NC}"
echo -e "  日志: $LOG_DIR/trader.log"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  所有服务已启动完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\n服务状态:"
echo -e "  ${GREEN}•${NC} API服务      PID: $API_PID"
echo -e "  ${GREEN}•${NC} 交易机器人   PID: $TRADER_PID"
echo -e "\n实时日志:"
echo -e "  tail -f $LOG_DIR/api.log"
echo -e "  tail -f $LOG_DIR/trader.log"
echo -e "\n按 ${YELLOW}Ctrl+C${NC} 停止所有服务\n"

# 持续运行并监控进程
while true; do
    # 检查API服务
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo -e "${RED}[ERROR] API服务已停止，退出...${NC}"
        cleanup
    fi

    # 检查交易机器人
    if ! kill -0 "$TRADER_PID" 2>/dev/null; then
        echo -e "${RED}[ERROR] 交易机器人已停止，退出...${NC}"
        cleanup
    fi

    sleep 5
done
