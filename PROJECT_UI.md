# 🎨 PodCast Translator — AI UI/UX 设计需求规范

> **设计历史**：本文记录 PodFlow 早期 UI/UX 设计输入，旧品牌名称仅用于呈现历史背景。当前界面以仓库中的前端代码和产品截图为准。
>
> **版本**：v2.0
> **日期**：2026-04-13
> **关联文档**：[PRD](./PROJECT_PRD.md)
> **输出目标**：为 v0.dev / Midjourney / Bolt.new 等 AI 设计工具提供高精度结构化 Prompt

---

## 0. 全局设计系统 (Global Design System)

### 0.1 品牌调性关键词

| 维度 | 关键词 |
|------|--------|
| 情感 | 专业、可信赖、高效、轻松 |
| 视觉 | 干净、克制、呼吸感、容器型 UI |
| 类比 | "Apple Podcasts 的简洁 × Linear 的效率感 × Notion 的留白" |

### 0.2 色彩系统 (Color Palette)

| Token | 色值 | 用途 |
|-------|------|------|
| `--bg-primary` | `#FFFFFF` | 主背景 |
| `--bg-secondary` | `#F8F9FA` | 卡片/区块背景 |
| `--bg-tertiary` | `#F1F3F5` | 输入框/上传区域背景 |
| `--text-primary` | `#1A1A1A` | 主文本 |
| `--text-secondary` | `#6B7280` | 辅助文本/描述 |
| `--text-tertiary` | `#9CA3AF` | 占位符/禁用态 |
| `--accent` | `#2563EB` | 主强调色（CTA 按钮、链接、进度条） |
| `--accent-hover` | `#1D4ED8` | 强调色悬停态 |
| `--accent-light` | `#EFF6FF` | 强调色浅底（Tag/Badge 背景） |
| `--success` | `#16A34A` | 成功状态（✅ 完成） |
| `--warning` | `#F59E0B` | 进行中状态（🔄 翻译中） |
| `--error` | `#DC2626` | 错误/失败状态 |
| `--border` | `#E5E7EB` | 分割线/边框 |

> **色彩原则**：整体为 Light mode 浅色系，大面积留白。仅 `--accent` 蓝色作为唯一强调色，全局出现不超过 3 处。避免高饱和度色彩。

### 0.3 字体系统 (Typography)

| 层级 | 字号 | 字重 | 行高 | 用途 |
|------|------|------|------|------|
| H1 | 36px | 700 (Bold) | 1.2 | 首页主标题 |
| H2 | 24px | 600 (SemiBold) | 1.3 | 页面标题/区块标题 |
| H3 | 18px | 600 | 1.4 | 卡片标题 |
| Body | 15px | 400 (Regular) | 1.6 | 正文/描述 |
| Caption | 13px | 400 | 1.5 | 辅助文字/时间戳 |
| Overline | 12px | 500 (Medium) | 1.4 | 标签/状态文字（大写） |

> **字体栈**：`"Inter", "SF Pro Display", -apple-system, "PingFang SC", "Noto Sans SC", sans-serif`

### 0.4 间距与圆角 (Spacing & Radius)

| Token | 值 | 用途 |
|-------|----|------|
| `--space-xs` | 4px | 图标与文字间距 |
| `--space-sm` | 8px | 紧凑元素间距 |
| `--space-md` | 16px | 卡片内边距 |
| `--space-lg` | 24px | 区块间距 |
| `--space-xl` | 40px | 大区块间距 |
| `--space-2xl` | 64px | 页面级留白 |
| `--radius-sm` | 8px | 按钮/输入框 |
| `--radius-md` | 12px | 卡片 |
| `--radius-lg` | 16px | 上传区域/大容器 |

### 0.5 阴影与材质 (Shadows & Materials)

| Token | 值 | 用途 |
|-------|----|------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | 卡片默认 |
| `--shadow-md` | `0 4px 12px rgba(0,0,0,0.08)` | 卡片悬停/弹窗 |
| `--shadow-lg` | `0 8px 24px rgba(0,0,0,0.12)` | Modal/Dropdown |

> **材质原则**：Flat design 为主。仅上传区域可使用极轻度 `backdrop-filter: blur(8px)` 磨砂效果。禁止渐变背景、禁止发光效果。

### 0.6 图标系统

- 图标库：**Lucide Icons**（线性风格，2px 描边）
- 图标尺寸：20px（正文内联）/ 24px（按钮/导航）/ 32px（空状态）
- 图标颜色：跟随文本颜色，CTA 图标使用 `--accent`

### 0.7 负向约束 (Negative Prompts — 全局强制)

```
❌ No cyberpunk, no neon lights, no glitch art
❌ No heavy glowing effects, no dark sci-fi theme
❌ No gradient backgrounds, no glassmorphism heavy blur
❌ No 3D illustrations, no isometric icons
❌ No high-saturation colors, no rainbow palette
❌ No decorative animations, no particle effects
```

### 0.8 站点地图与路由架构 (Site Map & Routing)

```
🌐 PodFlow 站点地图
│
├─ 🔓 公开页面（无需登录）
│  ├── /login ............... 登录/注册页 (§4)
│  ├── /terms ............... 服务条款页
│  ├── /privacy ............. 隐私政策页
│  └── /404 ................. 404 未找到 (§7)
│
├─ 🔒 需登录页面
│  ├── / .................... 首页/上传页 (§1)
│  ├── /tasks ............... 任务历史列表 (§6)
│  ├── /tasks/:id ........... 任务详情/进度 (§2)
│  ├── /tasks/:id/transcript  中英文对照 (§3, Phase 2)
│  ├── /profile ............. 个人主页/设置 (§5)
│  └── /pricing ............. 升级/定价 (§8, Phase 4)
│
└─ 🧩 全局组件 (§9)
   ├── TopNav + Avatar Dropdown
   ├── AuthGuard (路由守卫)
   ├── ToastProvider (全局通知)
   └── SkeletonLoader (骨架屏)
```

> **路由分组**：Next.js App Router Route Groups — `(public)` 组无导航栏独立布局，`(protected)` 组含 TopNav + AuthGuard 路由守卫。

---

## 1. 页面一：首页 / 上传页 (Home / Upload Page)

### 1.1 核心意图与组件清单 (Core Intent & Components)

- **UI 类型**：SaaS 产品首页 / 核心功能入口页（登录后状态）
- **核心功能区**：
  1. **顶部导航栏 (Top Nav)**：Logo + 用户头像菜单
  2. **Hero 区 / 价值主张 (Hero Section)**：一句话传达产品价值
  3. **上传操作区 (Upload Zone)**：拖拽上传 + URL 输入，双入口并列
  4. **最近翻译列表 (Recent Tasks)**：历史任务卡片，含状态标识
  5. **额度提示条 (Quota Bar)**：剩余免费额度，低额度时引导升级

### 1.2 布局与信息架构 (Layout & Structure)

```
骨架逻辑：单列居中布局（Single-column centered）
最大内容宽度：720px
页面纵向结构（从上到下）：

┌─ Full-width Top Nav ─────────────────────────────────┐
│  [Logo: 🎙️ PodFlow]                    [Avatar ▾]    │
│  height: 56px; border-bottom: 1px solid --border      │
└───────────────────────────────────────────────────────┘

┌─ Content Container (max-w: 720px, mx: auto) ─────────┐
│                                                       │
│  ┌─ Hero Section ──────────────────────────────────┐  │
│  │  H1: "将英文播客翻译为中文"                       │  │
│  │  Subtitle: "保留原主播声音，像听中文播客一样自然"   │  │
│  │  margin-top: 64px; margin-bottom: 40px;          │  │
│  │  text-align: center;                             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Upload Zone ───────────────────────────────────┐  │
│  │  Dashed-border container (--radius-lg)           │  │
│  │  Icon: Upload Cloud (32px, --text-tertiary)      │  │
│  │  "拖拽音频文件到此处，或 点击选择文件"              │  │
│  │  Caption: "支持 MP3/WAV/M4A，最大 500MB"          │  │
│  │  height: 200px; bg: --bg-tertiary;               │  │
│  │  border: 2px dashed --border;                    │  │
│  │  hover: border-color --accent;                   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Divider ───────────────────────────────────────┐  │
│  │  ────────── 或者 ──────────                      │  │
│  │  margin-y: 24px; --text-tertiary                 │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ URL Input Row ─────────────────────────────────┐  │
│  │  [🔗 Input: "粘贴播客音频 URL..."  ] [开始翻译]   │  │
│  │  Input: flex-1; Button: --accent bg, white text  │  │
│  │  height: 48px; gap: 12px;                        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Quota Bar ─────────────────────────────────────┐  │
│  │  "本月剩余免费额度：3 / 5 集"                     │  │
│  │  margin-top: 16px; text-align: center;           │  │
│  │  font: Caption; color: --text-secondary;         │  │
│  │  额度 ≤ 1 时：color: --warning + [升级] link     │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Recent Tasks Section ──────────────────────────┐  │
│  │  H3: "最近翻译"  margin-top: 48px;               │  │
│  │                                                  │  │
│  │  ┌─ Task Card ────────────────────────────────┐  │  │
│  │  │  [🎧] Title + Subtitle     Status  [Action]│  │  │
│  │  │  padding: 16px; radius: --radius-md;       │  │  │
│  │  │  bg: --bg-primary; border: 1px --border;   │  │  │
│  │  │  hover: --shadow-sm;                       │  │  │
│  │  │  状态类型：                                 │  │  │
│  │  │    ✅ 已完成 (--success) → [▶ 播放] btn    │  │  │
│  │  │    🔄 翻译中 68% (--warning) → 进度文字     │  │  │
│  │  │    ❌ 失败 (--error) → [重试] btn           │  │  │
│  │  │    ⏳ 排队中 (--text-tertiary) → 等待文字   │  │  │
│  │  └────────────────────────────────────────────┘  │  │
│  │  (repeat × N, gap: 8px, max visible: 5)         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  padding-bottom: 64px;                                │
└───────────────────────────────────────────────────────┘
```

### 1.3 视觉风格与色彩规范 (Visual Style)

- **整体风格 (Style)**：Minimalist, Clean tech, Apple-like simplicity, content-first layout
- **色彩模式 (Color Palette)**：Light mode, white dominant, monochrome with single blue accent (`#2563EB`)
- **材质与光影 (Material & Lighting)**：Flat design, subtle 1px borders, soft micro-shadows on hover, natural daylight feel
- **上传区域特殊处理**：Dashed border container, light gray background, hover 时 border 变为 accent blue + 轻微 scale(1.005) 过渡
- **负向提示词 (Negative Prompts)**：No cyberpunk, no neon, no glowing text, no heavy sci-fi, no gradient backgrounds, no 3D elements, no dark mode

### 1.4 交互状态矩阵

| 组件 | Default | Hover | Active/Focus | Disabled | Loading |
|------|---------|-------|--------------|----------|---------|
| 上传区域 | Dashed border `--border` | Border → `--accent`, bg lighten | 文件拖入：border solid `--accent` + bg `--accent-light` | — | 上传进度条替换内部文案 |
| URL 输入框 | Border `--border` | Border `--accent` | Ring: 2px `--accent-light` | Opacity 0.5 | — |
| "开始翻译" 按钮 | bg `--accent`, white text | bg `--accent-hover` | Scale 0.98 | bg `--bg-tertiary`, text `--text-tertiary` | Spinner + "解析中..." |
| 任务卡片 | Border `--border` | `--shadow-sm` + translate-y(-1px) | — | — | — |

### 1.5 专属 AI 生成提示词 (Ready-to-Use Prompt)

#### For v0.dev / Bolt.new (React + Tailwind)

```
Build a clean, minimal SaaS homepage for a podcast translation app called "PodFlow".

Tech stack: Next.js + Tailwind CSS + Lucide icons.

Layout: Single-column centered (max-w-2xl), white background (#FFFFFF).

Top nav: 56px height, logo "🎙️ PodFlow" on left (text-lg font-semibold), user avatar circle on right, separated by bottom border (gray-200).

Hero section: centered text, margin-top 16. H1 "将英文播客翻译为中文" (text-3xl font-bold text-gray-900). Below it a subtitle "保留原主播声音，像听中文播客一样自然" (text-base text-gray-500 mt-2).

Upload zone: Below hero (mt-10). A 200px tall dashed border container (border-2 border-dashed border-gray-300 rounded-2xl bg-gray-50). Centered content: Upload cloud icon (32px, gray-400), text "拖拽音频文件到此处，或 点击选择文件" (text-sm text-gray-500), caption "支持 MP3/WAV/M4A，最大 500MB" (text-xs text-gray-400 mt-1). On hover: border-blue-500 transition.

Divider: "── 或者 ──" centered (text-xs text-gray-400 my-6) with horizontal lines on both sides.

URL input row: flex row gap-3. Input field (flex-1, h-12, rounded-lg, border gray-300, placeholder "粘贴播客音频 URL..."). Blue button "开始翻译" (bg-blue-600 text-white px-6 h-12 rounded-lg hover:bg-blue-700).

Quota text: centered below (mt-4, text-xs text-gray-400) "本月剩余免费额度：3 / 5 集".

Recent tasks section: mt-12. H3 "最近翻译" (text-lg font-semibold mb-4). List of 3 task cards, each: flex row, items-center, p-4, rounded-xl, border border-gray-200, hover:shadow-sm transition. Left: headphones icon + title text. Right: status badge. Statuses: "✅ 已完成" green with play button, "🔄 翻译中 68%" amber with percentage, "✅ 已完成" green with play button.

Style: Ultra-clean, lots of whitespace, no gradients, no dark theme, no decorative elements. Apple-like minimalism. Inter font family.
```

#### For Midjourney / UI Screenshot Generation

```
UI design of a minimal SaaS podcast translation web app homepage, light mode, white background, single column centered layout, clean top navigation bar with small logo and avatar, large centered headline in Chinese, dashed-border upload dropzone area with upload icon, URL input field with blue CTA button, list of recent task cards with status badges, Swiss design influence, Apple-like minimalism, generous whitespace, Inter font, soft gray borders, single blue accent color, high resolution, 1440x900 desktop screenshot, Dribbble quality, UX/UI design --ar 16:10 --no cyberpunk, neon, glowing effects, dark theme, gradients, 3D elements
```

---

## 2. 页面二：任务详情 / 进度页 (Task Detail / Progress Page)

### 2.1 核心意图与组件清单 (Core Intent & Components)

- **UI 类型**：任务状态详情页 / 异步进度追踪页
- **核心功能区**：
  1. **顶部导航 (Top Nav)**：返回箭头 + "任务详情" 标题
  2. **任务信息头 (Task Header)**：播客标题 + 元信息（时长、上传时间）
  3. **翻译进度面板 (Progress Panel)**：5 步骤条 + 总进度条 + 预计时间
  4. **结果操作区 (Result Actions)**：播放器 + 下载按钮 + 查看文本按钮（完成后显示）
  5. **失败态区域 (Error State)**：错误信息 + 重试按钮（失败时显示）

### 2.2 布局与信息架构 (Layout & Structure)

```
骨架逻辑：单列居中布局（Single-column centered）
最大内容宽度：640px
页面有两种状态：[进行中态] / [完成态]，通过条件渲染切换

┌─ Full-width Top Nav ─────────────────────────────────┐
│  [← 返回]                    任务详情                  │
│  height: 56px; border-bottom: 1px solid --border      │
└───────────────────────────────────────────────────────┘

┌─ Content Container (max-w: 640px, mx: auto) ─────────┐
│                                                       │
│  ┌─ Task Header ───────────────────────────────────┐  │
│  │  [🎧 48px icon]                                  │  │
│  │  H2: "Lex Fridman Podcast #421"                  │  │
│  │  Body: "Sam Altman: OpenAI, GPT-5 and..."        │  │
│  │  Caption: "时长 2:15:30 · 上传于 10 分钟前"       │  │
│  │  margin-top: 40px; margin-bottom: 32px;          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Progress Panel (进行中态) ─────────────────────┐  │
│  │  bg: --bg-secondary; radius: --radius-lg;        │  │
│  │  padding: 24px;                                  │  │
│  │                                                  │  │
│  │  Step List (vertical, gap: 16px):                │  │
│  │  ┌──────────────────────────────────────────┐    │  │
│  │  │ ✅ 音源分离              完成             │    │  │
│  │  │ ✅ 语音识别              完成             │    │  │
│  │  │ 🔄 智能翻译              进行中 72%       │    │  │
│  │  │ ○  声音克隆合成           等待中           │    │  │
│  │  │ ○  混音输出              等待中           │    │  │
│  │  └──────────────────────────────────────────┘    │  │
│  │                                                  │  │
│  │  每行结构：                                       │  │
│  │    [状态图标 20px] [步骤名 flex-1] [状态文字]      │  │
│  │    ✅ = --success 圆形勾选图标                    │  │
│  │    🔄 = --warning 旋转 spinner                   │  │
│  │    ○  = --border 空心圆                          │  │
│  │    ❌ = --error 圆形叉号                          │  │
│  │                                                  │  │
│  │  ┌─ Total Progress Bar ──────────────────────┐   │  │
│  │  │  height: 6px; radius: 3px;                │   │  │
│  │  │  bg-track: --bg-tertiary;                 │   │  │
│  │  │  bg-fill: --accent; width: 62%;           │   │  │
│  │  │  transition: width 0.5s ease;             │   │  │
│  │  └───────────────────────────────────────────┘   │  │
│  │                                                  │  │
│  │  flex row justify-between:                       │  │
│  │    "总进度 62%" (Caption, --text-secondary)       │  │
│  │    "预计剩余 约 8 分钟" (Caption, --text-tertiary)│  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Result Section (完成态，替换 Progress Panel) ──┐  │
│  │                                                  │  │
│  │  ┌─ Audio Player ────────────────────────────┐   │  │
│  │  │  [▶/⏸ 40px] ━━━━━━━━━○━━━━  01:23:45     │   │  │
│  │  │  height: 64px; bg: --bg-secondary;        │   │  │
│  │  │  radius: --radius-md; padding: 16px;      │   │  │
│  │  │  进度条: --accent; 圆形 handle;            │   │  │
│  │  │  倍速选择: [1x ▾] 小型 dropdown            │   │  │
│  │  └───────────────────────────────────────────┘   │  │
│  │                                                  │  │
│  │  flex row gap-12, justify-center, mt-24:         │  │
│  │    [⬇️ 下载 MP3]  — Primary button (--accent)    │  │
│  │    [📝 查看中英文对照] — Secondary button (outline)│  │
│  │                                                  │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Error Section (失败态，替换 Progress Panel) ───┐  │
│  │  bg: #FEF2F2; border: 1px --error/20%;           │  │
│  │  radius: --radius-lg; padding: 24px;             │  │
│  │  text-align: center;                             │  │
│  │                                                  │  │
│  │  Icon: AlertCircle (32px, --error)               │  │
│  │  H3: "翻译失败" (--error)                         │  │
│  │  Body: "语音识别阶段出现错误，请重试"              │  │
│  │  [🔄 重新翻译] — Primary button (--accent)        │  │
│  │  Caption: "重试不会消耗额度"                      │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
└───────────────────────────────────────────────────────┘
```

### 2.3 视觉风格与色彩规范 (Visual Style)

- **整体风格 (Style)**：Minimalist status dashboard, Linear-app-like progress tracking, calm and reassuring
- **色彩模式 (Color Palette)**：Light mode, white dominant. 进度面板使用 `--bg-secondary` 浅灰底色形成层次。三色状态系统：green(完成) / amber(进行中) / gray(等待)
- **材质与光影 (Material & Lighting)**：Flat cards with subtle background color differentiation, no shadows on progress panel, soft rounded corners
- **动效规范**：进度条使用 `transition: width 0.5s ease`；Spinner 使用 `animation: spin 1s linear infinite`；步骤完成时 checkmark 有轻微 scale bounce (0.3s)
- **负向提示词 (Negative Prompts)**：No cyberpunk, no neon, no glowing progress bars, no heavy animations, no dark theme, no sci-fi dashboard

### 2.4 交互状态矩阵

| 组件 | 进行中态 | 完成态 | 失败态 |
|------|---------|--------|--------|
| Progress Panel | 可见，实时更新 | 隐藏（或折叠为摘要行） | 隐藏 |
| Audio Player | 隐藏 | 可见，可播放 | 隐藏 |
| 下载/查看按钮 | 隐藏 | 可见可点击 | 隐藏 |
| Error Section | 隐藏 | 隐藏 | 可见 + 重试按钮 |
| 页面标题右侧 | 无 | "✅ 翻译完成" badge | "❌ 翻译失败" badge |

### 2.5 专属 AI 生成提示词 (Ready-to-Use Prompt)

#### For v0.dev / Bolt.new (React + Tailwind)

```
Build a task detail / progress page for a podcast translation app called "PodFlow".

Tech stack: Next.js + Tailwind CSS + Lucide icons.

Layout: Single-column centered (max-w-xl), white background.

Top nav: 56px, left side has back arrow icon + "返回" text link (text-gray-600), center has "任务详情" text (font-medium).

Task header: mt-10. Headphones icon (48px, gray-400) centered. Below: H2 title "Lex Fridman Podcast #421" (text-xl font-semibold). Subtitle "Sam Altman: OpenAI, GPT-5 and..." (text-sm text-gray-500 mt-1). Meta line: "时长 2:15:30 · 上传于 10 分钟前" (text-xs text-gray-400 mt-2). All centered.

Progress panel: mt-8, bg-gray-50, rounded-2xl, p-6. Contains a vertical step list with 5 items, gap-4. Each step is a flex row: left icon (20px) + step name (flex-1, text-sm) + status text (text-sm). Step states: completed = green circle-check icon + "完成" in green; active = amber spinning loader icon + "进行中 72%" in amber; pending = gray empty circle + "等待中" in gray-400.

Below steps: mt-6, a thin progress bar (h-1.5, rounded-full, bg-gray-200). Fill portion is bg-blue-600 at 62% width with smooth transition. Below bar: flex justify-between, "总进度 62%" left (text-xs text-gray-500), "预计剩余 约 8 分钟" right (text-xs text-gray-400).

Show a second variant (completed state): Replace progress panel with result section. Audio player: bg-gray-50 rounded-xl p-4, flex row items-center. Play button (circle, 40px, bg-blue-600, white play icon). Seek bar (flex-1, mx-4, h-1 bg-gray-300 with blue fill, round handle). Time "01:23:45" (text-xs text-gray-500). Speed selector "1x" small dropdown.

Below player: mt-6, flex row gap-3 justify-center. Primary button "⬇️ 下载 MP3" (bg-blue-600 text-white px-6 py-3 rounded-lg). Secondary button "📝 查看中英文对照" (border border-gray-300 text-gray-700 px-6 py-3 rounded-lg).

Style: Ultra-clean, calm, reassuring. No gradients, no dark mode, no decorative elements. Linear-app inspired minimalism.
```

#### For Midjourney / UI Screenshot Generation

```
UI design of a task progress detail page for a podcast translation web app, light mode, white background, single column centered layout, clean top bar with back button, podcast episode title with metadata, vertical step progress tracker showing 5 stages with green checkmarks and amber spinner, thin blue progress bar at 62 percent, estimated time remaining text, below is an audio player with play button and seek bar, download and view transcript buttons, Swiss design influence, Apple-like minimalism, generous whitespace, Inter font, soft rounded cards, single blue accent color, high resolution, 1440x900 desktop screenshot, Dribbble quality, UX/UI design --ar 16:10 --no cyberpunk, neon, glowing effects, dark theme, gradients, 3D elements
```

---

## 3. 页面三：中英文对照页 (Bilingual Transcript Page) — Phase 2

### 3.1 核心意图与组件清单 (Core Intent & Components)

- **UI 类型**：内容校对编辑页 / 双语对照阅读页
- **核心功能区**：
  1. **顶部操作栏 (Top Action Bar)**：返回 + 标题 + "重新生成音频" CTA
  2. **同步播放器 (Synced Player)**：播放时高亮当前段落
  3. **对照段落列表 (Transcript Segments)**：按说话人分段，每段含英文原文 + 中文译文 + 编辑按钮
  4. **编辑态 (Inline Edit)**：点击编辑后 inline 展开 textarea

### 3.2 布局与信息架构 (Layout & Structure)

```
骨架逻辑：单列居中布局（Single-column centered）
最大内容宽度：720px
特点：长列表滚动页面，播放器 sticky 吸顶

┌─ Full-width Top Nav ─────────────────────────────────┐
│  [← 返回]    中英文对照    [🔄 重新生成音频] (accent) │
│  height: 56px; border-bottom: 1px solid --border      │
│  "重新生成音频" 仅在有编辑修改时高亮可点击             │
└───────────────────────────────────────────────────────┘

┌─ Sticky Player Bar ──────────────────────────────────┐
│  [▶/⏸] ━━━━━━━━━○━━━━━━━  01:23:45 / 2:15:30  [1x] │
│  height: 52px; bg: --bg-primary; border-bottom;      │
│  position: sticky; top: 56px; z-index: 10;           │
│  backdrop-filter: blur(8px); bg: rgba(255,255,255,0.9)│
└───────────────────────────────────────────────────────┘

┌─ Content Container (max-w: 720px, mx: auto) ─────────┐
│  padding-top: 24px;                                   │
│                                                       │
│  ┌─ Segment Card (Speaker A) ──────────────────────┐  │
│  │  ┌─ Speaker Label ─────────────────────────────┐ │  │
│  │  │  [🔵 8px dot] "Speaker A (Lex)"             │ │  │
│  │  │  Overline style, --text-secondary            │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  │                                                  │  │
│  │  EN: "So Sam, let's start with the big picture. │  │
│  │       Where is OpenAI heading right now?"        │  │
│  │  font: Body; color: --text-secondary;            │  │
│  │  line-height: 1.7; font-style: italic;           │  │
│  │                                                  │  │
│  │  CN: "那 Sam，我们从大局开始聊吧。OpenAI 现在     │  │
│  │       走到哪一步了？"                             │  │
│  │  font: Body; color: --text-primary;              │  │
│  │  line-height: 1.7; font-weight: 400;             │  │
│  │                                                  │  │
│  │  [✏️ 编辑] — 右下角，text button, --text-tertiary │  │
│  │  hover: --accent                                 │  │
│  │                                                  │  │
│  │  ── 编辑态 (展开) ──                              │  │
│  │  textarea: auto-height, border --accent,          │  │
│  │  bg: --accent-light, radius: --radius-sm;         │  │
│  │  [取消] [保存] 按钮组，右对齐                      │  │
│  │                                                  │  │
│  │  bg: --bg-primary; border: 1px --border;          │  │
│  │  radius: --radius-md; padding: 20px;              │  │
│  │  当前播放段高亮: border-left: 3px solid --accent;  │  │
│  │  bg: --accent-light (极淡蓝底);                   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  (gap: 12px between segments)                         │
│                                                       │
│  ┌─ Segment Card (Speaker B) ──────────────────────┐  │
│  │  [🟢 8px dot] "Speaker B (Sam)"                  │  │
│  │  EN: "Yeah, I think we're at this really..."     │  │
│  │  CN: "嗯，我觉得我们正处在一个非常有趣的..."      │  │
│  │  [✏️ 编辑]                                       │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ... repeat for all segments ...                      │
│                                                       │
│  padding-bottom: 120px; (为 sticky player 留空间)     │
└───────────────────────────────────────────────────────┘
```

### 3.3 视觉风格与色彩规范 (Visual Style)

- **整体风格 (Style)**：Reader-mode, Notion-like content editing, calm reading experience, editorial design
- **色彩模式 (Color Palette)**：Light mode. 英文原文使用 `--text-secondary` + italic 弱化；中文译文使用 `--text-primary` 强化。当前播放段使用 `--accent-light` 极淡蓝底 + 左侧 3px accent 色条
- **说话人区分**：Speaker A = 蓝色圆点 `#2563EB`；Speaker B = 绿色圆点 `#16A34A`；更多说话人依次分配低饱和度色点
- **材质与光影 (Material & Lighting)**：Flat segment cards, 1px border, no shadows. Sticky player 使用极轻磨砂 `backdrop-filter: blur(8px)` + 半透明白底
- **负向提示词 (Negative Prompts)**：No cyberpunk, no neon, no syntax highlighting colors, no heavy borders, no dark mode, no complex editor UI

### 3.4 交互状态矩阵

| 组件 | Default | 播放中 | 编辑态 | 已编辑未保存 |
|------|---------|--------|--------|-------------|
| Segment Card | 白底 + 灰边框 | 淡蓝底 + 左侧蓝色条 | textarea 展开 | 右上角显示 "已修改" 小标签 |
| 编辑按钮 | `--text-tertiary` | 同 default | 隐藏（被 textarea 替代） | — |
| "重新生成" 按钮 | Disabled (outline gray) | 同 | 同 | Enabled (bg `--accent`, 白字) |
| Sticky Player | 正常 | 播放动画 + 时间滚动 | 同 | 同 |

### 3.5 专属 AI 生成提示词 (Ready-to-Use Prompt)

#### For v0.dev / Bolt.new (React + Tailwind)

```
Build a bilingual transcript review page for a podcast translation app called "PodFlow".

Tech stack: Next.js + Tailwind CSS + Lucide icons.

Layout: Single-column centered (max-w-2xl), white background.

Top nav: 56px, left "← 返回" link, center "中英文对照" text, right "🔄 重新生成音频" button (initially outline gray disabled, becomes bg-blue-600 white when edits exist).

Sticky player bar: position sticky top-56px, h-13, bg-white/90 backdrop-blur-md, border-bottom gray-200, z-10. Contains: play/pause circle button (32px), seek bar (flex-1, h-1 gray-300 with blue fill), current time / total time (text-xs gray-500), speed selector "1x".

Transcript segments: mt-6, list of segment cards with gap-3. Each card: bg-white, border border-gray-200, rounded-xl, p-5.

Each segment card structure:
- Speaker label: flex row, small colored dot (8px, blue for Speaker A, green for Speaker B) + "Speaker A (Lex)" text (text-xs font-medium text-gray-500 uppercase tracking-wide).
- English text: mt-3, text-sm text-gray-400 italic leading-relaxed. Prefix "EN:" in text-xs font-medium.
- Chinese text: mt-2, text-sm text-gray-900 leading-relaxed. Prefix "CN:" in text-xs font-medium.
- Edit button: absolute bottom-right, text-xs text-gray-400 hover:text-blue-600, pencil icon + "编辑".

Active/playing segment: border-l-3 border-blue-500, bg-blue-50/50.

Edit mode (show on one segment as example): Chinese text replaced by auto-resize textarea with blue border, bg-blue-50, rounded-lg, p-3. Below textarea: flex justify-end gap-2, "取消" ghost button + "保存" blue button (text-sm).

Show about 4-5 segments alternating between Speaker A and Speaker B.

Style: Notion-like reading experience, ultra-clean, generous line-height, calm colors. No gradients, no dark mode, no heavy UI chrome.
```

#### For Midjourney / UI Screenshot Generation

```
UI design of a bilingual transcript review page for a podcast translation web app, light mode, white background, single column centered layout, sticky audio player bar at top, list of conversation segment cards alternating between two speakers, each card shows English text in gray italic and Chinese translation in dark text, small colored speaker label dots, one segment highlighted with blue left border and light blue background indicating current playback, clean edit button on each card, Notion-like reading experience, Swiss typography, Apple-like minimalism, generous whitespace and line-height, Inter font, soft rounded cards, single blue accent color, high resolution, 1440x900 desktop screenshot, Dribbble quality, UX/UI design --ar 16:10 --no cyberpunk, neon, glowing effects, dark theme, gradients, 3D elements, syntax highlighting
```

---

## 4. 页面四：登录 / 注册页 (Login / Register Page)

### 4.1 核心意图与组件清单 (Core Intent & Components)

- **UI 类型**：身份认证入口页（独立全屏布局，不含 TopNav）
- **核心功能区**：
  1. **品牌标识 (Brand Header)**：Logo + 产品名 + Slogan
  2. **短信登录表单 (SMS Login Form)**：手机号输入 + 验证码输入 + 发送倒计时
  3. **微信登录 (WeChat Login)**：微信扫码 / OAuth 登录按钮
  4. **协议勾选 (Agreement Checkbox)**：服务条款 + 隐私政策链接
  5. **页脚 (Footer)**：版权信息

### 4.2 布局与信息架构 (Layout & Structure)

```
骨架逻辑：全屏垂直居中布局（Full-screen centered）
最大内容宽度：400px
不含 TopNav，独立页面布局

┌─ Full-screen Container ──────────────────────────────┐
│  (flex, items-center, justify-center, min-h: 100vh)  │
│                                                       │
│  ┌─ Login Card (max-w: 400px, w: full) ────────────┐ │
│  │                                                   │ │
│  │  ┌─ Brand Header ────────────────────────────┐   │ │
│  │  │  Logo: 🎙️ (48px icon, centered)           │   │ │
│  │  │  H2: "PodFlow"                            │   │ │
│  │  │  Subtitle: "将英文播客翻译为中文"           │   │ │
│  │  │  text-align: center; margin-bottom: 40px;  │   │ │
│  │  └────────────────────────────────────────────┘   │ │
│  │                                                   │ │
│  │  ┌─ SMS Login Form ──────────────────────────┐   │ │
│  │  │  Label: "手机号" (Caption, --text-secondary)│   │ │
│  │  │  [🇨🇳 +86 ▾] [输入手机号              ]    │   │ │
│  │  │  flex row; 区号 Dropdown w-80px;          │   │ │
│  │  │  Input: flex-1; h-48px; border --border;  │   │ │
│  │  │                                            │   │ │
│  │  │  Label: "验证码" (mt: 16px)                │   │ │
│  │  │  [输入 6 位验证码       ] [获取验证码]      │   │ │
│  │  │  Input: flex-1; h-48px;                   │   │ │
│  │  │  发送按钮: w-120px; 点击后 60s 倒计时      │   │ │
│  │  │                                            │   │ │
│  │  │  [          登 录          ]               │   │ │
│  │  │  Primary Button: w-full; h-48px; mt-24px; │   │ │
│  │  │  bg --accent; 无手机号/未勾选协议时 disabled│   │ │
│  │  └────────────────────────────────────────────┘   │ │
│  │                                                   │ │
│  │  ┌─ Divider ─────────────────────────────────┐   │ │
│  │  │  ────────── 其他登录方式 ──────────         │   │ │
│  │  │  margin-y: 24px; --text-tertiary           │   │ │
│  │  └────────────────────────────────────────────┘   │ │
│  │                                                   │ │
│  │  ┌─ WeChat Login ────────────────────────────┐   │ │
│  │  │  [🟢 微信扫码登录]                         │   │ │
│  │  │  Secondary Button: w-full; h-48px;        │   │ │
│  │  │  border: 1px --border; 绿色微信 icon 左侧 │   │ │
│  │  └────────────────────────────────────────────┘   │ │
│  │                                                   │ │
│  │  ┌─ Agreement ───────────────────────────────┐   │ │
│  │  │  [☐] 我已阅读并同意 [服务条款] 和 [隐私政策]│   │ │
│  │  │  font: Caption; color: --text-tertiary;    │   │ │
│  │  │  链接: --accent 色; mt-16px;               │   │ │
│  │  └────────────────────────────────────────────┘   │ │
│  │                                                   │ │
│  └───────────────────────────────────────────────────┘ │
│                                                       │
│  ┌─ Footer ──────────────────────────────────────┐    │
│  │  "© 2026 PodFlow. All rights reserved."       │    │
│  │  font: Caption; color: --text-tertiary;       │    │
│  │  margin-top: 40px;                            │    │
│  └────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────┘
```

### 4.3 视觉风格与色彩规范 (Visual Style)

- **整体风格 (Style)**：Ultra-minimal auth page, Apple ID login-like simplicity, single card centered on plain white canvas
- **色彩模式 (Color Palette)**：Full white background (`--bg-primary`), no decorative elements. Only brand icon and `--accent` CTA button carry color
- **材质与光影 (Material & Lighting)**：No card shadow or boundary. Pure form elements on white. Inputs use 1px `--border` only
- **负向提示词 (Negative Prompts)**：No split-screen layout, no hero image, no illustrations, no gradients, no background patterns, no dark mode

### 4.4 交互状态矩阵

| 组件 | Default | Hover | Active/Focus | Disabled | Loading |
|------|---------|-------|-------------|----------|---------|
| 手机号输入 | border `--border` | border `--accent` | ring 2px `--accent-light` | — | — |
| 验证码输入 | border `--border` | border `--accent` | ring 2px `--accent-light` | — | — |
| 获取验证码 | `--accent` text 无底色 | underline | — | 灰色 + "59s 后重试" 倒计时文字 | Spinner |
| 登录按钮 | bg `--accent` 白字 | bg `--accent-hover` | scale 0.98 | bg `--bg-tertiary` 灰字（未勾选协议/手机号为空） | Spinner + "登录中..." |
| 微信登录 | outline + 绿色微信 icon | bg `--bg-tertiary` | scale 0.98 | — | 跳转微信 OAuth 页面 |
| 协议勾选 | 空心方框 `--border` | — | 勾选 ✓ + `--accent` 填充 | — | — |

### 4.5 专属 AI 生成提示词 (Ready-to-Use Prompt)

#### For v0.dev / Bolt.new (React + Tailwind)

```
Build a minimal login page for a podcast translation app called "PodFlow".

Tech stack: Next.js + Tailwind CSS + Lucide icons.

Layout: Full-screen centered (min-h-screen flex items-center justify-center), white background (#FFFFFF). No navigation bar.

Brand header: centered, 🎙️ emoji (text-5xl), below "PodFlow" (text-2xl font-semibold text-gray-900), below "将英文播客翻译为中文" (text-sm text-gray-500 mt-1). Margin-bottom 10.

SMS form: max-w-sm w-full. Phone row: flex gap-3. Country code selector "🇨🇳 +86" (w-20 h-12 border border-gray-300 rounded-lg text-sm). Phone input (flex-1 h-12 border rounded-lg px-4 placeholder "输入手机号").

Code row: mt-4 flex gap-3. Code input (flex-1 h-12 border rounded-lg placeholder "输入 6 位验证码"). Send code button (w-28 h-12 text-blue-600 text-sm font-medium hover:underline). Disabled state shows gray "59s" countdown.

Login button: mt-6 w-full h-12 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700. Disabled: bg-gray-200 text-gray-400.

Divider: "── 其他登录方式 ──" (text-xs text-gray-400 my-6).

WeChat button: w-full h-12 border border-gray-300 rounded-lg flex items-center justify-center gap-2. Green WeChat icon (fill-green-500) + "微信扫码登录" text-sm.

Agreement: mt-4 flex items-start gap-2. Checkbox (w-4 h-4 rounded border-gray-300). Text "我已阅读并同意 服务条款 和 隐私政策" (text-xs text-gray-400), links in text-blue-600.

Footer: mt-10 text-center text-xs text-gray-300 "© 2026 PodFlow".

Style: Ultra-clean, Apple ID login-like. No illustrations, no gradients, no dark mode, no hero images.
```

#### For Midjourney / UI Screenshot Generation

```
UI design of a minimal login page for a podcast translation web app, light mode, full white background, centered login form, brand logo emoji microphone at top, app name in clean sans-serif typography, phone number input with country code dropdown, verification code input with send code button, blue full-width login CTA button, WeChat login option below a divider, terms agreement checkbox at bottom, Apple ID login page-like simplicity, Swiss design influence, generous whitespace, Inter font, single blue accent color, no illustrations, high resolution, 1440x900 desktop screenshot, Dribbble quality, UX/UI design --ar 16:10 --no illustrations, hero images, gradients, dark theme, split-screen, decorative backgrounds, 3D elements
```

---

## 5. 页面五：个人主页 / 设置页 (Profile / Settings Page)

### 5.1 核心意图与组件清单 (Core Intent & Components)

- **UI 类型**：用户信息管理与配额查看页
- **核心功能区**：
  1. **用户信息卡片 (Profile Card)**：头像 + 昵称（可编辑）+ 手机号 + 注册时间
  2. **配额使用概览 (Quota Overview)**：本月用量/总额度 + 进度条 + 重置日期
  3. **偏好设置 (Preferences)**：通知开关、默认输出格式
  4. **退出登录 (Logout)**：危险操作按钮

### 5.2 布局与信息架构 (Layout & Structure)

```
骨架逻辑：单列居中布局（Single-column centered）
最大内容宽度：640px
复用 ProtectedLayout（含 TopNav）

┌─ Full-width Top Nav ─────────────────────────────────┐
│  [← 返回]                    个人中心                  │
│  height: 56px; border-bottom: 1px solid --border      │
└───────────────────────────────────────────────────────┘

┌─ Content Container (max-w: 640px, mx: auto) ─────────┐
│                                                       │
│  ┌─ Profile Card ──────────────────────────────────┐  │
│  │  [🧑 64px Avatar, rounded-full]                  │  │
│  │  H2: "用户昵称" (右侧 ✏️ 编辑图标)               │  │
│  │  Caption: "138****1234 · 注册于 2026-03-15"       │  │
│  │  margin-top: 40px; text-align: center;            │  │
│  │  padding: 32px; bg: --bg-secondary;               │  │
│  │  radius: --radius-lg;                             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Quota Section ─────────────────────────────────┐  │
│  │  H3: "用量配额" (mt: 32px; mb: 16px)             │  │
│  │                                                  │  │
│  │  ┌─ Quota Card ──────────────────────────────┐   │  │
│  │  │  flex row justify-between:                │   │  │
│  │  │    "本月已使用"          "2 / 5 集"        │   │  │
│  │  │                                           │   │  │
│  │  │  ┌─ Progress Bar ─────────────────────┐   │   │  │
│  │  │  │  h-6px; radius: 3px;               │   │   │  │
│  │  │  │  bg-track: --bg-tertiary;          │   │   │  │
│  │  │  │  bg-fill: --accent; width: 40%;    │   │   │  │
│  │  │  │  额度 ≤ 1: fill → --warning;       │   │   │  │
│  │  │  └────────────────────────────────────┘   │   │  │
│  │  │                                           │   │  │
│  │  │  Caption: "额度将于 4月30日 重置"          │   │  │
│  │  │  额度 ≤ 1 时追加:                         │   │  │
│  │  │    [✨ 升级获取更多额度] --accent link      │   │  │
│  │  │                                           │   │  │
│  │  │  bg: --bg-secondary; radius: --radius-md; │   │  │
│  │  │  padding: 20px;                           │   │  │
│  │  └───────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Settings Section ──────────────────────────────┐  │
│  │  H3: "偏好设置" (mt: 32px; mb: 16px)             │  │
│  │                                                  │  │
│  │  ┌─ Setting Row ─────────────────────────────┐   │  │
│  │  │  "翻译完成通知"              [Toggle ◉]   │   │  │
│  │  │  py: 16px; border-bottom: 1px --border;   │   │  │
│  │  └───────────────────────────────────────────┘   │  │
│  │  ┌─ Setting Row ─────────────────────────────┐   │  │
│  │  │  "默认输出格式"              [MP3 ▾]      │   │  │
│  │  │  py: 16px; border-bottom: 1px --border;   │   │  │
│  │  └───────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Danger Zone ───────────────────────────────────┐  │
│  │  [退出登录]                                      │  │
│  │  Ghost Button: color --error; w-full; mt-48px;   │  │
│  │  hover: bg rgba(220,38,38, 0.05);               │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  padding-bottom: 64px;                                │
└───────────────────────────────────────────────────────┘
```

### 5.3 视觉风格与色彩规范 (Visual Style)

- **整体风格 (Style)**：Settings page, Apple Account-like simplicity, functional and calm layout
- **色彩模式 (Color Palette)**：Light mode, white dominant. Profile card 和 Quota card 使用 `--bg-secondary` 浅灰底色形成层次。配额进度条正常为 `--accent`，低额度时为 `--warning`
- **材质与光影 (Material & Lighting)**：Flat cards with subtle background differentiation, no shadows, rounded corners for card containers
- **负向提示词 (Negative Prompts)**：No complex dashboard, no charts/graphs, no dark mode, no gamification elements, no profile banners

### 5.4 交互状态矩阵

| 组件 | Default | Hover | Active | 数据状态 |
|------|---------|-------|--------|---------|
| 头像 | 灰色占位圆 / 用户图片 | 半透明遮罩 + Camera icon | 弹出文件选择 | — |
| 昵称 | 纯文本显示 | ✏️ 图标出现 | inline Input + [确认][取消] | — |
| 配额进度条 | `--accent` 蓝色填充 | — | — | ≤1 集变 `--warning` 橙色 |
| Toggle 开关 | 灰色(off) / `--accent`(on) | — | 滑动动画 0.2s ease | 保存立即生效 |
| 退出登录按钮 | `--error` 文字 | 浅红底色 | 弹出确认 Modal | — |

### 5.5 专属 AI 生成提示词 (Ready-to-Use Prompt)

#### For v0.dev / Bolt.new (React + Tailwind)

```
Build a profile/settings page for a podcast translation app called "PodFlow".

Tech stack: Next.js + Tailwind CSS + Lucide icons.

Layout: Single-column centered (max-w-xl), white background.

Top nav: 56px, left "← 返回" link (text-gray-600), center "个人中心" text (font-medium), border-bottom gray-200.

Profile card: mt-10, bg-gray-50, rounded-2xl, p-8, text-center. Avatar circle (64px, bg-gray-300 rounded-full, centered). Name "用户昵称" (text-xl font-semibold mt-4) with pencil icon. Meta "138****1234 · 注册于 2026-03-15" (text-xs text-gray-400 mt-1).

Quota section: mt-8. H3 "用量配额" (text-lg font-semibold mb-4). Quota card (bg-gray-50 rounded-xl p-5): top row flex justify-between "本月已使用" left, "2 / 5 集" right (text-sm). Progress bar (mt-3, h-1.5, rounded-full, bg-gray-200, 40% fill bg-blue-600). Caption "额度将于 4月30日 重置" (text-xs text-gray-400 mt-2).

Settings section: mt-8. H3 "偏好设置". Two setting rows: "翻译完成通知" with toggle switch (right), "默认输出格式" with "MP3" dropdown (right). Each row py-4 border-b border-gray-100 flex justify-between items-center.

Logout button: mt-12 w-full py-3 text-red-500 text-sm font-medium hover:bg-red-50 rounded-lg transition.

Style: Clean settings page, Apple-like. No gradients, no dark mode.
```

#### For Midjourney / UI Screenshot Generation

```
UI design of a user profile and settings page for a podcast translation web app, light mode, white background, single column centered layout, top bar with back button, centered user avatar circle with name below, usage quota card with progress bar showing 2 of 5 episodes used, preference settings with toggle switches, logout button at bottom in red text, Apple Account settings page-like design, Swiss minimalism, generous whitespace, Inter font, soft rounded cards with light gray backgrounds, single blue accent color, high resolution, 1440x900 desktop screenshot, Dribbble quality, UX/UI design --ar 16:10 --no cyberpunk, neon, dark theme, gradients, complex dashboards, gamification
```

---

## 6. 页面六：任务历史列表页 (Task History Page)

### 6.1 核心意图与组件清单 (Core Intent & Components)

- **UI 类型**：列表管理页 / 历史记录归档页
- **核心功能区**：
  1. **页面标题 (Page Header)**：标题 + 总条数统计
  2. **筛选与排序 (Filter Bar)**：状态筛选（全部/进行中/已完成/失败）+ 时间排序下拉
  3. **任务列表 (Task List)**：可分页的详细任务卡片列表
  4. **分页器 (Pagination)**：简洁的上下页导航
  5. **空状态 (Empty State)**：无任务时的引导

> **与首页「最近翻译」的区别**：首页仅展示最近 5 条快速访问入口，本页为完整分页列表，支持按状态筛选与排序。

### 6.2 布局与信息架构 (Layout & Structure)

```
骨架逻辑：单列居中布局（Single-column centered）
最大内容宽度：720px
复用 ProtectedLayout（含主 TopNav）

┌─ Full-width Top Nav ─────────────────────────────────┐
│  [🎙️ PodFlow]                           [Avatar ▾]   │
│  height: 56px; border-bottom: 1px solid --border      │
└───────────────────────────────────────────────────────┘

┌─ Content Container (max-w: 720px, mx: auto) ─────────┐
│                                                       │
│  ┌─ Page Header ───────────────────────────────────┐  │
│  │  H2: "翻译历史"                                  │  │
│  │  Caption: "共 23 条翻译记录" (--text-secondary)   │  │
│  │  margin-top: 40px; margin-bottom: 24px;          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Filter Bar ────────────────────────────────────┐  │
│  │  [全部] [进行中] [已完成] [失败]     [最新 ▾]     │  │
│  │  左侧: Pill tabs, gap: 8px;                      │  │
│  │  右侧: Sort dropdown (最新/最早/时长);            │  │
│  │  Active tab: bg --accent-light, text --accent;   │  │
│  │  Inactive: bg transparent, text --text-secondary; │  │
│  │  margin-bottom: 16px;                            │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Task Card (详细版) ────────────────────────────┐  │
│  │  flex row, items-center                          │  │
│  │                                                  │  │
│  │  [🎧 36px]  ┌─ Info ────────────┐  ┌─ Right ──┐│  │
│  │             │ H3: "Lex Frid..." │  │ ✅ 已完成 ││  │
│  │             │ Body: "Sam Alt.." │  │           ││  │
│  │             │ Caption: 2:15:30  │  │ [▶] [⬇️]  ││  │
│  │             │  · 3 天前         │  │           ││  │
│  │             └──────────────────┘  └──────────┘│  │
│  │                                                  │  │
│  │  padding: 16px; border: 1px --border;            │  │
│  │  radius: --radius-md; hover: --shadow-sm;        │  │
│  │  cursor: pointer → 点击跳转 /tasks/:id           │  │
│  │                                                  │  │
│  │  状态变体:                                        │  │
│  │    ✅ 已完成 (--success) → [▶ 播放] [⬇️ 下载]    │  │
│  │    🔄 翻译中 68% (--warning) → 进度文字           │  │
│  │    ❌ 失败 (--error) → [重试]                     │  │
│  │    ⏳ 排队中 (--text-tertiary) → 等待文字         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  (gap: 8px, repeat × N)                               │
│                                                       │
│  ┌─ Pagination ────────────────────────────────────┐  │
│  │  [← 上一页]   第 1 / 5 页   [下一页 →]           │  │
│  │  margin-top: 24px; flex justify-center; gap: 16px│  │
│  │  Ghost Buttons; disabled 态 opacity 0.4;         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ── 空状态（无任何任务时替换列表区域） ──                 │
│  ┌─ Empty State ───────────────────────────────────┐  │
│  │  🎙️ (极简线条图标, 64px, --text-tertiary)        │  │
│  │  H3: "还没有翻译记录"                             │  │
│  │  Body: "上传第一条播客，开始体验 AI 翻译"          │  │
│  │  [开始翻译] Primary Button → link to /           │  │
│  │  text-align: center; padding: 64px 0;            │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  padding-bottom: 64px;                                │
└───────────────────────────────────────────────────────┘
```

### 6.3 视觉风格与色彩规范 (Visual Style)

- **整体风格 (Style)**：Clean list page, Linear-app-like task management, scan-friendly card layout
- **色彩模式 (Color Palette)**：Light mode, white dominant. Filter pills 使用 `--accent-light` 浅蓝底高亮当前筛选。四色状态系统与 §2 任务详情页保持一致
- **材质与光影 (Material & Lighting)**：Flat card list, 1px border, hover shadow, no decorative elements
- **负向提示词 (Negative Prompts)**：No complex table layout, no dark mode, no heavy grid system, no icons overload

### 6.4 交互状态矩阵

| 组件 | Default | Hover | Active |
|------|---------|-------|--------|
| 筛选 Tab | bg 透明, `--text-secondary` | bg `--bg-tertiary` | bg `--accent-light`, text `--accent`, font-medium |
| 排序 Dropdown | border `--border`, text `--text-secondary` | `--shadow-sm` | 展开选项列表 |
| 任务卡片 | border `--border` | `--shadow-sm` + translate-y(-1px) | → 导航到 `/tasks/:id` |
| 卡片内快捷按钮 | icon `--text-tertiary` | icon `--accent` | 执行操作（播放/下载/重试） |
| 分页按钮 | Ghost, `--text-secondary` | underline | 加载下一页 |

### 6.5 专属 AI 生成提示词 (Ready-to-Use Prompt)

#### For v0.dev / Bolt.new (React + Tailwind)

```
Build a task history list page for a podcast translation app called "PodFlow".

Tech stack: Next.js + Tailwind CSS + Lucide icons.

Layout: Single-column centered (max-w-2xl), white background.

Top nav: 56px, logo "🎙️ PodFlow" left, avatar circle right, border-bottom gray-200.

Page header: mt-10. H2 "翻译历史" (text-xl font-semibold). Below "共 23 条翻译记录" (text-sm text-gray-400 mt-1).

Filter bar: mt-6 flex justify-between items-center. Left: pill tabs ["全部", "进行中", "已完成", "失败"], each px-3 py-1.5 rounded-full text-sm. Active: bg-blue-50 text-blue-600 font-medium. Inactive: text-gray-500 hover:bg-gray-100. Right: sort dropdown "最新 ▾" (text-sm text-gray-500 border rounded-lg px-3 py-1.5).

Task cards: mt-4, list with gap-2. Each card: flex items-center p-4 border border-gray-200 rounded-xl hover:shadow-sm transition cursor-pointer. Left: headphones icon (36px text-gray-400). Center (flex-1 ml-4): title (text-sm font-medium truncate), subtitle (text-xs text-gray-400 mt-0.5 truncate), meta "2:15:30 · 3 天前" (text-xs text-gray-300 mt-1). Right: status badge + action buttons.

Status badges: "✅ 已完成" green-100 text-green-700, "🔄 68%" amber-100 text-amber-700, "❌ 失败" red-100 text-red-700, "⏳ 排队中" gray-100 text-gray-500. All: text-xs px-2 py-0.5 rounded-full.

Show 5 cards with mixed statuses. Completed cards show play and download icon buttons.

Pagination: mt-6 flex justify-center items-center gap-4. "← 上一页" and "下一页 →" ghost buttons (text-sm text-gray-500 hover:underline). Center "第 1 / 5 页" (text-xs text-gray-400).

Style: Linear-app-like task list, ultra-clean. No gradients, no dark mode.
```

#### For Midjourney / UI Screenshot Generation

```
UI design of a task history list page for a podcast translation web app, light mode, white background, single column centered layout, clean top navigation bar, page title with record count, pill-style filter tabs for status filtering, list of podcast task cards with headphones icon and status badges in green amber and gray, each card showing episode title and metadata, pagination controls at bottom, Linear app-like task management aesthetic, Swiss minimalism, generous whitespace, Inter font, soft rounded cards, single blue accent color, high resolution, 1440x900 desktop screenshot, Dribbble quality, UX/UI design --ar 16:10 --no cyberpunk, neon, dark theme, gradients, complex tables, 3D elements
```

---

## 7. 页面七：404 未找到页面 (Not Found Page)

### 7.1 核心意图与组件清单 (Core Intent & Components)

- **UI 类型**：全局错误页 / 死链兜底（独立全屏布局，不含 TopNav）
- **核心功能区**：
  1. **错误状态码 (Error Code)**：巨大灰色 "404" 作装饰
  2. **错误信息 (Error Message)**：标题 + 描述文案
  3. **导航按钮 (Navigation CTA)**：返回首页按钮

### 7.2 布局与信息架构 (Layout & Structure)

```
骨架逻辑：全屏垂直居中布局（Full-screen centered）
无 TopNav，独立全屏

┌─ Full-screen Container ──────────────────────────────┐
│  (flex, items-center, justify-center, min-h: 100vh)  │
│                                                       │
│  ┌─ Error Content (text-align: center) ────────────┐ │
│  │                                                   │ │
│  │  "404"                                            │ │
│  │  font-size: 120px; font-weight: 700;              │ │
│  │  color: --bg-tertiary (#F1F3F5);                  │ │
│  │  letter-spacing: 8px; line-height: 1;             │ │
│  │                                                   │ │
│  │  H2: "页面未找到"                                  │ │
│  │  margin-top: -16px; color: --text-primary;        │ │
│  │                                                   │ │
│  │  Body: "你访问的页面不存在或已被移除"               │ │
│  │  color: --text-secondary; margin-top: 8px;        │ │
│  │                                                   │ │
│  │  [🏠 返回首页]                                    │ │
│  │  Primary Button: margin-top: 32px;                │ │
│  │  bg --accent; px-6; h-12; rounded-lg;             │ │
│  │                                                   │ │
│  └───────────────────────────────────────────────────┘ │
│                                                       │
└───────────────────────────────────────────────────────┘
```

### 7.3 视觉风格与色彩规范 (Visual Style)

- **整体风格 (Style)**：Ultra-minimal error page, gigantic muted number as decorative element, single clear CTA
- **色彩模式 (Color Palette)**：White background. "404" 使用极浅灰 `--bg-tertiary` 作为装饰数字。仅返回按钮使用 `--accent`
- **负向提示词 (Negative Prompts)**：No illustrations, no animations, no emoji as decoration, no complex graphics, no dark mode

### 7.4 专属 AI 生成提示词 (Ready-to-Use Prompt)

#### For v0.dev / Bolt.new (React + Tailwind)

```
Build a minimal 404 page for a web app called "PodFlow".

Tech stack: Next.js + Tailwind CSS.

Layout: Full-screen centered (min-h-screen flex items-center justify-center), white background. No navigation bar.

Content centered: "404" in giant text (text-9xl font-bold text-gray-100 tracking-widest). Below (overlapping slightly, -mt-4): H2 "页面未找到" (text-xl font-semibold text-gray-900). Below: "你访问的页面不存在或已被移除" (text-sm text-gray-500 mt-2). Below: "🏠 返回首页" button (mt-8 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium).

Style: Ultra-minimal, Apple-like. No illustrations, no animations.
```

---

## 8. 页面八：升级 / 定价页 (Pricing Page) — Phase 4

### 8.1 核心意图与组件清单 (Core Intent & Components)

- **UI 类型**：商业化转化页 / 定价方案展示
- **核心功能区**：
  1. **定价标题 (Pricing Header)**：核心价值传达 + "选择适合你的方案"
  2. **方案卡片 (Plan Cards)**：免费版 / 标准版 / 专业版，三列对比
  3. **FAQ 折叠面板 (FAQ Accordion)**：定价相关常见问题

### 8.2 布局与信息架构 (Layout & Structure)

```
骨架逻辑：单列居中（Header + FAQ） + 三列并排（卡片区）
最大内容宽度：960px
复用 ProtectedLayout（含 TopNav）

┌─ Full-width Top Nav ─────────────────────────────────┐
│  [🎙️ PodFlow]                           [Avatar ▾]   │
│  height: 56px; border-bottom: 1px solid --border      │
└───────────────────────────────────────────────────────┘

┌─ Content Container (max-w: 960px, mx: auto) ─────────┐
│                                                       │
│  ┌─ Pricing Header ───────────────────────────────┐  │
│  │  H1: "选择适合你的方案"                          │  │
│  │  Subtitle: "从免费开始，按需升级"                 │  │
│  │  text-align: center;                             │  │
│  │  margin-top: 64px; margin-bottom: 48px;          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Plan Cards (flex row, gap: 24px) ──────────────┐ │
│  │                                                  │ │
│  │  ┌─ Free ──────┐ ┌─ Standard ──┐ ┌─ Pro ─────┐ │ │
│  │  │ "免费版"     │ │ ⭐ "标准版"  │ │ "专业版"   │ │ │
│  │  │ ¥0/月       │ │ ¥29/月      │ │ ¥99/月    │ │ │
│  │  │             │ │ 推荐 Badge  │ │           │ │ │
│  │  │ · 5集/月    │ │ · 30集/月   │ │ · 无限    │ │ │
│  │  │ · 单/双人   │ │ · 多说话人  │ │ · API 访问│ │ │
│  │  │ · MP3 输出  │ │ · MP3/AAC   │ │ · 优先处理│ │ │
│  │  │             │ │ · 校对编辑  │ │ · 校对编辑│ │ │
│  │  │ [当前方案]   │ │ [升级]      │ │ [升级]    │ │ │
│  │  │ disabled btn│ │ accent btn  │ │ accent btn│ │ │
│  │  └────────────┘ └─────────────┘ └───────────┘ │ │
│  │                                                  │ │
│  │  所有卡片: radius --radius-lg; padding 32px;     │ │
│  │  默认: border 1px --border;                      │ │
│  │  推荐卡片: border 2px --accent;                  │ │
│  │  推荐 Badge: absolute -top-3, bg --accent,       │ │
│  │    white text, px-3 py-1, text-xs, rounded-full; │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  ┌─ FAQ Section ───────────────────────────────────┐  │
│  │  H3: "常见问题" (mt: 64px; mb: 24px)             │  │
│  │  max-width: 640px; mx: auto;                     │  │
│  │                                                  │  │
│  │  ┌─ Accordion Item ─────────────────────────┐    │  │
│  │  │  Q: "额度每月什么时候重置？"      [▾]     │    │  │
│  │  │  A: (展开) "每月 1 日自动重置..."         │    │  │
│  │  │  py: 16px; border-bottom: 1px --border;  │    │  │
│  │  └──────────────────────────────────────────┘    │  │
│  │  ┌─ Accordion Item ─────────────────────────┐    │  │
│  │  │  Q: "可以随时取消订阅吗？"        [▾]     │    │  │
│  │  └──────────────────────────────────────────┘    │  │
│  │  ┌─ Accordion Item ─────────────────────────┐    │  │
│  │  │  Q: "支持哪些支付方式？"          [▾]     │    │  │
│  │  └──────────────────────────────────────────┘    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  padding-bottom: 64px;                                │
└───────────────────────────────────────────────────────┘
```

### 8.3 视觉风格与色彩规范 (Visual Style)

- **整体风格 (Style)**：Clean pricing page, Stripe/Linear-inspired pricing layout, comparison-friendly card design
- **色彩模式 (Color Palette)**：Light mode. 推荐方案卡片使用 `--accent` 边框 + 顶部 Badge 突出。其余卡片使用 `--border` 默认边框
- **材质与光影 (Material & Lighting)**：Flat price cards, no shadows. 推荐卡片通过 2px accent border 形成视觉层次
- **负向提示词 (Negative Prompts)**：No dark mode, no gradient cards, no heavy decorations, no complex comparison tables

### 8.4 交互状态矩阵

| 组件 | Default | Hover | Active |
|------|---------|-------|--------|
| 方案卡片 | border `--border` | `--shadow-sm` | — |
| 推荐卡片 | border 2px `--accent` | `--shadow-md` | — |
| 升级按钮 | bg `--accent` 白字 | bg `--accent-hover` | scale 0.98 |
| 当前方案按钮 | bg `--bg-tertiary` 灰字 | — | — (disabled) |
| Accordion | 折叠状态, ChevronDown | 文字 `--accent` | ChevronUp, 内容展开 |

### 8.5 响应式策略

| 断点 | 布局调整 |
|------|---------|
| Desktop ≥ 1024px | 三列卡片并排，FAQ 居中 640px |
| Tablet 768–1023px | 三列缩窄，减少内边距 |
| Mobile < 768px | 单列堆叠，推荐方案置顶，FAQ 全宽 |

### 8.6 专属 AI 生成提示词 (Ready-to-Use Prompt)

#### For v0.dev / Bolt.new (React + Tailwind)

```
Build a pricing page for a podcast translation app called "PodFlow".

Tech stack: Next.js + Tailwind CSS + Lucide icons.

Layout: Single-column centered, white background. Max-width 4xl for cards, 2xl for FAQ.

Top nav: 56px, logo left, avatar right, border-bottom gray-200.

Pricing header: mt-16 text-center. H1 "选择适合你的方案" (text-3xl font-bold). Subtitle "从免费开始，按需升级" (text-base text-gray-500 mt-2 mb-12).

Three plan cards: flex row gap-6 justify-center. Each card: flex-1 max-w-xs, border border-gray-200; rounded-2xl, p-8.

Free card: "免费版" (text-lg font-semibold), "¥0/月" (text-3xl font-bold mt-2), feature list (mt-6, list, text-sm text-gray-600, gap-3): "5 集/月", "单/双人播客", "MP3 输出". Button "当前方案" (mt-8 w-full py-3 bg-gray-100 text-gray-400 rounded-lg cursor-not-allowed).

Standard card (recommended): same structure but border-2 border-blue-600. Relative positioned. Badge: absolute -top-3 left-1/2 -translate-x-1/2, bg-blue-600 text-white text-xs px-3 py-1 rounded-full "推荐". "标准版", "¥29/月". Features: "30 集/月", "多说话人支持", "MP3/AAC 输出", "校对编辑". Button "升级" (bg-blue-600 text-white hover:bg-blue-700).

Pro card: "专业版", "¥99/月". Features: "无限翻译", "API 访问", "优先处理", "校对编辑". Button "升级" (bg-blue-600 text-white).

FAQ section: mt-16 max-w-2xl mx-auto. H3 "常见问题" (text-lg font-semibold mb-6). Three accordion items: "额度每月什么时候重置？", "可以随时取消订阅吗？", "支持哪些支付方式？". Each: py-4 border-b border-gray-200, flex justify-between, chevron-down icon. Click to expand answer text.

Style: Stripe-like pricing, clean and trustworthy. No gradients, no dark mode.
```

#### For Midjourney / UI Screenshot Generation

```
UI design of a pricing page for a podcast translation web app, light mode, white background, three pricing plan cards side by side, free standard and pro tiers, middle card highlighted with blue border and recommended badge, each card showing price per month and feature checklist, upgrade buttons in blue, FAQ accordion section below, Stripe pricing page-like design, Swiss minimalism, generous whitespace, Inter font, soft rounded cards, single blue accent color, high resolution, 1440x900 desktop screenshot, Dribbble quality, UX/UI design --ar 16:10 --no cyberpunk, neon, dark theme, gradients, complex tables, 3D elements
```

---

## 9. 全局组件补充 (Global Component Additions)

### 9.1 TopNav 头像下拉菜单 (Avatar Dropdown Menu)

> 适用于所有 `(protected)` 路由组页面的 TopNav 右侧头像交互。

```
Avatar (w-8 h-8, rounded-full) 点击后展开 Dropdown：

┌─ Avatar Dropdown ──────────────────┐
│  ┌─ User Info Header ───────────┐  │
│  │  [🧑 32px avatar] "用户昵称" │  │
│  │  "138****1234"               │  │
│  │  padding: 12px 16px;         │  │
│  │  border-bottom: 1px --border;│  │
│  └──────────────────────────────┘  │
│                                    │
│  [👤 个人中心]          → /profile │
│  [📋 翻译历史]          → /tasks   │
│  [✨ 升级方案]          → /pricing │
│                                    │
│  ────────── (分割线) ──────────     │
│                                    │
│  [↩️ 退出登录]          → /login   │
│                                    │
│  min-width: 200px;                │
│  bg: white; shadow: --shadow-lg;  │
│  radius: --radius-md;             │
│  border: 1px --border;            │
│  z-index: 20;                     │
│  position: absolute; top: 48px;   │
│  right: 0;                        │
│                                    │
│  菜单项: py-8px px-16px;          │
│  hover: bg --bg-tertiary;         │
│  font: Body; color: --text-primary│
│  退出登录: color --error;          │
│                                    │
│  动画: fadeIn + translateY(-4px)   │
│       → translateY(0), 0.15s ease; │
│                                    │
│  外部点击关闭 (click-outside)      │
└────────────────────────────────────┘
```

### 9.2 Toast 通知系统 (Toast Notification System)

```
┌─ Toast Container ────────────────────────────────────┐
│  position: fixed; top: 72px; right: 24px;            │
│  z-index: 50; max-width: 360px;                      │
│  display: flex; flex-direction: column; gap: 8px;    │
│                                                       │
│  ┌─ Toast Item ──────────────────────────────────┐   │
│  │  [Icon 20px] [Message text flex-1]  [× Close] │   │
│  │  flex row, items-center; gap: 12px;            │   │
│  │  padding: 12px 16px;                           │   │
│  │  radius: --radius-sm;                          │   │
│  │  shadow: --shadow-md;                          │   │
│  │  bg: white;                                    │   │
│  │  border-left: 3px solid [type-color];          │   │
│  │                                                │   │
│  │  四种类型:                                      │   │
│  │    ✅ Success: border-left --success (#16A34A)  │   │
│  │    ❌ Error:   border-left --error (#DC2626)    │   │
│  │    ⚠️ Warning: border-left --warning (#F59E0B)  │   │
│  │    ℹ️ Info:    border-left --accent (#2563EB)   │   │
│  │                                                │   │
│  │  进入动画: slideInRight 0.3s ease-out;          │   │
│  │  退出动画: fadeOut 0.2s;                        │   │
│  │  自动消失: 5s 后触发退出动画;                    │   │
│  │  Close 按钮: 手动关闭;                          │   │
│  └────────────────────────────────────────────────┘   │
│                                                       │
│  (多条 Toast 垂直堆叠, 最新在上)                      │
└───────────────────────────────────────────────────────┘
```

**Toast 使用场景映射**：

| 触发场景 | Toast 类型 | 文案示例 | 自动消失 |
|---------|-----------|---------|---------|
| 翻译任务创建 | ✅ Success | "任务已创建，正在处理中..." | 5s |
| 翻译完成推送 | ✅ Success | "「Lex Fridman #421」翻译完成！" | 不消失, 需手动关闭 |
| 文件格式错误 | ❌ Error | "不支持该格式，请上传 MP3/WAV/M4A 文件" | 5s |
| 上传失败 | ❌ Error | "上传失败，请检查网络后重试" | 5s |
| 额度不足 | ⚠️ Warning | "额度已用完，升级解锁更多" | 不消失 |
| 网络断开 | ⚠️ Warning | "网络连接已断开，正在尝试重连..." | 不消失 |
| 译文保存成功 | ✅ Success | "译文已保存" | 3s |
| 复制链接 | ℹ️ Info | "已复制到剪贴板" | 3s |
| 登录过期 | ⚠️ Warning | "登录已过期，请重新登录" → 自动跳转 /login | 3s |

### 9.3 骨架屏 (Skeleton Loader)

> 页面数据加载期间显示的占位 UI，与实际组件保持尺寸与圆角一致。

```
── 首页骨架屏示例 ──

┌─ Top Nav ─────────────────────────────────────────────┐
│  [■■■ Logo placeholder]                 [● Avatar]    │
└───────────────────────────────────────────────────────┘

┌─ Content ─────────────────────────────────────────────┐
│                                                       │
│       ■■■■■■■■■■■■■■■■■           ← H1 骨架          │
│       ■■■■■■■■■■■■■■■■■■■■■       ← Subtitle 骨架    │
│                                                       │
│  ┌─ Upload Zone Skeleton ──────────────────────────┐  │
│  │                                                 │  │
│  │          ■■■■■ (pulse animation)                │  │
│  │          ■■■■■■■■■■■                            │  │
│  │                                                 │  │
│  │  height: 200px; radius: --radius-lg;            │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ Card Skeleton ─────────────────────────────────┐  │
│  │  [● 36px] ■■■■■■■■■■■              ■■■■        │  │
│  │           ■■■■■■■■                              │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─ Card Skeleton ─────────────────────────────────┐  │
│  │  [● 36px] ■■■■■■■■■■■■■■           ■■■         │  │
│  │           ■■■■■                                 │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─ Card Skeleton ─────────────────────────────────┐  │
│  │  [● 36px] ■■■■■■■■■■               ■■■■■       │  │
│  │           ■■■■■■■■■■                            │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
```

**骨架屏设计规范**：

| Token | 值 | 说明 |
|-------|----|------|
| 骨架色 | `--bg-tertiary` (#F1F3F5) | 所有占位块的底色 |
| 动画 | `pulse`: opacity 0.4 → 1.0 → 0.4, 1.5s ease-in-out infinite | 微妙的呼吸闪烁 |
| 文本骨架 | height: 对应字号; border-radius: 4px | 圆角矩形条 |
| 图标骨架 | 对应尺寸 circle | 圆形占位 |
| 卡片骨架 | 与实际卡片相同尺寸、圆角、内边距 | 保持布局稳定 |

**各页面骨架屏覆盖**：

| 页面 | 骨架内容 |
|------|---------|
| 首页 | Hero 文字骨架 + 上传区骨架 + 3 张任务卡片骨架 |
| 任务详情 | 标题骨架 + 进度面板骨架（5 行步骤条） |
| 任务列表 | 筛选栏骨架 + 5 张任务卡片骨架 |
| 个人中心 | 头像骨架 + 名称骨架 + 配额卡片骨架 |
| 中英文对照 | 播放器骨架 + 3 张 Segment 卡片骨架 |

---

## 10. 组件规范速查表 (Component Quick Reference)

| 组件 | 规格 | 示例 |
|------|------|------|
| **Primary Button** | h-12, px-6, bg-`--accent`, white text, rounded-lg, font-medium | "开始翻译" / "下载 MP3" |
| **Secondary Button** | h-12, px-6, border `--border`, `--text-primary`, rounded-lg | "查看中英文对照" |
| **Ghost Button** | h-8, px-3, no border, `--text-secondary`, hover: `--bg-tertiary` | "取消" / "编辑" |
| **Text Input** | h-12, px-4, border `--border`, rounded-lg, focus: ring `--accent` | URL 输入框 |
| **Task Card** | p-4, border `--border`, rounded-xl, hover: `--shadow-sm` | 任务列表项 |
| **Status Badge** | px-2 py-0.5, rounded-full, text-xs font-medium | "✅ 已完成" / "🔄 72%" |
| **Progress Bar** | h-1.5, rounded-full, bg-track: `--bg-tertiary`, bg-fill: `--accent` | 总进度条 |
| **Audio Player** | h-16, p-4, bg-`--bg-secondary`, rounded-xl | 播放器容器 |
| **Segment Card** | p-5, border `--border`, rounded-xl, active: border-l-3 `--accent` | 对照文本段落 |
| **Divider** | h-px, bg-`--border`, my-6, 或带文字居中分割 | "── 或者 ──" |
| **Avatar** | w-8 h-8, rounded-full, bg-`--bg-tertiary` | 导航栏用户头像 |
| **Dropdown** | `--shadow-lg`, rounded-lg, border `--border`, bg-white | 头像菜单 / 倍速选择 |
| **Toggle Switch** | w-10 h-5, rounded-full, transition 0.2s, active: bg-`--accent` | 通知开关 |
| **Checkbox** | w-4 h-4, rounded-sm, border `--border`, checked: bg-`--accent` ✓ | 协议勾选 |
| **Toast Item** | p-3 px-4, border-left 3px, `--shadow-md`, rounded-`--radius-sm`, slideIn 0.3s | 全局通知 |
| **Skeleton Block** | bg-`--bg-tertiary`, rounded, animate: pulse 1.5s infinite | 加载占位 |
| **Filter Tab/Pill** | px-3 py-1.5, rounded-full, active: bg-`--accent-light` text-`--accent` | 状态筛选 |
| **Accordion Item** | py-4, border-bottom `--border`, ChevronDown icon rotate transition | FAQ 折叠面板 |
| **Pagination** | Ghost button style, flex row gap-2, hover: underline | 分页导航 |

---

## 11. 响应式断点策略 (Responsive Breakpoints)

| 断点 | 宽度 | 布局调整 |
|------|------|---------|
| Desktop | ≥ 1024px | 标准布局，内容区 max-w 720px 居中 |
| Tablet | 768–1023px | 内容区 max-w 不变，两侧 padding 缩小至 24px |
| Mobile | < 768px | 内容区全宽 padding 16px；上传区高度缩至 160px；任务卡片堆叠；播放器简化（隐藏倍速）；对照页英文默认折叠（点击展开） |

---

## 12. 空状态与边界场景 (Empty & Edge States)

| 场景 | 视觉处理 |
|------|---------|
| 无历史任务 | 首页"最近翻译"区域显示空状态插画（极简线条风格）+ "还没有翻译记录，上传第一条播客开始体验" 文案 |
| 额度用尽 | 上传区域变为 disabled 态 + 覆盖半透明遮罩 + "额度已用完，升级解锁更多" + 升级按钮 |
| 网络断开 | Toast 提示 "网络连接已断开，正在尝试重连..." + 进度页自动切换为轮询模式 |
| 上传格式错误 | 上传区域边框变 `--error` + 下方红色提示文字 "不支持该格式，请上传 MP3/WAV/M4A 文件" |
| 翻译超时 | 进度页显示 "翻译时间超出预期，仍在处理中..." + 可选 "取消任务" 按钮 |

---

*规范结束。以上内容可直接作为 v0.dev / Bolt.new / Midjourney 等 AI 设计工具的输入源。*
