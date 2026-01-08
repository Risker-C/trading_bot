# 配置验证器功能说明文档

## 概述

配置验证器使用 Pydantic 提供类型安全的配置验证，在机器人启动时自动检查配置参数的有效性，防止因配置错误导致的运行时异常。

**核心价值：**
- 🛡️ 类型安全：编译时捕获配置错误
- ⚡ 快速失败：启动时立即发现问题
- 📊 智能验证：自动检查参数范围和组合风险
- 🔧 易于扩展：基于 Pydantic 模型

## 功能特性

1. **风险配置验证（RiskConfig）**
   - 止损/止盈/移动止损比例范围检查
   - 杠杆倍数合理性验证
   - 仓位与杠杆组合风险评估

2. **交易所配置验证（ExchangeConfig）**
   - API 密钥长度验证
   - 保证金模式合法性检查
   - 交易对格式验证

3. **策略配置验证（StrategyConfig）**
   - 策略列表非空检查
   - 信号强度/一致性范围验证

## 配置说明

### 配置文件位置
- 主配置：`config.py`
- 验证模块：`config_validator.py`

### 配置项详解

**RiskConfig：**
```python
stop_loss_percent: float      # 止损比例 (1%-10%)
take_profit_percent: float    # 止盈比例 (1%-20%)
trailing_stop_percent: float  # 移动止损比例 (0.5%-10%)
leverage: int                 # 杠杆倍数 (1-125)
position_size_percent: float  # 仓位比例 (1%-50%)
```

**验证规则：**
- 杠杆 > 20x 时发出警告
- 单笔最大损失 > 2% 时发出警告

## 使用方法

### 自动验证（已集成）

机器人启动时自动验证：
```python
# bot.py 中已集成
from config_validator import validate_config

if not validate_config(config):
    raise ValueError("配置验证失败")
```

### 手动验证

```bash
# 运行验证
python3 config_validator.py
```

### 测试验证

```bash
# 运行测试用例
python3 scripts/test_config_validator.py
```

## 技术实现

### 核心模块

**config_validator.py：**
- `RiskConfig` - 风险配置模型
- `ExchangeConfig` - 交易所配置模型
- `StrategyConfig` - 策略配置模型
- `validate_config()` - 验证函数

### 数据流程

```
config.py → validate_config() → Pydantic Models → 验证通过/失败
                                      ↓
                              field_validator 检查
                                      ↓
                              返回 True/False
```

## 故障排查

### 问题1：ValidationError

**现象：** 启动时抛出 ValidationError

**原因：** 配置参数超出范围

**解决：**
```python
# 检查配置值
python3 -c "import config; print(config.LEVERAGE)"

# 修改 config.py 中的参数
LEVERAGE = 10  # 确保在 1-125 范围内
```

### 问题2：导入错误

**现象：** ModuleNotFoundError: No module named 'pydantic'

**解决：**
```bash
pip install pydantic>=2.0.0
```

## 性能优化

- ✅ 验证只在启动时执行一次
- ✅ 使用 Pydantic V2（性能提升 5-50x）
- ✅ 无运行时性能影响

## 扩展开发

### 添加新的配置模型

```python
class MLConfig(BaseModel):
    """ML配置"""
    enable_ml_filter: bool = Field(False)
    ml_quality_threshold: float = Field(0.6, ge=0.0, le=1.0)

    @field_validator('ml_quality_threshold')
    @classmethod
    def validate_threshold(cls, v):
        if v < 0.5:
            print("⚠️ ML质量阈值较低，可能过滤不足")
        return v
```

### 集成到验证函数

```python
def validate_config(config_module):
    # ... 现有验证

    # 添加新验证
    ml_config = MLConfig(
        enable_ml_filter=config_module.ENABLE_ML_FILTER,
        ml_quality_threshold=config_module.ML_QUALITY_THRESHOLD,
    )
    print("✅ ML配置验证通过")
```

## 最佳实践

1. **启动前验证**：每次修改配置后先运行验证
2. **范围检查**：使用 `ge`/`le` 限制参数范围
3. **组合验证**：检查参数之间的关系（如仓位×杠杆）
4. **警告提示**：对高风险配置发出警告

## 更新日志

- **2026-01-08**: 初始版本，支持风险/交易所/策略配置验证

## 相关文档

- [异步I/O实施指南](async_io_implementation_guide.md)
- [数据库开发规范](database_standards.md)
