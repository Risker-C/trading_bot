# 飞书推送智能过滤功能说明文档

## 概述

飞书推送智能过滤功能是对交易机器人状态监控系统的重要优化，旨在解决飞书推送过于频繁和无用信息过多的问题。通过智能过滤算法，系统能够自动识别并过滤掉重复、无价值的推送，显著降低推送频率，提升信息质量。

**优化效果：**
- 推送频率从每天288次降低到约96次（降低67%）
- 无持仓且行情变化小时自动跳过推送
- 重复内容自动过滤
- 非交易活跃时段自动降频

## 功能特性

### 1. 推送间隔优化
- 状态监控推送间隔从5分钟调整为15分钟
- 每天推送次数从288次降低到96次
- 保持重要信息的及时性

### 2. 智能空闲过滤
- 自动检测是否有持仓
- 检测行情变化幅度
- 无持仓且行情变化小于0.5%时自动跳过推送
- 避免无意义的重复推送

### 3. 重复内容过滤
- 使用内容哈希算法检测完全相同的推送
- 使用相似度算法检测高度相似的推送（90%以上）
- 自动过滤重复信息，减少信息噪音

### 4. 非交易时段降频
- 识别非交易活跃时段（0-6点、22-24点）
- 非活跃时段推送间隔自动翻倍（15分钟→30分钟）
- 在保证监控的同时减少夜间打扰

### 5. 推送历史记录
- 记录最近100次推送历史
- 支持推送统计和分析
- 便于后续优化和调试

## 配置说明

### 配置文件位置
`config.py`

### 配置项详解

#### 1. 基础配置

```python
# 状态推送间隔（分钟）
STATUS_MONITOR_INTERVAL = 15  # 优化：从5分钟改为15分钟，减少推送频率
```

#### 2. 飞书推送过滤配置

```python
# 是否启用飞书推送智能过滤
ENABLE_FEISHU_PUSH_FILTER = True

# 行情变化阈值（只推送变化超过此值的行情）
FEISHU_PRICE_CHANGE_THRESHOLD = 0.005  # 0.5%，低于此值不推送行情变化

# 无持仓时是否简化推送内容
FEISHU_SIMPLIFY_NO_POSITION = True  # 无持仓时只推送关键信息

# 无持仓且无显著行情变化时是否跳过推送
FEISHU_SKIP_IDLE_PUSH = True  # 无持仓且行情变化小时跳过推送

# 推送频率限制（同类型推送的最小间隔，分钟）
FEISHU_MIN_PUSH_INTERVAL = {
    'status_monitor': 15,     # 状态监控最小间隔15分钟
    'market_report': 120,     # 市场报告最小间隔120分钟
    'trade': 0,               # 交易通知不限制（重要）
    'signal': 5,              # 信号通知最小间隔5分钟
    'risk_event': 0,          # 风控事件不限制（重要）
}

# 是否过滤重复内容推送
FEISHU_FILTER_DUPLICATE_CONTENT = True  # 内容与上次相同时跳过推送

# 重复内容判断的相似度阈值（0-1）
FEISHU_DUPLICATE_SIMILARITY_THRESHOLD = 0.9  # 90%相似度视为重复

# 是否在非交易时段降低推送频率
FEISHU_REDUCE_OFF_HOURS = True  # 非交易活跃时段降低推送

# 非交易活跃时段定义（小时，24小时制）
FEISHU_OFF_HOURS = list(range(0, 6)) + list(range(22, 24))  # 0-6点和22-24点

# 非交易时段推送间隔倍数
FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER = 2.0  # 非活跃时段间隔翻倍
```

## 使用方法

### 1. 启用智能过滤

智能过滤功能默认启用，无需额外配置。如需禁用，可在 `config.py` 中设置：

```python
ENABLE_FEISHU_PUSH_FILTER = False
```

### 2. 调整过滤阈值

根据实际需求调整行情变化阈值：

```python
# 更严格的过滤（减少推送）
FEISHU_PRICE_CHANGE_THRESHOLD = 0.01  # 1%

# 更宽松的过滤（增加推送）
FEISHU_PRICE_CHANGE_THRESHOLD = 0.002  # 0.2%
```

### 3. 自定义非交易时段

根据交易习惯自定义非活跃时段：

```python
# 只在深夜降频
FEISHU_OFF_HOURS = list(range(0, 6))  # 0-6点

# 扩大非活跃时段
FEISHU_OFF_HOURS = list(range(0, 8)) + list(range(20, 24))  # 0-8点和20-24点
```

### 4. 调整相似度阈值

根据需要调整重复内容判断的严格程度：

```python
# 更严格（只过滤完全相同的内容）
FEISHU_DUPLICATE_SIMILARITY_THRESHOLD = 0.95  # 95%

# 更宽松（过滤更多相似内容）
FEISHU_DUPLICATE_SIMILARITY_THRESHOLD = 0.85  # 85%
```

## 技术实现

### 核心模块

#### 1. FeishuPushFilter 类
位置：`status_monitor.py:110-321`

**主要功能：**
- 推送过滤决策
- 内容相似度计算
- 推送历史记录

**关键方法：**
- `should_filter()`: 判断是否应该过滤推送
- `_check_idle_push()`: 检查空闲推送
- `_check_duplicate_content()`: 检查重复内容
- `_check_off_hours()`: 检查非交易时段
- `record_push()`: 记录推送历史

#### 2. StatusMonitorScheduler 类
位置：`status_monitor.py:323-476`

**主要功能：**
- 状态监控调度
- 推送时机控制
- 过滤器集成

**关键属性：**
- `push_filter`: 推送过滤器实例
- `filtered_count`: 被过滤的推送次数

#### 3. StatusMonitorCollector 类
位置：`status_monitor.py:478-915`

**主要功能：**
- 状态数据收集
- 消息格式化
- 推送执行

**关键方法：**
- `collect_and_push()`: 收集数据并推送（集成过滤逻辑）

### 数据流程

```
主循环 (bot.py)
    ↓
更新价格历史 (status_monitor.update_price)
    ↓
检查推送时机 (status_monitor.check_and_push)
    ↓
收集状态数据 (collector.collect_all)
    ↓
格式化消息 (collector.format_message)
    ↓
应用过滤器 (push_filter.should_filter)
    ├─ 检查1: 空闲推送过滤
    ├─ 检查2: 重复内容过滤
    └─ 检查3: 非交易时段降频
    ↓
[过滤] → 记录日志，跳过推送
[通过] → 推送到飞书 → 记录推送历史
```

### 过滤算法

#### 1. 空闲推送检测
```python
def _check_idle_push(data):
    # 检查是否有持仓
    has_position = data['account_info']['has_position']
    if has_position:
        return False  # 有持仓，不过滤

    # 检查行情变化
    change_percent = abs(data['market_change']['change_percent'])
    if change_percent < threshold:
        return True  # 行情变化小，过滤

    return False
```

#### 2. 重复内容检测
```python
def _check_duplicate_content(message):
    # 计算内容哈希（移除时间戳）
    current_hash = calculate_hash(message)
    last_hash = calculate_hash(last_message)

    if current_hash == last_hash:
        return True  # 完全相同，过滤

    # 计算相似度
    similarity = calculate_similarity(message, last_message)
    if similarity >= threshold:
        return True  # 高度相似，过滤

    return False
```

#### 3. 非交易时段检测
```python
def _check_off_hours():
    current_hour = datetime.now().hour

    if current_hour in off_hours:
        elapsed = now - last_push_time
        required_interval = base_interval * multiplier

        if elapsed < required_interval:
            return True  # 未达到降频间隔，过滤

    return False
```

## 故障排查

### 问题1：推送完全停止

**可能原因：**
- 过滤阈值设置过于严格
- 长期无持仓且行情波动小

**解决方法：**
1. 检查配置项 `ENABLE_FEISHU_PUSH_FILTER`
2. 降低 `FEISHU_PRICE_CHANGE_THRESHOLD` 阈值
3. 临时禁用 `FEISHU_SKIP_IDLE_PUSH`
4. 查看日志中的过滤原因

### 问题2：仍然推送过于频繁

**可能原因：**
- 持仓状态频繁变化
- 行情波动较大
- 过滤器未启用

**解决方法：**
1. 确认 `ENABLE_FEISHU_PUSH_FILTER = True`
2. 提高 `STATUS_MONITOR_INTERVAL` 间隔
3. 提高 `FEISHU_PRICE_CHANGE_THRESHOLD` 阈值
4. 启用 `FEISHU_FILTER_DUPLICATE_CONTENT`

### 问题3：重要信息被过滤

**可能原因：**
- 相似度阈值设置过低
- 空闲过滤过于激进

**解决方法：**
1. 提高 `FEISHU_DUPLICATE_SIMILARITY_THRESHOLD` 到 0.95
2. 降低 `FEISHU_PRICE_CHANGE_THRESHOLD` 到 0.002
3. 禁用 `FEISHU_SKIP_IDLE_PUSH`
4. 检查日志确认过滤原因

### 问题4：夜间仍然频繁推送

**可能原因：**
- 非交易时段配置不正确
- 降频倍数设置过小

**解决方法：**
1. 检查 `FEISHU_OFF_HOURS` 配置
2. 提高 `FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER` 到 3.0
3. 确认 `FEISHU_REDUCE_OFF_HOURS = True`

### 调试方法

查看过滤日志：
```bash
# 查看过滤记录
grep "过滤推送" logs/info.log

# 查看推送统计
grep "状态监控" logs/info.log | grep -E "(推送成功|推送已过滤)"

# 实时监控
tail -f logs/info.log | grep -E "(push_filter|状态监控)"
```

## 性能优化

### 1. 内存优化
- 推送历史使用 `deque` 限制最大长度为100
- 自动清理过期数据
- 哈希计算使用 MD5（快速且足够准确）

### 2. CPU优化
- 相似度计算使用简化算法
- 只比较关键数据行
- 避免全文比较

### 3. 推送优化
- 过滤在推送前执行，避免无效API调用
- 记录推送历史，支持快速查询
- 异步推送（如果需要）

### 推荐配置

**保守配置（减少推送）：**
```python
STATUS_MONITOR_INTERVAL = 20
FEISHU_PRICE_CHANGE_THRESHOLD = 0.01
FEISHU_SKIP_IDLE_PUSH = True
FEISHU_FILTER_DUPLICATE_CONTENT = True
FEISHU_DUPLICATE_SIMILARITY_THRESHOLD = 0.85
FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER = 3.0
```

**平衡配置（推荐）：**
```python
STATUS_MONITOR_INTERVAL = 15
FEISHU_PRICE_CHANGE_THRESHOLD = 0.005
FEISHU_SKIP_IDLE_PUSH = True
FEISHU_FILTER_DUPLICATE_CONTENT = True
FEISHU_DUPLICATE_SIMILARITY_THRESHOLD = 0.9
FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER = 2.0
```

**激进配置（更多推送）：**
```python
STATUS_MONITOR_INTERVAL = 10
FEISHU_PRICE_CHANGE_THRESHOLD = 0.002
FEISHU_SKIP_IDLE_PUSH = False
FEISHU_FILTER_DUPLICATE_CONTENT = True
FEISHU_DUPLICATE_SIMILARITY_THRESHOLD = 0.95
FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER = 1.5
```

## 扩展开发

### 添加新的过滤规则

在 `FeishuPushFilter` 类中添加新的检查方法：

```python
def _check_custom_rule(self, data: Dict[str, Any]) -> tuple[bool, str]:
    """
    自定义过滤规则

    Returns:
        tuple: (是否过滤, 原因)
    """
    # 实现自定义逻辑
    if some_condition:
        return True, "自定义过滤原因"
    return False, ""
```

然后在 `should_filter` 方法中调用：

```python
def should_filter(self, data: Dict[str, Any], message: str) -> tuple[bool, str]:
    # ... 现有检查 ...

    # 检查4: 自定义规则
    should_filter, reason = self._check_custom_rule(data)
    if should_filter:
        self.logger.info(f"🔇 过滤推送: {reason}")
        return True, reason

    return False, ""
```

### 集成机器学习

可以使用机器学习模型预测推送的价值：

```python
def _check_ml_prediction(self, data: Dict[str, Any]) -> tuple[bool, str]:
    """
    使用ML模型预测推送价值
    """
    features = self._extract_features(data)
    value_score = ml_model.predict(features)

    if value_score < threshold:
        return True, f"ML预测价值低 ({value_score:.2f})"
    return False, ""
```

### 添加推送统计

扩展推送历史记录功能：

```python
def get_push_statistics(self) -> Dict[str, Any]:
    """获取推送统计信息"""
    total = len(self.push_history)
    if total == 0:
        return {}

    return {
        'total_pushes': total,
        'avg_interval': self._calculate_avg_interval(),
        'filter_rate': self.filtered_count / (total + self.filtered_count),
        'push_by_hour': self._group_by_hour()
    }
```

## 最佳实践

### 1. 初次部署
- 使用推荐的平衡配置
- 观察1-2天的推送情况
- 根据实际需求调整参数

### 2. 参数调优
- 每次只调整一个参数
- 观察至少4小时后再调整
- 记录调整前后的推送次数

### 3. 监控建议
- 定期检查过滤日志
- 统计推送频率和过滤率
- 关注是否有重要信息被过滤

### 4. 特殊场景
- 重大行情时临时降低阈值
- 长假期间提高过滤强度
- 测试期间可以禁用过滤

### 5. 与其他功能配合
- 交易通知不受过滤影响（重要）
- 风控事件不受过滤影响（重要）
- 市场报告有独立的推送间隔

## 更新日志

### v1.0.0 (2025-12-21)
- ✨ 初始版本发布
- ✨ 实现智能空闲过滤
- ✨ 实现重复内容过滤
- ✨ 实现非交易时段降频
- ✨ 推送间隔从5分钟优化到15分钟
- 📝 完整的配置说明和使用文档

## 相关文档

- [状态监控功能说明](status_monitor.md)
- [飞书通知配置说明](../README.md#飞书通知配置)
- [日志系统说明](../README.md#日志系统)

## 技术支持

如有问题或建议，请：
1. 查看本文档的故障排查章节
2. 检查日志文件 `logs/info.log`
3. 提交 Issue 到项目仓库

---

**注意：** 本功能旨在优化推送体验，不会影响交易通知和风控事件的及时性。所有重要通知（交易、风控）都不受过滤影响。
