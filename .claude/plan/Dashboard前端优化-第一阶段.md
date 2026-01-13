# Trading Dashboard 前端优化 - 第一阶段（渐进式打磨）

> 创建时间: 2026-01-13
> 状态: 实施中
> 预计完成: 3-5 天
> 风险等级: 🟢 低

## 1. 优化目标

将 Trading Dashboard 从"原型级"提升到"标准化产品"水平，通过精细化调整提升专业感与可读性。

### 核心优化内容

1. **排版优化**：等宽字体（数字）、间距调整
2. **色彩系统**：涨跌语义化色彩（emerald-500/rose-500）
3. **卡片设计**：细边框 + 微弱阴影 + 渐变背景
4. **图表增强**：Recharts 渐变填充、自定义 Tooltip
5. **微动效**：加载骨架屏、hover 状态、简单过渡

---

## 2. 设计 Tokens

### 色彩 (Colors)
- **Success (Up)**: `emerald-500` (Main), `emerald-500/10` (Surface)
- **Destructive (Down)**: `rose-500` (Main), `rose-500/10` (Surface)
- **Brand**: `indigo-600` (Primary Action)
- **Muted**: `slate-500` (Secondary Text)

### 排版 (Typography)
- **UI Sans**: Inter / System Sans（通用 UI）
- **Data Mono**: Geist Mono / JetBrains Mono（价格、数量、百分比，启用 `tnum` 特性）

### 阴影 (Shadows)
- **Soft Shadow**: `0 4px 20px -2px rgba(0, 0, 0, 0.05)`（卡片浮动感）

---

## 3. 技术架构

### 代码组织
- `apps/dashboard/app/globals.css` - 样式变量与语义色
- `apps/dashboard/tailwind.config.js` - Tailwind 扩展配置
- `apps/dashboard/lib/theme.ts` - **新增** - 统一主题常量
- `apps/dashboard/lib/types/dashboard-ui.ts` - **新增** - TypeScript 类型定义
- `apps/dashboard/components/charts/` - **新增** - 图表组件封装

### TypeScript 类型定义
```typescript
export type TrendDirection = 'up' | 'down' | 'neutral';
export type SemanticTone = 'profit' | 'loss' | 'neutral';

export interface ThemeTone {
  foreground: string;
  softBg: string;
  border: string;
}

export interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: number;
  trendDirection?: TrendDirection;
  className?: string;
}
```

### 性能优化策略
- 图表组件懒加载（`next/dynamic` + `ssr: false`）
- `StatCard` 使用 `React.memo`
- 派生数据使用 `useMemo`
- Tooltip 与渐变使用稳定 `gradientId`

---

## 4. 文件修改清单

| 文件 | 修改内容 | 优先级 |
|------|----------|--------|
| `tailwind.config.js` | 扩展 colors、fonts、shadows、animations | P0 |
| `app/globals.css` | 定义 `--trading-up/down` HSL 变量 | P0 |
| `app/layout.tsx` | 引入 Geist Mono 字体 | P0 |
| `lib/theme.ts` | **新增** - 统一主题常量 | P0 |
| `lib/types/dashboard-ui.ts` | **新增** - TypeScript 类型 | P0 |
| `components/ui/card.tsx` | 细边框 + 微弱阴影 + 毛玻璃 | P1 |
| `components/ui/table.tsx` | 收紧内边距 + 数字列 `font-mono` | P1 |
| `components/ui/skeleton.tsx` | 优化骨架屏颜色 | P1 |
| `components/StatCard.tsx` | 渐变边框 + 等宽数字 + hover | P1 |
| `components/charts/` | **新增** - 渐变 Area + Tooltip | P2 |
| 页面文件 | 应用语义色 + 优化布局间距 | P2 |

---

## 5. 实施步骤

### Day 1：基础设施（P0）
- [x] 更新 `tailwind.config.js` 和 `globals.css`
- [ ] 配置 Geist Mono 字体
- [ ] 创建 `lib/theme.ts` 和 `lib/types/`

### Day 2：组件升级（P1）
- [ ] 优化 `Card`、`Table`、`Skeleton`
- [ ] 升级 `StatCard`（hover 效果 + 等宽字体）
- [ ] 应用 `font-mono` 到所有数字展示

### Day 3：数据可视化（P2）
- [ ] Recharts 渐变填充
- [ ] 自定义 Tooltip 组件
- [ ] 骨架屏包装器

### Day 4：细节打磨
- [ ] 移动端适配验证
- [ ] 暗黑模式对比度修复
- [ ] 统一 focus-ring 样式

---

## 6. 验收标准

1. ✅ **对齐检查**：所有数值垂直对齐（等宽字体）
2. ✅ **视觉呼吸感**：卡片间距 24px，边框 `border/50`
3. ✅ **语义清晰度**：盈利 emerald、亏损 rose，无混用
4. ✅ **加载性能**：骨架屏覆盖 80%+ 异步数据区域
5. ✅ **交互反馈**：hover/click 有明确视觉反馈

---

## 7. 风险规避

- **语义色冲突**：统一使用 tokens，禁止硬编码
- **等宽字体兼容**：优先 `tabular-nums`，降级 `font-mono`
- **性能问题**：限定柔和渐变和阴影，避免低端设备掉帧
- **Tooltip 溢出**：使用 `overflow-visible` 限制容器宽度

---

## 8. 测试验证清单

- [ ] 功能：四页主题色与卡片一致性
- [ ] 功能：涨跌语义色正确、数值对齐无抖动
- [ ] 视觉：卡片细边框/微阴影/渐变在浅色与暗色主题下可读性正常
- [ ] 性能：LCP/CLS 基线对比，图表懒加载前后首屏无回退
- [ ] 交互：Tooltip 悬停稳定，Skeleton 加载与数据切换无闪烁

---

**协作模型**：
- Gemini Session: `31713852-c7ae-4e9a-b27f-2f093e8e4aa0`
- Codex Session: `019bb6f1-2bf9-7170-992b-b2b554173777`

**文档状态**: ✅ 已批准
**实施状态**: 🔄 进行中
