#!/bin/bash
# Claude Code statusline - Professional Edition
# 优化：动态预警、全平台兼容、补全染色逻辑

# --- 颜色与样式定义 ---
RESET='\033[0m'
BOLD='\033[1m'
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
ORANGE='\033[38;5;208m'
GRAY='\033[90m'

# --- 工具函数：数值缩写 ---
format_number() {
    local num=$1
    if [[ -z "$num" || "$num" == "null" || "$num" == "0" ]]; then echo "0"; return; fi
    # 处理千万级/百万级/千级
    awk -v n="$num" 'BEGIN {
        if (n >= 1000000) printf "%.1fM", n/1000000;
        else if (n >= 1000) printf "%.1fk", n/1000;
        else print n;
    }'
}

# --- 1. 读取并验证输入 ---
input=$(cat)
if [[ -z "$input" ]]; then
    echo -e "${GRAY}Waiting for Claude data...${RESET}"
    exit 0
fi

# --- 2. 解析 JSON ---
if command -v jq &> /dev/null; then
    eval $(echo "$input" | jq -r '
        (.model.display_name // "Unknown") as $model |
        (.context_window.total_input_tokens // 0) as $it |
        (.context_window.total_output_tokens // 0) as $ot |
        (.context_window.current_usage.input_tokens // 0) as $ctx |
        (.context_window.max_input_tokens // 200000) as $max |
        (.version // "v?") as $ver |
        (.output_style.name // "default") as $style |
        (.cost.total_duration_ms // 0) as $dur |
        (.cost.total_lines_added // 0) as $la |
        (.cost.total_lines_removed // 0) as $lr |
        (.cost.total_cost_usd // 0) as $cost |
        "MODEL=\($model|@sh); IN_TK=\($it); OUT_TK=\($ot); CTX_TK=\($ctx); MAX_TK=\($max); VER=\($ver|@sh); STYLE=\($style|@sh); DUR=\($dur); ADDED=\($la); REMOVED=\($lr); COST=\($cost)"
    ')

    # 计算逻辑
    TOTAL_TK=$((IN_TK + OUT_TK))
    DUR_MIN=$((DUR / 60000))
    [ "$MAX_TK" -le 0 ] && MAX_TK=200000
    CTX_PCT=$(( CTX_TK * 100 / MAX_TK ))
    
    # 动态预警：根据上下文占比切换颜色
    COLOR_CTX=$YELLOW
    if [ $CTX_PCT -ge 90 ]; then COLOR_CTX=$RED; elif [ $CTX_PCT -ge 75 ]; then COLOR_CTX=$ORANGE; fi
    
    # 动态预警：单次会话成本超过 $5 或 $10 变色
    COLOR_COST=$YELLOW
    IS_HIGH_COST=$(awk -v c="$COST" 'BEGIN {print (c > 10.0 ? 2 : (c > 5.0 ? 1 : 0))}')
    [ $IS_HIGH_COST -eq 1 ] && COLOR_COST=$ORANGE
    [ $IS_HIGH_COST -eq 2 ] && COLOR_COST="${BOLD}${RED}"

    # 格式化展示值
    IN_FMT=$(format_number $IN_TK)
    OUT_FMT=$(format_number $OUT_TK)
    TOTAL_FMT=$(format_number $TOTAL_TK)
    CTX_FMT=$(format_number $CTX_TK)
    COST_FMT=$(printf "%.2f" $COST)

    # 第一行：核心统计 (带动态预警)
    echo -e "${BOLD}Model:${RESET} ${CYAN}${MODEL}${RESET} | ${BOLD}In:${RESET} ${GREEN}${IN_FMT}${RESET} | ${BOLD}Out:${RESET} ${GREEN}${OUT_FMT}${RESET} | ${BOLD}Total:${RESET} ${CYAN}${TOTAL_FMT}${RESET} | ${BOLD}Ctx:${RESET} ${COLOR_CTX}${CTX_FMT}${RESET} | ${BOLD}Ctx:${RESET} ${COLOR_CTX}${CTX_PCT}%${RESET}"

    # 第二行：会话详情 (带成本预警)
    echo -e "${CYAN}${VER}${RESET} | ${BOLD}Style:${RESET} ${CYAN}${STYLE}${RESET} | ${BOLD}Session:${RESET} ${YELLOW}${DUR_MIN}m${RESET} | (${GREEN}+${ADDED}${RESET},${RED}-${REMOVED}${RESET}) | ${BOLD}Cost:${RESET} ${COLOR_COST}\$${COST_FMT}${RESET}"
else
    echo -e "${RED}Error: jq not found${RESET}"
fi

# --- 3. 第三行：ccusage 深度集成 (补全染色逻辑) ---
if command -v ccusage &> /dev/null; then
    # 提取 ccusage 状态行
    ccusage_output=$(echo "$input" | ccusage statusline | sed -E 's/^🤖[^|]*\| //')
    
    # 精准染色：💰钱币、美元数值、Session标签、剩余时间、🔥开销速率、🧠配额
    echo "$ccusage_output" | sed -E \
        -e "s/(💰)/\x1b[1;33m\1\x1b[0m/g" \
        -e "s/(\\$[0-9]+\.[0-9]+)/\x1b[1;33m\1\x1b[0m/g" \
        -e "s/(session|today|block)/\x1b[36m\1\x1b[0m/g" \
        -e "s/(\([0-9]+h [0-9]+m left\))/\x1b[33m\1\x1b[0m/g" \
        -e "s/(🔥)/\x1b[1;31m\1\x1b[0m/g" \
        -e "s/(\\$[0-9]+\.[0-9]+\/hr)/\x1b[1;31m\1\x1b[0m/g" \
        -e "s/(🧠)/\x1b[1;35m\1\x1b[0m/g" \
        -e "s/([0-9,]+) \(([0-9]+)%\)/\x1b[1;35m\1\x1b[0m \x1b[35m(\2%)\x1b[0m/g"
fi
