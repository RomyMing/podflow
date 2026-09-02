# 🎙️ PodCast Translator — 项目架构规范 (v1.0)

> **设计历史**：本文记录 PodFlow 早期架构规范，不再是公开快照的现行操作准则。当前架构以 [podcast_translator/ARCHITECTURE.md](podcast_translator/ARCHITECTURE.md) 和代码为准。
>
> 最后更新：2026-04-04 | 维护者：Chief Architect

---

## 目录

- [1. 项目总览](#1-项目总览)
- [2. 技术栈清单](#2-技术栈清单)
- [3. 项目目录结构](#3-项目目录结构)
- [4. 各组件职责与位置](#4-各组件职责与位置)
- [5. 命名约定](#5-命名约定)
- [6. 编码标准](#6-编码标准)
- [7. 禁区规则 — 绝不可修改](#7-禁区规则--绝不可修改)
- [8. 必须遵循的设计模式](#8-必须遵循的设计模式)
- [9. 路由决策树 — 常见工作流](#9-路由决策树--常见工作流)
- [10. Git 工作流与分支规范](#10-git-工作流与分支规范)
- [11. 环境与部署](#11-环境与部署)
- [12. 文档维护规则](#12-文档维护规则)

---

## 1. 项目总览

| 属性 | 值 |
|------|-----|
| 项目名称 | **PodCast Translator** |
| 项目定位 | 英文播客 → 中文播客的端到端 AI 翻译平台 |
| 核心链路 | 音源分离 → 说话人分段 → ASR → 翻译 → 声音克隆TTS → 时间对齐 → 混音输出 |
| 架构风格 | 模块化单体（Modular Monolith），预留微服务拆分接缝 |
| 主语言 | Python 3.12+ (后端 & AI Pipeline), TypeScript 5.x (前端) |
| 运行环境 | Linux (Ubuntu 22.04+), Docker, Kubernetes |

---

## 2. 技术栈清单

### 2.1 后端 & AI Pipeline

| 层次 | 技术 | 版本约束 | 用途 |
|------|------|----------|------|
| Web 框架 | FastAPI | ≥ 0.115 | REST API + WebSocket |
| 任务队列 | Celery | ≥ 5.4 | 异步 Pipeline 调度 |
| 消息代理 | Redis | ≥ 7.0 | Celery Broker + 缓存 + 进度推送 |
| 数据库 | PostgreSQL | ≥ 16 | 元数据、转录文本、译文 |
| ORM | SQLAlchemy | ≥ 2.0 | 数据库访问层 |
| 迁移工具 | Alembic | ≥ 1.13 | 数据库 Schema 迁移 |
| 对象存储 | MinIO (开发) / AWS S3 (生产) | — | 音频文件存储 |
| 音源分离 | Demucs v4 | ≥ 4.0 | 人声/背景分离 |
| 说话人分段 | pyannote.audio | ≥ 3.3 | Speaker Diarization |
| 语音识别 | Faster-Whisper | ≥ 1.1 (large-v3) | 英文 ASR |
| 翻译引擎 | OpenAI GPT-4o (主) / DeepSeek-V3 (备) | — | 上下文口语化翻译 |
| 声音克隆 | CosyVoice 2 (主) / Fish-Speech 1.5 (备) | — | 跨语言 Voice Cloning |
| 音频处理 | FFmpeg ≥ 6.0 + SoX + pydub | — | 音频编辑、混音、编码 |
| 认证 | PyJWT + python-jose | ≥ 2.8 | JWT Token 签发与验证 |
| 短信服务 | 阿里云 SMS / 腾讯云 SMS | — | 手机号短信验证码登录 |
| 微信登录 | 微信开放平台 OAuth 2.0 | — | 微信扫码/小程序登录 |

### 2.2 前端

| 技术 | 版本约束 | 用途 |
|------|----------|------|
| React | ≥ 19 | UI 框架 |
| Next.js | ≥ 15 | SSR + 路由 |
| TypeScript | ≥ 5.5 | 类型安全 |
| Tailwind CSS | ≥ 4.0 | 样式方案 |
| Zustand | ≥ 5.0 | 状态管理 |
| React Query | ≥ 5.0 | 服务端状态 |

### 2.3 基础设施

| 技术 | 用途 |
|------|------|
| Docker + Docker Compose | 本地开发环境 |
| Kubernetes + Helm | 生产部署 |
| KEDA | GPU Pod 弹性伸缩 |
| OpenTelemetry + Grafana | 可观测性 |
| GitHub Actions | CI/CD |

---

## 3. 项目目录结构

```
podcast_translator/
│
├── ARCHITECTURE.md              # ❌ 本文件 — 架构宪法（受保护）
├── README.md                    # 项目简介
├── LICENSE                      # ❌ 受保护
├── pyproject.toml               # ❌ Python 依赖声明（受保护）
├── docker-compose.yml           # 本地开发环境编排
├── Makefile                     # 常用命令入口
│
├── .github/
│   ├── workflows/
│   │   ├── ci.yml               # CI 流水线
│   │   └── deploy.yml           # CD 流水线
│   └── CODEOWNERS               # ❌ 代码归属（受保护）
│
├── deploy/                      # 部署配置
│   ├── helm/                    # Helm Charts
│   ├── k8s/                     # 原始 K8s manifests
│   └── dockerfiles/
│       ├── Dockerfile.api       # API 服务镜像
│       ├── Dockerfile.worker    # Celery Worker 镜像
│       └── Dockerfile.gpu       # GPU Worker 镜像
│
├── src/                         # ========== 后端源码根目录 ==========
│   ├── __init__.py
│   ├── main.py                  # FastAPI 应用入口
│   ├── config.py                # ❌ 全局配置加载（受保护结构）
│   ├── dependencies.py          # FastAPI 依赖注入
│   │
│   ├── api/                     # ---------- API 路由层 ----------
│   │   ├── __init__.py
│   │   ├── router.py            # 路由注册总入口
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── tasks.py         # /api/v1/tasks/**
│   │   │   ├── transcripts.py   # /api/v1/tasks/{id}/transcript
│   │   │   ├── auth.py          # /api/v1/auth/** (登录/注册/刷新Token)
│   │   │   └── health.py        # /api/v1/health
│   │   └── websocket/
│   │       └── progress.py      # ws://*/ws/tasks/{id}/progress
│   │
│   ├── schemas/                 # ---------- Pydantic 数据契约 ----------
│   │   ├── __init__.py
│   │   ├── task.py              # TaskCreate, TaskResponse, TaskStatus
│   │   ├── transcript.py        # TranscriptResponse, TranscriptUpdate
│   │   ├── auth.py              # SMSLoginRequest, WechatLoginRequest, TokenResponse
│   │   ├── user.py              # UserResponse, QuotaResponse
│   │   └── common.py            # 公共分页、错误响应
│   │
│   ├── models/                  # ---------- SQLAlchemy ORM 模型 ----------
│   │   ├── __init__.py
│   │   ├── base.py              # ❌ 声明 DeclarativeBase（受保护）
│   │   ├── task.py              # Task 模型
│   │   ├── user.py              # User 模型 (手机号/微信openid/配额)
│   │   ├── speaker.py           # Speaker 模型
│   │   └── segment.py           # Segment 模型
│   │
│   ├── repositories/            # ---------- 数据访问层 (Repository) ----------
│   │   ├── __init__.py
│   │   ├── base.py              # ❌ BaseRepository 抽象类（受保护）
│   │   ├── user_repo.py
│   │   ├── task_repo.py
│   │   ├── speaker_repo.py
│   │   └── segment_repo.py
│   │
│   ├── services/                # ---------- 业务逻辑层 ----------
│   │   ├── __init__.py
│   │   ├── auth_service.py      # 登录、Token 签发/刷新、微信 OAuth 编排
│   │   ├── quota_service.py     # 配额检查、扣减、重置
│   │   ├── task_service.py      # 任务创建、查询、生命周期
│   │   ├── transcript_service.py
│   │   └── storage_service.py   # S3/MinIO 操作封装
│   │
│   ├── pipeline/                # ---------- AI Pipeline 核心 ----------
│   │   ├── __init__.py
│   │   ├── context.py           # ❌ PipelineContext 定义（受保护）
│   │   ├── orchestrator.py      # Pipeline 编排引擎
│   │   ├── base_stage.py        # ❌ StageProcessor 抽象基类（受保护）
│   │   ├── stages/              # 各阶段实现
│   │   │   ├── __init__.py
│   │   │   ├── s1_source_separation.py
│   │   │   ├── s2_speaker_diarization.py
│   │   │   ├── s3_asr_transcription.py
│   │   │   ├── s4_translation.py
│   │   │   ├── s5_voice_clone_tts.py
│   │   │   ├── s6_temporal_alignment.py
│   │   │   └── s7_final_mixing.py
│   │   └── strategies/          # 策略模式 — 可插拔 AI 模型
│   │       ├── __init__.py
│   │       ├── asr/
│   │       │   ├── base.py      # ❌ ASRStrategy 接口（受保护）
│   │       │   ├── whisper.py
│   │       │   └── sensevoice.py
│   │       ├── translation/
│   │       │   ├── base.py      # ❌ TranslationStrategy 接口（受保护）
│   │       │   ├── openai_gpt.py
│   │       │   └── deepseek.py
│   │       ├── tts/
│   │       │   ├── base.py      # ❌ TTSStrategy 接口（受保护）
│   │       │   ├── cosyvoice.py
│   │       │   └── fish_speech.py
│   │       └── separation/
│   │           ├── base.py      # ❌ SeparationStrategy 接口（受保护）
│   │           └── demucs.py
│   │
│   ├── workers/                 # ---------- Celery 异步任务 ----------
│   │   ├── __init__.py
│   │   ├── celery_app.py        # ❌ Celery 实例化配置（受保护）
│   │   └── tasks.py             # 任务定义入口
│   │
│   ├── core/                    # ---------- 核心基础设施 ----------
│   │   ├── __init__.py
│   │   ├── database.py          # ❌ 数据库引擎/会话工厂（受保护）
│   │   ├── redis.py             # Redis 连接池
│   │   ├── logging.py           # 统一日志配置
│   │   ├── exceptions.py        # 自定义异常体系
│   │   ├── security.py          # JWT 认证/鉴权 (签发+验证 Token)
│   │   ├── sms.py               # 短信验证码服务 (阿里云/腾讯云)
│   │   └── wechat.py            # 微信 OAuth 2.0 封装
│   │
│   └── utils/                   # ---------- 工具函数 ----------
│       ├── __init__.py
│       ├── audio.py             # 音频处理工具 (ffmpeg, sox 封装)
│       ├── time_align.py        # 时间轴对齐算法
│       └── validators.py        # 自定义校验器
│
├── migrations/                  # Alembic 数据库迁移
│   ├── env.py                   # ❌ Alembic 环境配置（受保护）
│   ├── alembic.ini
│   └── versions/                # 迁移版本文件
│
├── tests/                       # ========== 测试 ==========
│   ├── conftest.py              # Pytest fixtures
│   ├── unit/
│   │   ├── test_services/
│   │   ├── test_pipeline/
│   │   └── test_utils/
│   ├── integration/
│   │   ├── test_api/
│   │   └── test_workers/
│   └── e2e/
│       └── test_full_pipeline.py
│
├── frontend/                    # ========== 前端源码 ==========
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── src/
│   │   ├── app/                 # Next.js App Router
│   │   │   ├── layout.tsx       # ❌ 根布局（受保护结构）
│   │   │   ├── page.tsx
│   │   │   ├── tasks/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx
│   │   │   └── api/             # BFF 代理层 (如需要)
│   │   ├── components/
│   │   │   ├── ui/              # 基础 UI 组件 (Button, Modal...)
│   │   │   ├── upload/          # 上传相关组件
│   │   │   ├── player/          # 音频播放器
│   │   │   └── transcript/      # 转录文本展示/编辑
│   │   ├── hooks/               # 自定义 Hooks
│   │   ├── stores/              # Zustand stores
│   │   ├── services/            # API 调用封装
│   │   │   └── api-client.ts    # ❌ Axios/Fetch 实例（受保护）
│   │   ├── types/               # TypeScript 类型定义
│   │   └── lib/                 # 工具函数
│   └── public/                  # 静态资源
│
└── scripts/                     # 运维脚本
    ├── seed_db.py               # 初始化数据
    ├── benchmark_tts.py         # TTS 性能基准测试
    └── cleanup_s3.py            # S3 过期文件清理
```

---

## 4. 各组件职责与位置

### 4.1 后端分层架构

各层之间的依赖关系**必须单向向下**，严禁反向依赖或跨层调用。

```
┌──────────────────────────────────────────────┐
│                  API 路由层                    │  src/api/
│        (HTTP/WS 入口, 参数校验, 响应格式化)     │
├──────────────────────────────────────────────┤
│                  数据契约层                    │  src/schemas/
│            (Pydantic Request/Response)        │
├──────────────────────────────────────────────┤
│                  业务逻辑层                    │  src/services/
│           (编排业务流程, 无数据库直接操作)       │
├──────────────────────────────────────────────┤
│               AI Pipeline 层                  │  src/pipeline/
│         (7 阶段处理器 + 策略模式模型封装)       │
├──────────────────────────────────────────────┤
│                  数据访问层                    │  src/repositories/
│          (SQLAlchemy 查询, 数据库唯一出口)      │
├──────────────────────────────────────────────┤
│                  ORM 模型层                    │  src/models/
│            (表结构定义, 无业务逻辑)             │
├──────────────────────────────────────────────┤
│                 核心基础设施                   │  src/core/
│         (DB引擎, Redis, 日志, 异常, 安全)      │
└──────────────────────────────────────────────┘
```

**强制规则：**

| 规则 | 说明 |
|------|------|
| `api/` 只能调用 `services/` 和 `schemas/` | 路由层禁止直接操作数据库或调用 Pipeline |
| `services/` 只能调用 `repositories/` 和 `pipeline/` | 业务层禁止直接写 SQL |
| `repositories/` 只能调用 `models/` 和 `core/database` | 数据访问层禁止包含业务逻辑 |
| `pipeline/stages/` 只能调用 `strategies/` 和 `utils/` | 阶段处理器禁止直接实例化具体 AI 模型 |
| `models/` 零依赖 | ORM 模型禁止 import 上层任何模块 |

### 4.2 文件归属快速查找表

> **当你不确定代码应该放在哪里时，查阅此表。**

| 我要写的东西 | 放在哪里 | 文件命名 |
|-------------|---------|---------|
| 新的 REST API 端点 | `src/api/v1/` | `{resource_name}.py` |
| WebSocket 端点 | `src/api/websocket/` | `{feature}.py` |
| 请求/响应数据结构 | `src/schemas/` | `{resource_name}.py` |
| 数据库表模型 | `src/models/` | `{table_name_singular}.py` |
| 数据库查询方法 | `src/repositories/` | `{table_name}_repo.py` |
| 业务编排逻辑 | `src/services/` | `{domain}_service.py` |
| 新的 Pipeline 阶段 | `src/pipeline/stages/` | `s{N}_{stage_name}.py` |
| 新的 AI 模型接入 | `src/pipeline/strategies/{category}/` | `{model_name}.py` |
| Celery 异步任务 | `src/workers/tasks.py` | 追加到已有文件 |
| 数据库迁移 | `migrations/versions/` | Alembic 自动生成 |
| 工具函数 | `src/utils/` | `{domain}.py` |
| 自定义异常 | `src/core/exceptions.py` | 追加到已有文件 |
| 环境配置项 | `src/config.py` | 追加到已有文件 |
| 前端页面 | `frontend/src/app/` | Next.js App Router 约定 |
| 前端组件 | `frontend/src/components/{category}/` | `PascalCase.tsx` |
| 前端 API 调用 | `frontend/src/services/` | `{resource}.ts` |
| 前端类型定义 | `frontend/src/types/` | `{domain}.ts` |
| 认证逻辑（JWT/Token） | `src/core/security.py` | 追加到已有文件 |
| 短信验证码 | `src/core/sms.py` | 追加到已有文件 |
| 微信 OAuth | `src/core/wechat.py` | 追加到已有文件 |
| 配额管理逻辑 | `src/services/quota_service.py` | 追加到已有文件 |

---

## 5. 命名约定

### 5.1 Python 后端

```python
# ── 文件名 ──────────────────────────────
# 全部 snake_case，简洁有意义
task_service.py          # ✅
TaskService.py           # ❌
task-service.py          # ❌
svc_task.py              # ❌

# ── 类名 ────────────────────────────────
# PascalCase，后缀表明角色
class TaskService:           # Service 层
class TaskRepository:        # Repository 层
class TaskResponse:          # Schema (Pydantic)
class Task:                  # ORM Model
class ASRStage:              # Pipeline Stage
class WhisperStrategy:       # Strategy 实现
class AudioProcessingError:  # 异常类,以 Error 结尾

# ── 函数/方法名 ─────────────────────────
# snake_case，动词开头
def create_task():           # ✅
def get_task_by_id():        # ✅
def createTask():            # ❌ 禁止 camelCase

# ── 常量 ────────────────────────────────
# SCREAMING_SNAKE_CASE
MAX_AUDIO_DURATION_SECONDS = 7200
DEFAULT_OUTPUT_FORMAT = "mp3"

# ── 私有成员 ─────────────────────────────
# 单下划线前缀
def _validate_audio_format():  # 模块/类内部使用
_internal_cache = {}

# ── Pipeline Stage 文件名 ────────────────
# 固定前缀 s{阶段编号}_ + 描述性名称
s1_source_separation.py      # ✅
s2_speaker_diarization.py    # ✅
source_separation.py         # ❌ 缺少阶段编号

# ── 环境变量 ─────────────────────────────
# 统一前缀 PCT_ (PodCast Translator)
PCT_DATABASE_URL=postgresql://...
PCT_REDIS_URL=redis://...
PCT_S3_BUCKET=podcast-translator-audio
PCT_OPENAI_API_KEY=sk-...
PCT_GPU_WORKER_CONCURRENCY=2
```

### 5.2 TypeScript 前端

```typescript
// ── 文件名 ──────────────────────────────
// 组件: PascalCase.tsx
// 其他: camelCase.ts
AudioUploader.tsx          // ✅ React 组件
useTaskProgress.ts         // ✅ Hook (use 前缀)
taskService.ts             // ✅ Service
audio-uploader.tsx         // ❌ 禁止 kebab-case

// ── 组件命名 ─────────────────────────────
// PascalCase, 名词或名词短语
export function AudioUploader() {}    // ✅
export function TranscriptEditor() {} // ✅

// ── Hook 命名 ────────────────────────────
// use 前缀 + PascalCase 描述
export function useTaskProgress() {}  // ✅
export function useAudioPlayer() {}   // ✅

// ── 类型/接口 ────────────────────────────
// PascalCase, 不加 I 前缀
interface TaskResponse {}    // ✅
interface ITaskResponse {}   // ❌ 禁止 I 前缀
type TaskStatus = "pending" | "processing" | "completed" | "failed";

// ── Zustand Store ────────────────────────
// use + 名词 + Store
export const useTaskStore = create<TaskState>()(...);
```

### 5.3 数据库

```sql
-- 表名: snake_case 复数
CREATE TABLE tasks (...);
CREATE TABLE speakers (...);
CREATE TABLE segments (...);

-- 列名: snake_case
task_id, created_at, source_audio_url

-- 索引名: ix_{表}_{列}
CREATE INDEX ix_segments_task_id ON segments(task_id);

-- 外键名: fk_{子表}_{父表}
CONSTRAINT fk_segments_tasks FOREIGN KEY (task_id) REFERENCES tasks(id)

-- 枚举值: snake_case
'source_separation', 'voice_clone_tts', 'completed', 'failed'
```

### 5.4 API 端点

```
# RESTful 风格, 复数名词, 全小写, kebab-case
POST   /api/v1/tasks                    # ✅
GET    /api/v1/tasks/{task_id}           # ✅
GET    /api/v1/tasks/{task_id}/transcript # ✅

# 认证端点
POST   /api/v1/auth/sms/send            # ✅ 发送短信验证码
POST   /api/v1/auth/sms/login           # ✅ 手机号+验证码登录
POST   /api/v1/auth/wechat/login        # ✅ 微信 OAuth 登录 (code 换 token)
POST   /api/v1/auth/refresh             # ✅ 刷新 Access Token
POST   /api/v1/auth/logout              # ✅ 登出 (作废 Refresh Token)
GET    /api/v1/users/me                  # ✅ 获取当前用户信息

# 版本号始终保留
/api/v1/...                             # ✅
/api/tasks/...                          # ❌ 缺少版本号

# WebSocket
/ws/tasks/{task_id}/progress            # ✅
```

---

## 6. 编码标准

### 6.1 Python 强制规则

| 编号 | 规则 | 说明 |
|------|------|------|
| PY-01 | 所有函数必须有 Type Hints | 参数和返回值均需标注类型 |
| PY-02 | 所有 API 端点使用 Pydantic Schema | 禁止裸 dict 作为请求/响应 |
| PY-03 | 异步优先 | API 层和 I/O 操作使用 `async/await` |
| PY-04 | ORM 模型禁止业务逻辑 | Model 类只定义字段和关系，不写方法 |
| PY-05 | 每个 Strategy 实现必须继承对应 Base | 禁止绕过接口直接使用 AI 模型 |
| PY-06 | Docstring 必须 | 所有 public class/function 必须有 Google 风格 Docstring |
| PY-07 | 日志使用 structlog | 禁止 `print()` 或裸 `logging` |
| PY-08 | 硬编码零容忍 | 所有配置项通过 `src/config.py` 读取环境变量 |
| PY-09 | SQL 注入防护 | 禁止字符串拼接 SQL，只用 SQLAlchemy ORM/Core |
| PY-10 | 单文件不超过 400 行 | 超出则拆分 |

```python
# ✅ 正确示范
async def create_task(
    self,
    audio_file: UploadFile,
    config: TaskCreateRequest,
) -> TaskResponse:
    """创建播客翻译任务。

    Args:
        audio_file: 用户上传的英文播客音频文件。
        config: 任务配置（输出格式、目标语言等）。

    Returns:
        创建成功的任务信息。

    Raises:
        AudioFormatError: 音频格式不支持。
        AudioTooLongError: 音频超过最大时长限制。
    """
    ...

# ❌ 错误示范
def create_task(audio_file, config):
    # 没有 type hints, 没有 docstring, 没有 async
    ...
```

### 6.2 TypeScript 强制规则

| 编号 | 规则 | 说明 |
|------|------|------|
| TS-01 | strict 模式 | `tsconfig.json` 中 `strict: true`，不可关闭 |
| TS-02 | 禁止 `any` | 使用 `unknown` + 类型守卫替代 |
| TS-03 | 组件 Props 必须定义 interface | 禁止 inline 类型 |
| TS-04 | 服务端状态用 React Query | 禁止 useEffect + useState 手动管理 |
| TS-05 | 客户端状态用 Zustand | 禁止 Context 全局状态 |
| TS-06 | 所有 API 调用集中在 `services/` | 组件内禁止直接 fetch |

### 6.3 通用规则

| 编号 | 规则 | 说明 |
|------|------|------|
| GEN-01 | 提交前必须通过 lint + format | Python: ruff; TS: eslint + prettier |
| GEN-02 | 新功能必须附带测试 | Service 层 ≥ 80% 覆盖率, Pipeline Stage ≥ 90% |
| GEN-03 | 敏感信息禁止入库 | API Key、密码等只在环境变量中存在 |
| GEN-04 | 错误信息用户友好 | API 返回的 error message 面向终端用户 |
| GEN-05 | 所有音频操作必须校验格式 | 入口处校验 MIME type + magic bytes |

### 6.4 错误处理与重试策略

| 场景 | 策略 | 参数 |
|------|------|------|
| Pipeline 阶段失败 | Celery 自动重试，指数退避 | `max_retries=3`, `retry_backoff=True`, 初始间隔 60s |
| 外部 API 调用（LLM/TTS） | 指数退避 + 降级策略 | 3 次重试后切换备选模型（如 GPT-4o → DeepSeek） |
| 文件上传中断 | 断点续传 | 分片上传，5MB/片 |
| WebSocket 断连 | 客户端自动重连 + HTTP 轮询兜底 | 重连间隔 1s/2s/4s，最大 30s |
| 3 次重试仍失败 | 标记任务失败 + 不扣用户配额 | 记录错误日志，通知用户可重试 |
| 短信验证码发送失败 | 最多重试 2 次，间隔 5s | 同一手机号 60s 内只允许发送 1 次 |

---

## 7. 禁区规则 — 绝不可修改

### 7.1 受保护文件清单（Protected Files）

> ⛔ 以下文件未经 **Chief Architect 书面批准**，**任何人/任何 Agent** 不得修改。

| 文件路径 | 保护理由 |
|----------|---------|
| `ARCHITECTURE.md` | 项目宪法，修改需全员 Review |
| `pyproject.toml` | 依赖变更影响全局，需安全审计 |
| `LICENSE` | 法律文件 |
| `.github/CODEOWNERS` | 代码归属权 |
| `src/config.py` | 配置结构变更影响所有环境 |
| `src/models/base.py` | ORM Base 类，变更影响所有模型 |
| `src/repositories/base.py` | Repository 基类，变更影响所有数据访问 |
| `src/pipeline/context.py` | Pipeline 上下文定义，变更影响所有阶段 |
| `src/pipeline/base_stage.py` | 阶段抽象基类，变更影响所有处理器 |
| `src/pipeline/strategies/*/base.py` | 策略接口定义，变更影响所有实现 |
| `src/core/database.py` | 数据库引擎配置 |
| `src/workers/celery_app.py` | Celery 实例化配置 |
| `migrations/env.py` | Alembic 环境配置 |
| `frontend/src/app/layout.tsx` | 根布局结构 |
| `frontend/src/services/api-client.ts` | HTTP 客户端基础配置 |

### 7.2 受保护模式（Protected Patterns）

> ⛔ 以下设计模式是架构基石，不得违反或绕过：

| 编号 | 受保护模式 | 违规示例 |
|------|-----------|---------|
| PAT-01 | **分层单向依赖**：api → services → repositories → models | 在 `api/` 中直接 import `models/` |
| PAT-02 | **策略模式封装 AI 模型**：所有 AI 模型必须通过 Strategy 接口调用 | 在 Stage 中直接 `import whisper` |
| PAT-03 | **Pipeline Context 是唯一的阶段间通信载体** | 阶段之间通过全局变量或数据库传递中间状态 |
| PAT-04 | **Repository 是数据库唯一出口** | 在 Service 中直接写 `session.query(...)` |
| PAT-05 | **所有异步任务通过 Celery 调度** | 在 API 层用 `threading` 启后台任务 |
| PAT-06 | **所有文件存储通过 StorageService** | 直接调用 boto3/minio SDK |
| PAT-07 | **全局异常处理在 API 层统一捕获** | 在每个端点里写 try/except 返回错误 |

### 7.3 受保护接口签名

> 以下接口签名已经固化，仅可**扩展可选参数**，禁止修改已有参数的名称、类型或顺序。

```python
# ❌ 禁止修改的方法签名

# StageProcessor 基类 — 模板方法 + 责任链
class StageProcessor(ABC):
    def __init__(self, next_processor: 'StageProcessor' = None):
        self._next = next_processor

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        """模板方法：状态更新 → process → 进度上报 → 传递下一阶段（禁止覆写）"""
        ...

    @abstractmethod
    def process(self, ctx: PipelineContext) -> PipelineContext:
        """子类实现的核心处理逻辑"""
        ...

    @property
    @abstractmethod
    def stage(self) -> TaskStage:
        """返回当前阶段枚举值"""
        ...

# Strategy 接口
class ASRStrategy(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str, language: str) -> TranscriptionResult: ...

class TranslationStrategy(ABC):
    @abstractmethod
    async def translate(self, segments: list[TextSegment], context: str) -> list[str]: ...

class TTSStrategy(ABC):
    @abstractmethod
    async def synthesize(self, text: str, reference_audio: str, speaker_embedding: bytes) -> bytes: ...

class SeparationStrategy(ABC):
    @abstractmethod
    async def separate(self, audio_path: str) -> SeparationResult: ...
```

---

## 8. 必须遵循的设计模式

### 8.1 策略模式 — AI 模型可插拔

```
src/pipeline/strategies/tts/
├── base.py              # TTSStrategy (ABC)     ← 受保护
├── cosyvoice.py         # CosyVoiceStrategy     ← 可修改/替换
└── fish_speech.py       # FishSpeechStrategy    ← 可修改/替换
```

**添加新模型的标准步骤：**

1. 在对应 `strategies/{category}/` 下创建新文件
2. 继承 `base.py` 中的抽象类
3. 实现所有抽象方法
4. 在 `src/config.py` 中注册模型标识符
5. 编写单元测试 (`tests/unit/test_pipeline/test_strategies/`)
6. **绝不修改 `base.py`**

### 8.2 责任链模式 — Pipeline 编排

```python
# 标准的 Pipeline 组装方式（在 orchestrator.py 中）
# 新增阶段：在链中插入新 Stage 即可，无需修改已有 Stage
pipeline = (
    SourceSeparationStage()
    >> SpeakerDiarizationStage()
    >> ASRStage()
    >> TranslationStage()
    >> VoiceCloneTTSStage()
    >> TemporalAlignmentStage()
    >> FinalMixingStage()
)
```

### 8.3 Repository 模式 — 数据访问

```python
# 所有 Repository 必须继承 BaseRepository
class TaskRepository(BaseRepository[Task]):
    # 可添加自定义查询方法
    async def find_by_status(self, status: TaskStage) -> list[Task]: ...
    # 基础 CRUD 由 BaseRepository 提供: get, list, create, update, delete
```

### 8.4 依赖注入 — FastAPI

```python
# src/dependencies.py 中统一注册
# 禁止在路由函数内手动实例化 Service/Repository

async def get_task_service(
    db: AsyncSession = Depends(get_db_session),
    storage: StorageService = Depends(get_storage_service),
) -> TaskService:
    repo = TaskRepository(db)
    return TaskService(repo, storage)
```

---

## 9. 路由决策树 — 常见工作流

### 9.1 🆕 添加新的 API 端点

```
开始
 │
 ├─ 是否属于现有资源 (tasks, transcripts)?
 │   ├─ 是 → 在对应的 src/api/v1/{resource}.py 中添加
 │   └─ 否 → 创建 src/api/v1/{new_resource}.py
 │            并在 src/api/router.py 中注册
 │
 ├─ 定义 Request/Response Schema
 │   └─ 在 src/schemas/{resource}.py 中添加 Pydantic Model
 │
 ├─ 需要新的业务逻辑？
 │   ├─ 是 → 在 src/services/{domain}_service.py 中实现
 │   └─ 否 → 复用已有 Service 方法
 │
 ├─ 需要新的数据库查询？
 │   ├─ 是 → 在 src/repositories/{table}_repo.py 中添加方法
 │   └─ 否 → 使用 BaseRepository 内置方法
 │
 ├─ 需要新的数据库表/字段？
 │   ├─ 新表 → 创建 src/models/{table}.py + Alembic migration
 │   └─ 新字段 → 修改对应 Model + Alembic migration
 │       ⚠️ 禁止修改 src/models/base.py
 │
 └─ 编写测试
     └─ tests/unit/test_services/ + tests/integration/test_api/
```

### 9.2 🤖 接入新的 AI 模型

```
开始
 │
 ├─ 确定模型类别: ASR / Translation / TTS / Separation
 │
 ├─ 在 src/pipeline/strategies/{category}/ 下创建 {model_name}.py
 │   └─ 必须继承 {category}/base.py 中的抽象基类
 │   └─ ⚠️ 禁止修改 base.py
 │
 ├─ 实现所有抽象方法，保持签名一致
 │
 ├─ 在 src/config.py 中添加模型配置项（使用环境变量）
 │   └─ 环境变量命名: PCT_{CATEGORY}_{MODEL}_*
 │       例: PCT_TTS_COSYVOICE_ENDPOINT
 │
 ├─ 在对应的 Stage 中通过配置选择策略实例
 │   └─ ⚠️ 禁止在 Stage 中硬编码模型选择
 │
 ├─ 编写测试
 │   ├─ 单元测试: tests/unit/test_pipeline/test_strategies/
 │   └─ 集成测试: 使用 mock 或真实模型（标记 @pytest.mark.gpu）
 │
 └─ 如果模型需要 GPU
     └─ 在 deploy/dockerfiles/Dockerfile.gpu 中添加依赖
```

### 9.3 🗃️ 修改数据库 Schema

```
开始
 │
 ├─ 是新增表？
 │   ├─ 是 → 创建 src/models/{table_name}.py
 │   │       创建 src/repositories/{table_name}_repo.py
 │   │       ⚠️ 继承 BaseRepository
 │   └─ 否 → 修改已有 src/models/{table_name}.py
 │
 ├─ ⚠️ 禁止修改 src/models/base.py
 │
 ├─ 是否影响 PipelineContext？
 │   ├─ 是 → ⛔ 停止！需要 Chief Architect 审批
 │   └─ 否 → 继续
 │
 ├─ 生成 Alembic 迁移
 │   └─ alembic revision --autogenerate -m "描述性消息"
 │
 ├─ Review 生成的迁移文件
 │   └─ 确认无数据丢失风险
 │
 ├─ 更新对应的 Pydantic Schema (src/schemas/)
 │
 └─ 更新测试 fixtures (tests/conftest.py)
```

### 9.4 🐛 修复 Bug

```
开始
 │
 ├─ 定位 Bug 所在层次
 │   ├─ API 层 (请求/响应问题) → src/api/
 │   ├─ 业务逻辑 (流程错误)   → src/services/
 │   ├─ Pipeline (AI处理问题) → src/pipeline/
 │   ├─ 数据层 (查询/存储问题) → src/repositories/
 │   └─ 基础设施 (连接/配置)   → src/core/
 │
 ├─ Bug 是否涉及受保护文件？
 │   ├─ 是 → ⛔ 提交 Architect Review Request
 │   │        不得自行修改
 │   └─ 否 → 继续
 │
 ├─ 先写失败的测试用例（TDD）
 │   └─ 放在对应的 tests/ 目录
 │
 ├─ 修复代码
 │   └─ 修复范围必须最小化，禁止"顺手重构"
 │
 └─ 验证测试通过 + 回归测试无影响
```

### 9.5 ⚡ 性能优化

```
开始
 │
 ├─ 瓶颈在哪个 Pipeline Stage？
 │   ├─ 音源分离     → 考虑模型量化 or 分段并行处理
 │   ├─ ASR          → 使用 batched decode, 长音频分 chunk
 │   ├─ 翻译         → 增大滑动窗口, 减少 LLM 调用次数
 │   ├─ 声音克隆 TTS → ⭐最大瓶颈
 │   │   ├─ 不同 Speaker 并行合成
 │   │   ├─ 模型量化 FP16 → INT8
 │   │   └─ 增加 GPU Worker 实例
 │   └─ 混音         → FFmpeg 参数优化, 流式处理
 │
 ├─ 是否需要修改 Pipeline 接口？
 │   ├─ 是 → ⛔ 停止！需要 Architect 审批
 │   └─ 否 → 在具体 Stage/Strategy 内部优化
 │
 └─ 性能优化必须附带 Benchmark
     └─ 使用 scripts/benchmark_tts.py 等基准脚本
```

### 9.6 🚀 前端需求变更

```
开始
 │
 ├─ 是 UI 变更还是数据变更？
 │   ├─ 纯 UI → 修改 frontend/src/components/
 │   │   ├─ 通用组件 → components/ui/
 │   │   └─ 业务组件 → components/{feature}/
 │   │
 │   └─ 涉及数据 →
 │       ├─ 需要新 API？ → 先完成后端 (参考 9.1)
 │       ├─ API 调用 → frontend/src/services/
 │       │   ⚠️ 禁止修改 api-client.ts 基础配置
 │       ├─ 服务端状态 → React Query hook in frontend/src/hooks/
 │       └─ 客户端状态 → Zustand store in frontend/src/stores/
 │
 ├─ 需要新的页面路由？
 │   └─ 在 frontend/src/app/ 下按 Next.js 约定创建
 │       ⚠️ 禁止修改 layout.tsx 根结构
 │
 └─ 编写测试
```

---

## 10. Git 工作流与分支规范

### 10.1 分支命名

```
main              # 生产分支，受保护，仅 MR 合入
develop           # 开发主干
feature/PCT-{N}-{短描述}    # 功能分支    例: feature/PCT-42-add-fish-speech
bugfix/PCT-{N}-{短描述}     # 修复分支    例: bugfix/PCT-87-tts-timeout
hotfix/PCT-{N}-{短描述}     # 紧急修复    例: hotfix/PCT-99-s3-connection
refactor/PCT-{N}-{短描述}   # 重构分支
```

### 10.2 Commit 规范

```
# 格式: <type>(scope): <description>
# type: feat | fix | refactor | docs | test | chore | perf

feat(pipeline): add Fish-Speech TTS strategy
fix(api): handle audio upload timeout for files > 500MB
refactor(services): extract audio validation to shared util
docs(architecture): update protected files list
test(pipeline): add unit tests for temporal alignment
perf(tts): enable batched synthesis for CosyVoice
chore(deps): bump faster-whisper to 1.2.0
```

### 10.3 Merge Request 规则

| 目标分支 | 最少 Reviewer 数 | 必须包含 |
|----------|-----------------|----------|
| `main` | 2 (含 Architect) | 全部 CI 绿 + Changelog |
| `develop` | 1 | 全部 CI 绿 |
| 涉及受保护文件 | **Architect 独占审批** | 架构影响说明 |

---

## 11. 环境与部署

### 11.1 环境分级

| 环境 | 用途 | GPU | 数据 |
|------|------|-----|------|
| `local` | 开发者本机 (Docker Compose) | 可选 (CPU 模式) | 种子数据 |
| `staging` | 集成测试 | 1 × A10G | 脱敏测试数据 |
| `production` | 生产环境 | N × A100 (弹性) | 真实用户数据 |

### 11.2 环境变量要求

所有环境变量必须在 `src/config.py` 中声明，包含：
- 类型注解
- 默认值 (仅 local 允许默认值)
- 校验规则
- 注释说明

```python
class Settings(BaseSettings):
    # ── Database ──
    PCT_DATABASE_URL: PostgresDsn          # 无默认值, 必须显式配置
    PCT_DATABASE_POOL_SIZE: int = 10

    # ── Redis ──
    PCT_REDIS_URL: RedisDsn

    # ── S3 ──
    PCT_S3_ENDPOINT: str
    PCT_S3_BUCKET: str = "podcast-translator-audio"

    # ── AI Models ──
    PCT_ASR_PROVIDER: Literal["whisper", "sensevoice"] = "whisper"
    PCT_TTS_PROVIDER: Literal["cosyvoice", "fish_speech"] = "cosyvoice"
    PCT_TRANSLATION_PROVIDER: Literal["openai", "deepseek"] = "openai"
    PCT_OPENAI_API_KEY: SecretStr          # 敏感信息
```

---

## 12. 文档维护规则

| 规则 | 说明 |
|------|------|
| 本文件修改需要 Architect + 至少 1 位 Tech Lead 同时批准 | 双人审批制 |
| API 端点变更必须同步更新 OpenAPI Schema | FastAPI 自动生成，但需检查 |
| 新增 Pipeline Stage 必须更新本文件第 3 节目录结构 | 保持目录树准确 |
| 新增受保护文件必须更新第 7.1 节清单 | 保持禁区清单完整 |
| 每季度 Review 一次技术栈版本 | 确保依赖不过时 |

---

> **⚠️ 最终声明：本文件内所有标注 ❌ 或 ⛔ 的规则无例外条款。如遇特殊情况确需突破，必须发起 Architecture Decision Record (ADR) 并经团队全员 Review 通过后方可执行。**
