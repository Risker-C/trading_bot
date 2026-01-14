#!/bin/bash
# 检查ML模型在真实环境中的表现

echo "=========================================="
echo "ML模型性能分析"
echo "=========================================="

echo -e "\n1. 最近的ML预测记录（最近20条）:"
grep "ML过滤结果" logs/info.log | tail -20

echo -e "\n2. ML预测统计:"
echo "   总预测次数:"
grep "ML过滤结果" logs/info.log | wc -l

echo -e "\n3. 平均质量分数趋势:"
grep "平均质量=" logs/info.log | tail -10 | awk -F'平均质量=' '{print $2}' | awk -F',' '{print "   " $1}'

echo -e "\n4. 当前配置:"
grep -E "ML_MODE|ML_QUALITY_THRESHOLD" config.py

echo -e "\n=========================================="
echo "建议:"
echo "=========================================="
echo "如果平均质量分数持续 >= 0.6，可以考虑切换到 filter 模式"
echo "修改 config.py: ML_MODE = 'filter'"
echo "然后重启机器人: ./stop_bot.sh && ./start_bot.sh"
