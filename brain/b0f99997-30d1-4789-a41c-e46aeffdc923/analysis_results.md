# 🎙️ 三份项目文件一致性分析报告（已更新）

## 一、文件概览

| 文件 | 定位 | 核心内容 |
|------|------|----------|
| [PROJECT_PRD.md](../../PROJECT_PRD.md) | **产品需求文档 (PRD)** | 市场背景、用户画像、功能列表、页面设计、数据埋点、成功指标、MVP 范围 |
| [PROJECT_SAD.md](../../PROJECT_SAD.md) | **系统架构设计 (SAD)** | 技术挑战、顶层架构、数据流、存储选型、数据模型、核心伪代码、AI 模型选型、成本估算 |
| [PROJECT_ADS.md](../../PROJECT_ADS.md) | **架构开发规范 (ADS)** | 技术栈清单、目录结构、分层架构、命名约定、编码标准、保护规则、设计模式、Git 工作流 |

---

## 二、一致性分析

### ✅ 已修复的差异

| 维度 | 修复内容 | 涉及文件 |
|------|----------|----------|
| **产品名称** | 统一为 **PodCast Translator** | ADS ✅ |
| **环境变量前缀** | 统一为 `PCT_` | ADS ✅ |
| **Git 分支前缀** | 统一为 `PCT-{N}` | ADS ✅ |
| **S3 Bucket 名称** | 统一为 `podcast-translator-audio` | ADS ✅ |
| **MVP 多说话人范围** | 统一为支持**单/双人播客**，说话人分段移入 Phase 1 | SAD ✅ |
| **认证方案** | 统一为**手机号（短信验证码）+ 微信登录**，JWT Token | PRD + SAD + ADS ✅ |
| **StageProcessor 接口** | ADS 扩展为完整定义（`process` 抽象方法 + `execute` 模板方法 + `stage` 属性），与 SAD 一致 | ADS ✅ |
| **Pipeline 阶段映射** | PRD 进度页面注明用户侧 5 步与技术侧 7 阶段的映射关系 | PRD ✅ |
| **User 数据模型** | SAD 数据模型补充 USER 表（手机号、微信openid、配额）+ Task 增加 user_id | SAD ✅ |
| **配额管理** | ADS 补充 `quota_service.py`、PRD 已有配额描述、SAD 补充 User 模型字段 | SAD + ADS ✅ |
| **认证 API 端点** | SAD 和 ADS 均补充认证相关 API 端点（6个） | SAD + ADS ✅ |
| **目录结构补全** | ADS 补充 `auth.py`(API)、`user.py`(模型)、`auth.py`/`user.py`(Schema)、`user_repo.py`(Repo)、`auth_service.py`/`quota_service.py`(Service)、`sms.py`/`wechat.py`(Core) | ADS ✅ |
| **错误重试策略** | ADS 新增 §6.4 错误处理与重试策略表 | ADS ✅ |
| **文件归属表** | ADS 补充认证/配额相关文件归属 | ADS ✅ |

### ✅ 无需修改的差异（合理的文档分层差异）

| 维度 | 说明 |
|------|------|
| **前端样式方案** | ADS 明确 Tailwind CSS ≥ 4.0，PRD 无需提及（技术细节归 ADS 管） |
| **状态管理** | ADS 明确 Zustand + React Query，PRD 无需提及 |
| **PipelineContext 定义** | SAD 有伪代码，ADS 标注为受保护文件路径，实现时以 SAD 为参考 |
| **分阶段计划** | SAD 有 Gantt 图，PRD 有三期目标但无具体排期，以 SAD 为准 |

### 📋 用于开发阶段补充的事项（非文档不一致）

| 事项 | 说明 | 优先级 |
|------|------|--------|
| Docker Compose 配置 | ADS 提到但未给出具体配置，开发启动时创建 | Phase 0 |
| 初始数据库迁移 | Alembic 初始 migration，开发启动时生成 | Phase 0 |
| 前端组件详细设计 | PRD 有线框图，开发时拆分组件 | Phase 1 |
| CI/CD 流水线 | GitHub Actions 配置，可后期补充 | Phase 2+ |

---

## 三、总体评价

> [!TIP]
> 三份文档在**核心需求、技术选型、架构设计**上完全一致，所有差异均已修复。

文档之间的关系清晰：
- **PRD** 回答"做什么、为谁做、怎么衡量成功"
- **SAD** 回答"怎么做、用什么技术、数据怎么流转"
- **ADS** 回答"怎么组织代码、遵循什么规范、什么不能动"

---

## 四、接下来的执行步骤

> [!IMPORTANT]
> 所有文档差异已修复，可以直接进入开发阶段。

### Phase 0：项目初始化（预计 1-2 天）

- [ ] **1. 初始化项目骨架**：按 ADS 的 `podcast_translator/` 目录结构创建完整骨架
  - 后端 Python 项目 (`pyproject.toml`, `src/` 结构)
  - 前端 Next.js 项目 (`frontend/`)
  - Docker Compose 开发环境 (PostgreSQL + Redis + MinIO)
  - Makefile 常用命令
- [ ] **2. 创建受保护的基础文件**：
  - `src/models/base.py` — DeclarativeBase
  - `src/repositories/base.py` — BaseRepository 抽象类
  - `src/pipeline/context.py` — PipelineContext（参考 SAD 伪代码）
  - `src/pipeline/base_stage.py` — StageProcessor 抽象基类（含 execute 模板方法）
  - `src/pipeline/strategies/*/base.py` — 各 Strategy 接口
  - `src/core/database.py` — 数据库引擎配置
  - `src/core/security.py` — JWT 签发/验证
  - `src/config.py` — Settings 类（PCT_ 前缀环境变量）
  - `src/workers/celery_app.py` — Celery 实例
- [ ] **3. 创建数据模型 + 初始迁移**：User、Task、Speaker、Segment 四张表

### Phase 1 MVP 开发（预计 5-6 周，含双人播客）

#### 用户体系（Week 1）
- [ ] **4. 实现认证 API**：短信验证码登录 + 微信 OAuth 登录 + JWT Token
- [ ] **5. 实现配额管理**：配额检查、扣减、月重置

#### 后端核心（Week 1-2）
- [ ] **6. 实现 Task API**：`POST /api/v1/tasks`、`GET /api/v1/tasks/{id}` 等
- [ ] **7. 实现 Storage Service**（MinIO/S3 封装）
- [ ] **8. 实现 WebSocket 进度推送**

#### AI Pipeline（Week 2-4）
- [ ] **9. 实现音源分离 Stage**（Demucs v4）
- [ ] **10. 实现说话人分段 Stage**（pyannote.audio，支持双人）
- [ ] **11. 实现 ASR Stage**（Faster-Whisper）
- [ ] **12. 实现翻译 Stage**（GPT-4o + DeepSeek 降级）
- [ ] **13. 实现声音克隆 TTS Stage**（CosyVoice 2）
- [ ] **14. 实现时间轴对齐 Stage**
- [ ] **15. 实现混音输出 Stage**（FFmpeg）
- [ ] **16. 实现 Pipeline Orchestrator** 串联所有 Stage

#### 前端（Week 1-3，与后端并行）
- [ ] **17. 搭建 Next.js 项目基础**（App Router + Tailwind 4 + Zustand + React Query）
- [ ] **18. 实现登录页面**（手机号+微信）
- [ ] **19. 实现首页/上传页**（文件上传 + URL 输入 + 配额展示）
- [ ] **20. 实现任务详情/进度页**（WebSocket 实时进度，5步展示）
- [ ] **21. 实现音频播放器组件**
- [ ] **22. 实现任务列表页**

#### 集成测试（Week 5）
- [ ] **23. 端到端集成测试**：从登录→上传→翻译→下载的完整流程
- [ ] **24. 双人播客场景测试**：验证说话人分段+独立声音克隆
- [ ] **25. 性能基准测试**：单集 60 分钟播客的处理时间
- [ ] **26. 部署 staging 环境**

### Phase 2 体验优化（参考 SAD Gantt 图）
- 多说话人支持（3-5人）
- 时间轴对齐优化
- 背景音分离与混音
- 中英文校对编辑功能

### Phase 3 生产强化
- GPU 弹性伸缩
- 降级与限流
- 可观测性与质量监控
- 付费订阅系统
