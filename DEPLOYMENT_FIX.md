# 数据库路径修复 - 部署说明

## 修复内容

### 1. 支持环境变量配置数据库路径
- 文件: `config/settings.py`
- 修改: `DB_PATH = os.getenv("DATABASE_PATH", "trading_bot.db")`
- 作用: 允许通过环境变量指定数据库路径

### 2. 添加前端期望的统计字段
- 文件: `apps/api/services/statistics_service.py`
- 新增字段:
  - `today_profit` - 今日收益
  - `pnl_trend` - 盈亏趋势
  - `win_rate_trend` - 胜率趋势
  - `today_trend` - 今日趋势
  - `position_status` - 持仓状态
  - `pnl_history` - 盈亏历史(暂时为空数组)

### 3. 创建生产环境配置
- 文件: `apps/api/.env`
- 配置: `DATABASE_PATH=../../trading_bot.db`

## 生产环境部署步骤

### 步骤1: 上传修改的文件到 VPS

```bash
# 上传修改的文件
scp config/settings.py user@vps:/path/to/trading_bot/config/
scp apps/api/services/statistics_service.py user@vps:/path/to/trading_bot/apps/api/services/
scp apps/api/.env user@vps:/path/to/trading_bot/apps/api/
```

### 步骤2: 配置数据库路径

在 VPS 上编辑 `apps/api/.env`:

```bash
# 方式1: 使用相对路径(推荐)
DATABASE_PATH=../../trading_bot.db

# 方式2: 使用绝对路径
DATABASE_PATH=/path/to/trading_bot/trading_bot.db
```

### 步骤3: 重启后端 API

```bash
# 进入项目目录
cd /path/to/trading_bot

# 重启 API 服务
# 如果使用 systemd
sudo systemctl restart trading-api

# 如果使用 screen/tmux
# 先停止旧进程,再启动新进程
cd apps/api && uvicorn main:app --host 0.0.0.0 --port 8000
```

### 步骤4: 验证修复

访问 API 测试:
```bash
curl https://api.ryder137.de5.net/api/statistics/daily
```

检查返回的 JSON 是否包含新字段:
- `today_profit`
- `pnl_trend`
- `win_rate_trend`
- `position_status`

## 验证清单

- [ ] 后端 API 能正确读取 trading_bot.db
- [ ] 统计接口返回新增字段
- [ ] 前端 Dashboard 显示真实数据
- [ ] 不再显示 $0.00 或 N/A

## 故障排查

### 问题1: API 仍然读取空数据库

**原因**: 工作目录不正确

**解决**:
```bash
# 检查 API 实际读取的数据库路径
# 在 apps/api/main.py 中临时添加日志
from utils.logger_utils import TradeDatabase
db = TradeDatabase()
print(f"Database path: {db.db_file}")
```

### 问题2: 前端仍然显示假数据

**原因**: 前端缓存或 API 未重启

**解决**:
1. 清除浏览器缓存
2. 确认 API 已重启
3. 检查 Network 面板的 API 响应

## 联系信息

如有问题,请查看:
- Codex SESSION_ID: `019bbbed-d1f4-76c0-9657-625c461962f2`
- Gemini SESSION_ID: `9aade9f5-62ba-4be5-8dee-aa4b8feacaf4`
