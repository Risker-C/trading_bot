# Vercel 自动部署实施计划

> **方案**: Vercel Git 集成（方案A）
> **目标**: 实现推送到 main 分支后自动触发构建和部署
> **项目**: apps/dashboard/ (Next.js 14.0.4)

---

## 📋 实施步骤总览

### 阶段1：前端配置完善（必需）
1. 创建 PostCSS 配置文件
2. 创建环境变量模板
3. 优化 Next.js 配置
4. 抽取环境变量（WebSocket URL）

### 阶段2：UX 增强（推荐）
5. 添加骨架屏组件
6. 添加错误边界
7. 优化动态导入

### 阶段3：Vercel 部署配置
8. 导入 GitHub 仓库
9. 配置项目设置
10. 配置环境变量

### 阶段4：后端适配（必需）
11. 配置 CORS 白名单
12. 确保 HTTPS/WSS 可用

### 阶段5：验证与测试
13. 本地构建验证
14. 预览部署测试
15. 生产部署验证

---

## 🔧 阶段1：前端配置完善

### 1.1 创建 PostCSS 配置

**文件**: `apps/dashboard/postcss.config.js`

```javascript
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

**原因**: Tailwind CSS 生产构建必需，否则样式无法编译。

---

### 1.2 创建环境变量模板

**文件**: `apps/dashboard/.env.local.example`

```bash
# 后端 API 地址
NEXT_PUBLIC_API_URL=http://localhost:8000

# WebSocket 地址
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# 功能开关（可选）
NEXT_PUBLIC_MOCK_ENABLED=false
```

**用途**:
- 开发者参考
- Vercel 部署时的配置清单

---

### 1.3 优化 Next.js 配置

**文件**: `apps/dashboard/next.config.js`

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // 生产环境优化：移除 console.log
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production',
  },

  // 安全 Headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
        ],
      },
    ];
  },
}

module.exports = nextConfig
```

**改动**:
- 添加 `compiler.removeConsole`（生产环境移除日志）
- 添加安全 Headers（防止 XSS、点击劫持）

---

### 1.4 抽取 WebSocket 环境变量

**文件**: `apps/dashboard/hooks/useWebSocket.ts`

**当前问题**: 硬编码 `ws://localhost:8000`

**修改方案**:
```typescript
const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
```

**同时检查**: `apps/dashboard/lib/api-client.ts` 是否已使用 `NEXT_PUBLIC_API_URL`

---

## 🎨 阶段2：UX 增强（推荐）

### 2.1 添加骨架屏组件

**文件**: `apps/dashboard/app/loading.tsx`

```tsx
import { Skeleton } from '@/components/ui/skeleton';

export default function Loading() {
  return (
    <div className="flex min-h-screen flex-col p-8">
      <div className="mb-8">
        <Skeleton className="h-9 w-64 mb-2" />
        <Skeleton className="h-5 w-48" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>

      <Skeleton className="h-96" />
    </div>
  );
}
```

**用途**: 全局加载状态，提升首屏体验。

---

### 2.2 添加错误边界

**文件**: `apps/dashboard/app/error.tsx`

```tsx
'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { AlertCircle } from 'lucide-react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <div className="text-center space-y-4">
        <AlertCircle className="h-12 w-12 text-destructive mx-auto" />
        <h2 className="text-2xl font-bold">出错了</h2>
        <p className="text-muted-foreground">
          {error.message || '加载数据时发生错误'}
        </p>
        <Button onClick={reset}>重试</Button>
      </div>
    </div>
  );
}
```

**用途**: 捕获运行时错误，提供重试机制。

---

### 2.3 优化动态导入（可选）

**文件**: `apps/dashboard/components/ChartWrapper.tsx`

```tsx
import dynamic from 'next/dynamic';

const AreaChart = dynamic(
  () => import('recharts').then((mod) => mod.AreaChart),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] animate-pulse bg-muted rounded-lg" />
    )
  }
);

export { AreaChart };
```

**用途**: 减少初始 Bundle 大小，Recharts 仅在客户端加载。

---

## ☁️ 阶段3：Vercel 部署配置

### 3.1 导入 GitHub 仓库

1. 访问 [Vercel Dashboard](https://vercel.com/dashboard)
2. 点击 **New Project**
3. 选择 **Import Git Repository**
4. 授权并选择 `trading_bot` 仓库

---

### 3.2 配置项目设置

| 配置项 | 值 |
|--------|-----|
| **Framework Preset** | Next.js |
| **Root Directory** | `apps/dashboard/` |
| **Build Command** | `npm run build` |
| **Install Command** | `npm ci` |
| **Output Directory** | `.next` (默认) |
| **Node.js Version** | 18.x 或 20.x |

**重要**: 必须设置 `Root Directory` 为 `apps/dashboard/`，否则 Vercel 无法识别项目。

---

### 3.3 配置环境变量

在 Vercel Project Settings → Environment Variables 中添加：

| 变量名 | 生产环境值 | 预览环境值 |
|--------|-----------|-----------|
| `NEXT_PUBLIC_API_URL` | `https://api.your-domain.com` | `https://api-staging.your-domain.com` |
| `NEXT_PUBLIC_WS_URL` | `wss://api.your-domain.com/ws/stream` | `wss://api-staging.your-domain.com/ws/stream` |

**注意**:
- 生产环境必须使用 `https://` 和 `wss://`
- 预览环境可以使用不同的后端地址

---

### 3.4 部署触发策略

| 配置项 | 设置 |
|--------|------|
| **Production Branch** | `main` |
| **Preview Deployments** | 启用（为 PR 生成预览链接） |
| **Auto Deploy** | 启用 |

---

## 🔌 阶段4：后端适配

### 4.1 配置 CORS 白名单

**文件**: 后端 `.env` 或配置文件

```bash
CORS_ORIGINS=https://your-project.vercel.app,https://your-project-git-main.vercel.app
```

**注意**:
- Vercel 会生成多个域名（生产、预览、分支）
- 必须将所有需要访问的域名加入白名单
- 不能使用 `*`（因为后端启用了 `allow_credentials=True`）

**Vercel 域名格式**:
- 生产: `your-project.vercel.app`
- 主分支: `your-project-git-main.vercel.app`
- PR预览: `your-project-git-feature-branch.vercel.app`

---

### 4.2 确保 HTTPS/WSS 可用

**要求**:
1. 后端 API 必须支持 HTTPS
2. WebSocket 必须支持 WSS（TLS 加密）
3. 如果后端在自建服务器，需要配置反向代理（Nginx/Traefik）

**Nginx 配置示例**:
```nginx
location /ws/ {
    proxy_pass http://localhost:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

---

## ✅ 阶段5：验证与测试

### 5.1 本地构建验证

```bash
cd apps/dashboard
npm ci
npm run build
```

**预期结果**:
- ✅ 无 PostCSS 错误
- ✅ 无 Tailwind 编译错误
- ✅ 构建成功生成 `.next` 目录

---

### 5.2 预览部署测试

1. 创建新分支并推送
2. 在 Vercel Dashboard 查看预览部署状态
3. 访问预览 URL
4. 检查：
   - ✅ 页面正常渲染
   - ✅ API 请求成功（Network 面板无 CORS 错误）
   - ✅ WebSocket 连接成功（`wss://` 协议）

---

### 5.3 生产部署验证

1. 合并到 `main` 分支
2. 观察 Vercel 自动部署
3. 访问生产 URL
4. 完整测试：
   - ✅ 所有页面可访问
   - ✅ 数据正常加载
   - ✅ WebSocket 实时更新
   - ✅ 错误边界正常工作
   - ✅ 移动端响应式布局

---

## 🔒 安全检查清单

- [ ] 前端未暴露 `JWT_SECRET` 等后端敏感变量
- [ ] CORS 仅允许可信域名（不使用 `*`）
- [ ] 生产环境使用 HTTPS/WSS
- [ ] 环境变量在 Vercel Dashboard 中正确配置
- [ ] 预览部署权限控制（如需要）

---

## 📊 文件清单总结

### 必需创建/修改的文件

| 文件 | 状态 | 优先级 |
|------|------|--------|
| `apps/dashboard/postcss.config.js` | 新增 | P0 |
| `apps/dashboard/.env.local.example` | 新增 | P0 |
| `apps/dashboard/next.config.js` | 修改 | P0 |
| `apps/dashboard/hooks/useWebSocket.ts` | 修改 | P0 |
| `apps/dashboard/app/loading.tsx` | 新增 | P1 |
| `apps/dashboard/app/error.tsx` | 新增 | P1 |
| `apps/dashboard/components/ChartWrapper.tsx` | 新增 | P2 |

### 后端配置

| 配置项 | 优先级 |
|--------|--------|
| CORS 白名单（添加 Vercel 域名） | P0 |
| HTTPS/WSS 支持 | P0 |

---

## 🎯 预期成果

完成后，系统将实现：

1. ✅ **自动部署**: 推送到 `main` 分支自动触发生产部署
2. ✅ **预览部署**: PR 自动生成预览链接
3. ✅ **环境隔离**: 生产/预览环境使用不同的后端地址
4. ✅ **性能优化**: 移除 console.log、动态导入、安全 Headers
5. ✅ **用户体验**: 骨架屏、错误边界、实时反馈

---

## 📚 参考资源

- [Vercel Next.js 部署文档](https://vercel.com/docs/frameworks/nextjs)
- [Next.js 环境变量](https://nextjs.org/docs/app/building-your-application/configuring/environment-variables)
- [Vercel 环境变量配置](https://vercel.com/docs/projects/environment-variables)

---

**创建时间**: 2026-01-14
**Codex SESSION_ID**: 019bbb4b-65a5-7ad3-9f0f-3df99410e6ed
**Gemini SESSION_ID**: 794dbefc-76bf-4b2b-8d26-13431da0fb69
