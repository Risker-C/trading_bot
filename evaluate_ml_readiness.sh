#!/bin/bash
# 评估ML模型是否准备好切换到filter模式

echo "=========================================="
echo "ML模型就绪评估"
echo "=========================================="

# 1. 统计预测次数
total_predictions=$(grep "ML过滤结果" logs/info.log | wc -l)
echo -e "\n1. 预测次数: $total_predictions"

if [ $total_predictions -lt 50 ]; then
    echo "   ❌ 数据不足（需要至少50次）"
    echo "   建议：继续在shadow模式下运行"
    exit 1
else
    echo "   ✅ 数据充足"
fi

# 2. 统计预测成功率
nan_count=$(grep "平均质量=nan" logs/info.log | wc -l)
success_rate=$(echo "scale=2; ($total_predictions - $nan_count) * 100 / $total_predictions" | bc)
echo -e "\n2. 预测成功率: ${success_rate}%"

if (( $(echo "$success_rate < 90" | bc -l) )); then
    echo "   ⚠️  成功率偏低（建议>90%）"
    echo "   失败次数: $nan_count"
else
    echo "   ✅ 成功率良好"
fi

# 3. 计算平均质量分数
echo -e "\n3. 质量分数分析:"
grep "平均质量=" logs/info.log | grep -v "nan" | awk -F'平均质量=' '{print $2}' | awk -F',' '{print $1}' > /tmp/ml_scores.txt

if [ -s /tmp/ml_scores.txt ]; then
    avg_score=$(awk '{sum+=$1; count++} END {print sum/count}' /tmp/ml_scores.txt)
    echo "   平均质量分数: $avg_score"

    if (( $(echo "$avg_score >= 0.6" | bc -l) )); then
        echo "   ✅ 质量优秀（>= 60%）"
        quality_ok=1
    elif (( $(echo "$avg_score >= 0.4" | bc -l) )); then
        echo "   ⚠️  质量中等（40-60%）"
        echo "   建议：可以降低阈值到 0.4-0.5"
        quality_ok=0
    else
        echo "   ❌ 质量偏低（< 40%）"
        echo "   建议：考虑重新训练模型"
        quality_ok=0
    fi
else
    echo "   ❌ 没有有效的质量分数"
    quality_ok=0
fi

# 4. 最终建议
echo -e "\n=========================================="
echo "最终评估结果"
echo "=========================================="

if [ $total_predictions -ge 50 ] && (( $(echo "$success_rate >= 90" | bc -l) )) && [ $quality_ok -eq 1 ]; then
    echo "✅ ML模型已准备好切换到filter模式！"
    echo ""
    echo "执行以下步骤启用："
    echo "1. 编辑 config.py，修改："
    echo "   ML_MODE = 'filter'"
    echo ""
    echo "2. 重启机器人："
    echo "   ./stop_bot.sh && ./start_bot.sh"
    echo ""
    echo "3. 监控效果："
    echo "   tail -f logs/info.log | grep ML"
else
    echo "⚠️  ML模型尚未准备好"
    echo ""
    echo "建议："
    echo "- 继续在shadow模式下运行"
    echo "- 积累更多真实交易数据"
    echo "- 1周后再次运行此脚本评估"
fi

rm -f /tmp/ml_scores.txt
