# ML信号过滤器功能说明文档

## 概述

ML信号过滤器是一个基于机器学习的信号质量评估系统，用于预测交易信号的盈利概率，过滤低质量信号，从而提高交易胜率和盈亏比。

### 核心价值

- **提高胜率**：通过过滤低质量信号，预期将做多胜率从31.82%提升到40-45%
- **降低风险**：减少不必要的交易，降低交易频率30-40%
- **可解释性**：提供信号质量分数，帮助理解为什么某些信号被过滤
- **渐进式部署**：支持影子模式，可以在不影响实际交易的情况下验证效果

### 工作原理

```
技术指标策略 → 生成信号 → ML过滤器 → 现有过滤链 → 执行交易
                              ↓
                    预测信号质量 (0-1分数)
                    过滤低质量信号 (<阈值)
```

---

## 功能特性

### 1. 三种运行模式

| 模式 | 说明 | 影响交易 | 适用场景 |
|------|------|---------|---------|
| **shadow** | 影子模式 | ❌ 否 | 初期测试、数据收集、效果验证 |
| **filter** | 过滤模式 | ✅ 是 | 正式使用、实际过滤信号 |
| **off** | 关闭 | ❌ 否 | 禁用ML功能 |

### 2. 50+个特征维度

- **技术指标**：RSI、MACD、布林带、ATR、ADX、EMA等
- **价格动量**：多周期价格变化、ROC、动量加速度
- **成交量**：成交量比率、成交量趋势、成交量突增
- **波动率**：历史波动率、波动率比率、ATR相对波动率
- **信号特征**：信号强度、置信度、策略一致性
- **市场状态**：市场制度、趋势强度、价格位置
- **时间特征**：小时、星期、交易时段
- **价格形态**：K线形态、高低点趋势

### 3. 智能信号质量评估

- 使用LightGBM模型预测信号盈利概率
- 输出0-1的质量分数
- 可配置质量阈值（默认0.6）
- 支持模型热更新

### 4. 完整的日志和监控

- 记录每个信号的预测结果
- 统计过滤率和平均质量分数
- 可选的详细日志输出
- 支持数据库记录（用于后续分析）

---

## 配置说明

### 配置文件位置

`config.py`

### 配置项详解

```python
# ==================== ML信号过滤器配置 ====================

# 是否启用ML信号过滤器
ENABLE_ML_FILTER = False  # 默认禁用，需要先训练模型

# ML运行模式
ML_MODE = "shadow"  # shadow: 影子模式, filter: 过滤模式, off: 关闭

# ML模型路径
ML_MODEL_PATH = "models/signal_quality_v1.pkl"

# ML信号质量阈值（0-1，只执行质量分数>=此值的信号）
ML_QUALITY_THRESHOLD = 0.6  # 60%质量分数

# ML最小信号数量（如果过滤后信号数量<此值，则不过滤）
ML_MIN_SIGNALS = 1

# 是否记录ML预测结果到数据库
ML_LOG_PREDICTIONS = True

# 是否在日志中显示ML预测详情
ML_VERBOSE_LOGGING = True

# ML特征工程配置
ML_FEATURE_LOOKBACK = 20  # 特征计算回溯周期（K线数量）

# ML模型更新配置
ML_AUTO_RETRAIN = False  # 是否自动重新训练模型
ML_RETRAIN_INTERVAL_DAYS = 30  # 重新训练间隔（天）
ML_MIN_TRAINING_SAMPLES = 100  # 最小训练样本数
```

### 配置建议

**初期（影子模式）**：
```python
ENABLE_ML_FILTER = True
ML_MODE = "shadow"
ML_VERBOSE_LOGGING = True
```

**验证期（灰度模式）**：
```python
ENABLE_ML_FILTER = True
ML_MODE = "filter"
ML_QUALITY_THRESHOLD = 0.7  # 提高阈值，更保守
ML_VERBOSE_LOGGING = True
```

**正式使用**：
```python
ENABLE_ML_FILTER = True
ML_MODE = "filter"
ML_QUALITY_THRESHOLD = 0.6
ML_VERBOSE_LOGGING = False  # 减少日志
```

---

## 使用方法

### 第一步：训练模型

#### 方法1：使用演示模型（快速测试）

```bash
# 训练演示模型（使用模拟数据）
python3 model_trainer.py
```

这会生成一个演示模型用于测试，但**不适合实际交易**。

#### 方法2：训练真实模型（推荐）

1. **收集历史数据**（至少100笔交易，建议3-6个月）
   ```bash
   # 运行机器人收集数据
   ./start_bot.sh
   ```

2. **实现数据准备流程**
   - 从交易所API获取历史K线数据
   - 计算技术指标
   - 匹配开仓和平仓记录
   - 提取特征和生成标签

3. **训练模型**
   ```bash
   python3 model_trainer.py
   ```

### 第二步：启用影子模式

修改 `config.py`：
```python
ENABLE_ML_FILTER = True
ML_MODE = "shadow"
```

重启机器人：
```bash
./stop_bot.sh
./start_bot.sh
```

### 第三步：观察和验证

查看日志：
```bash
tail -f logs/trading_bot.log | grep "ML"
```

观察指标：
- ML预测的质量分数
- 如果使用过滤模式，会过滤掉多少信号
- 被过滤的信号实际表现如何

### 第四步：切换到过滤模式

如果影子模式验证效果良好（建议至少2-4周），切换到过滤模式：

```python
ENABLE_ML_FILTER = True
ML_MODE = "filter"
ML_QUALITY_THRESHOLD = 0.6  # 根据验证结果调整
```

### 第五步：持续优化

- 定期重新训练模型（建议每月一次）
- 根据实际表现调整质量阈值
- 监控过滤率和胜率变化

---

## 技术实现

### 核心模块

#### 1. feature_engineer.py - 特征工程

**功能**：从市场数据和信号信息中提取50+个特征

**核心类**：
```python
class FeatureEngineer:
    def extract_features(self, df: pd.DataFrame, signal_info: Dict) -> pd.DataFrame:
        """提取特征"""
```

**特征类别**：
- 技术指标特征（15个）
- 价格动量特征（6个）
- 成交量特征（3个）
- 波动率特征（7个）
- 信号特征（6个）
- 市场状态特征（3个）
- 时间特征（5个）
- 价格形态特征（6个）

#### 2. ml_predictor.py - ML预测器

**功能**：加载模型、预测信号质量、过滤信号

**核心类**：
```python
class MLSignalPredictor:
    def predict_signal_quality(self, df: pd.DataFrame, signal: TradeSignal) -> float:
        """预测信号质量（0-1）"""

    def filter_signals(self, signals: List[TradeSignal], df: pd.DataFrame) -> Tuple[List[TradeSignal], List[Dict]]:
        """过滤信号列表"""
```

**单例模式**：
```python
predictor = get_ml_predictor()  # 全局单例
```

#### 3. model_trainer.py - 模型训练

**功能**：训练LightGBM模型

**核心类**：
```python
class ModelTrainer:
    def train_model(self, X: pd.DataFrame, y: pd.Series):
        """训练模型"""

    def save_model(self, output_path: str):
        """保存模型"""
```

### 数据流程

```
1. 策略生成信号
   ↓
2. bot.py调用ml_predictor.filter_signals()
   ↓
3. ml_predictor调用feature_engineer.extract_features()
   ↓
4. 提取50+个特征
   ↓
5. 模型预测质量分数
   ↓
6. 根据阈值过滤信号
   ↓
7. 返回过滤后的信号列表
   ↓
8. 继续现有过滤链（趋势过滤、方向过滤等）
```

### 模型文件格式

模型文件（`models/signal_quality_v1.pkl`）包含：
```python
{
    'model': LGBMClassifier,  # 训练好的模型
    'scaler': StandardScaler,  # 特征标准化器
    'feature_names': List[str],  # 特征名称列表
    'trained_at': str,  # 训练时间
    'config': Dict  # 训练配置
}
```

---

## 故障排查

### 问题1：模型文件不存在

**现象**：
```
ML模型文件不存在: models/signal_quality_v1.pkl
ML预测器将在影子模式下运行（不影响交易）
```

**解决方法**：
1. 运行 `python3 model_trainer.py` 训练模型
2. 或者禁用ML功能：`ENABLE_ML_FILTER = False`

### 问题2：缺少依赖包

**现象**：
```
✗ 缺少依赖包: No module named 'lightgbm'
```

**解决方法**：
```bash
pip install lightgbm scikit-learn joblib
```

### 问题3：特征提取失败

**现象**：
```
✗ ML预测失败: KeyError: 'rsi'
```

**解决方法**：
- 检查K线数据是否包含必要的技术指标
- 确保indicators.py正确计算了所有指标
- 查看feature_engineer.py的默认值处理

### 问题4：过滤率过高

**现象**：
- 90%以上的信号被过滤
- 几乎没有交易

**解决方法**：
1. 降低质量阈值：`ML_QUALITY_THRESHOLD = 0.5`
2. 检查模型是否过拟合
3. 重新训练模型

### 问题5：过滤率过低

**现象**：
- 几乎所有信号都通过
- ML过滤没有效果

**解决方法**：
1. 提高质量阈值：`ML_QUALITY_THRESHOLD = 0.7`
2. 检查模型是否欠拟合
3. 增加训练数据量

---

## 性能优化

### 1. 特征计算优化

**问题**：特征提取耗时较长

**优化方案**：
- 缓存技术指标计算结果
- 只计算必要的特征
- 使用向量化操作

### 2. 模型推理优化

**问题**：模型预测延迟

**优化方案**：
- 使用CPU推理（LightGBM已经很快）
- 批量预测多个信号
- 考虑使用ONNX Runtime加速

### 3. 内存优化

**问题**：内存占用过高

**优化方案**：
- 限制特征计算的回溯周期
- 定期清理预测历史
- 使用float32代替float64

---

## 扩展开发

### 1. 添加新特征

编辑 `feature_engineer.py`：

```python
def _extract_custom_features(self, df: pd.DataFrame) -> Dict:
    """提取自定义特征"""
    features = {}

    # 添加你的特征
    features['my_feature'] = ...

    return features
```

然后在 `extract_features()` 中调用：
```python
features.update(self._extract_custom_features(df))
```

### 2. 使用不同的模型

编辑 `model_trainer.py`：

```python
from xgboost import XGBClassifier

self.model = XGBClassifier(
    n_estimators=100,
    learning_rate=0.05,
    max_depth=5
)
```

### 3. 集成到其他过滤器

ML预测器可以与其他过滤器组合使用：

```python
# 在bot.py中
if ml_quality_score > 0.8 and trend_pass and direction_pass:
    # 高质量信号，直接执行
    execute_trade()
elif ml_quality_score > 0.6:
    # 中等质量信号，需要Claude分析
    claude_result = self.claude_analyzer.analyze_signal(...)
```

### 4. 实现自动重训练

```python
# 在bot.py中添加定时任务
if should_retrain():
    trainer = ModelTrainer()
    trainer.train_model(X, y)
    trainer.save_model()
    self.ml_predictor.load_model()  # 热更新
```

---

## 最佳实践

### 1. 数据收集

- **最少数据量**：100笔交易（约1-2周）
- **推荐数据量**：500笔交易（约1-2个月）
- **理想数据量**：1000+笔交易（约3-6个月）

### 2. 模型训练

- **训练频率**：每月一次
- **验证方法**：时间序列交叉验证
- **评估指标**：AUC-ROC、精确率、召回率
- **过拟合检测**：训练集和测试集性能差异<5%

### 3. 阈值调整

| 胜率目标 | 建议阈值 | 过滤率 | 适用场景 |
|---------|---------|--------|---------|
| 35-40% | 0.5 | 20-30% | 激进策略 |
| 40-45% | 0.6 | 30-40% | 平衡策略（推荐） |
| 45-50% | 0.7 | 40-50% | 保守策略 |
| 50%+ | 0.8 | 50-60% | 极保守策略 |

### 4. 监控指标

**每日监控**：
- 过滤率（filtered_signals / total_predictions）
- 平均质量分数
- 被过滤信号的实际表现

**每周监控**：
- 胜率变化
- 盈亏比变化
- 交易频率变化

**每月监控**：
- 模型性能衰减
- 特征重要性变化
- 是否需要重新训练

### 5. 风险控制

- **影子模式验证**：至少2-4周
- **灰度上线**：先用小仓位测试
- **回退机制**：随时可以禁用ML功能
- **人工审核**：定期检查被过滤的信号

---

## 更新日志

### v1.0.0 (2025-12-21)

**初始版本**

- ✅ 实现特征工程模块（50+个特征）
- ✅ 实现ML预测器模块（支持3种运行模式）
- ✅ 实现模型训练脚本
- ✅ 集成到bot.py主程序
- ✅ 支持影子模式和过滤模式
- ✅ 完整的日志和监控

**已知限制**：
- 模型训练需要手动实现数据准备流程
- 暂不支持自动重训练
- 暂不支持多模型集成

**后续计划**：
- 实现完整的数据准备流程
- 添加自动重训练功能
- 支持模型A/B测试
- 添加更多特征维度

---

## 相关文档

- [预测技术应用分析](prediction_tech_analysis.md) - 预测技术的详细分析和对比
- [交易机器人性能优化](trading_optimization_2024-12.md) - 整体性能优化方案
- [开多胜率修复](long_win_rate_fix.md) - 做多胜率低的修复方案
- [README.md](../README.md) - 项目总体说明

---

## 技术支持

如有问题，请：
1. 查看本文档的故障排查章节
2. 查看日志文件：`logs/trading_bot.log`
3. 运行测试用例：`python3 scripts/test_ml_signal_filter.py`
4. 提交Issue到项目仓库

---

**文档版本**: v1.0.0
**创建日期**: 2025-12-21
**最后更新**: 2025-12-21
**作者**: Trading Bot Development Team
