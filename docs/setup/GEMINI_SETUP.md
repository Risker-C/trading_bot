# Gemini API 配置指南

## 问题诊断

当前测试失败的原因：
- ❌ API Key 无效
- ⚠️ SDK 已弃用（`google.generativeai` → `google.genai`）

## 解决方案

### 方案 1: 使用 Google Gemini API（直接调用）

#### 1.1 获取有效的 API Key

访问 Google AI Studio 获取 API Key：
```
https://makersuite.google.com/app/apikey
```

#### 1.2 配置环境变量

```bash
# 方式 1: 临时设置
export GEMINI_API_KEY="your_actual_api_key_here"

# 方式 2: 添加到 .env 文件
echo "GEMINI_API_KEY=your_actual_api_key_here" >> .env
```

#### 1.3 更新 SDK（推荐）

```bash
# 卸载旧版本
pip uninstall google-generativeai -y

# 安装新版本
pip install google-genai
```

### 方案 2: 使用 Claude Code 的 collaborating-with-gemini 技能

这个技能使用 Gemini CLI 工具，不需要直接配置 API Key。

#### 2.1 检查技能是否可用

```bash
# 在 Claude Code 中运行
/help
```

#### 2.2 使用技能

在 Claude Code 对话中直接调用：
```
请使用 Gemini 分析这段代码...
```

## 性能监控说明

测试脚本 `test_gemini_performance.py` 提供了完整的性能监控功能：

- ✅ CPU 使用率监控（进程级 + 系统级）
- ✅ 内存使用监控（MB + 百分比）
- ✅ 响应时间统计
- ✅ 线程数监控
- ✅ 采样间隔可配置（默认 0.1 秒）

## 资源占用问题排查

如果遇到"资源占用满"的问题，可能的原因：

1. **首次调用初始化开销** - SDK 首次加载模型时会占用较多资源
2. **并发请求过多** - 建议添加请求间隔
3. **响应内容过大** - 限制 max_tokens 参数
4. **系统资源不足** - 检查可用内存和 CPU

## 下一步操作

1. 选择使用方案 1 或方案 2
2. 配置相应的环境
3. 重新运行测试：`python3 test_gemini_performance.py`
