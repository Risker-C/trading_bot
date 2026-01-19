#!/bin/bash
# Trading Bot 重启脚本 - 拉取最新代码并重启服务

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo -e "${YELLOW}[1/3] 拉取最新代码...${NC}"
git pull

echo -e "\n${YELLOW}[2/3] 停止服务...${NC}"
bash stop.sh

echo -e "\n${YELLOW}[3/3] 启动服务...${NC}"
bash start.sh
