# PodFlow 测试计划与前后端联调方案

> 基于 2026-04-22 对全部前后端代码的深度审查

---

## 一、代码审查发现的问题

### 🔴 必须修复（阻塞联调）

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 1 | `router.py` 是空文件，路由直接在 `main.py` 中注册 | `src/api/router.py` | 与架构规范不一致，但不阻塞功能 |
| 2 | `conftest.py` 为空，无任何测试 fixture | `tests/conftest.py` | 所有测试目录为空壳，零测试覆盖 |
| 3 | WebSocket 路由不走 Next.js rewrites 代理 | `frontend/next.config.ts` | `ws://` 协议无法通过 HTTP rewrite 代理 |
| 4 | 全局异常处理泄露 traceback 给客户端 | `src/main.py:35-40` | 安全风险：生产环境不应暴露堆栈 |
| 5 | `create_task` 中错误日志写固定文件 `error.log` | `src/api/v1/tasks.py:30` | 多并发写冲突，应改用 logger |

### 🟡 建议优化（不阻塞联调）

| # | 问题 | 位置 |
|---|------|------|
| 6 | `main.py` 中 import 分散在文件中间，违反 PEP8 | `src/main.py` |
| 7 | `health.py` 和 `transcripts.py` 是空文件 | `src/api/v1/` |
| 8 | 前端 `TokenResponse.exp` 类型为 `string`，后端为 `datetime` | 前端 `types/api.ts:31` vs 后端 `schemas/auth.py:21` |
| 9 | WebSocket 无自动重连机制 | `frontend/src/lib/websocket.ts` |
| 10 | Pipeline 阶段结束后未回调更新 DB 中的 task 状态 | `orchestrator.py` 与 `task_service.update_task_progress` 之间断裂 |

---

## 二、后端测试计划

### Phase T1：测试基础设施搭建

**目标**：搭建可运行的 pytest 环境

```
tests/
├── conftest.py              # 全局 fixtures
├── unit/
│   ├── test_services/
│   │   ├── test_auth_service.py
│   │   ├── test_task_service.py
│   │   └── test_quota_service.py
│   ├── test_pipeline/
│   │   └── test_orchestrator.py
│   └── test_utils/
├── integration/
│   ├── test_api/
│   │   ├── test_auth_api.py
│   │   ├── test_tasks_api.py
│   │   └── test_users_api.py
│   └── test_workers/
└── e2e/
    └── test_full_pipeline.py
```

**conftest.py 需要提供的 fixtures**：
- `test_db_session` — 使用 SQLite (async) 或独立 PostgreSQL test 数据库
- `test_client` — `httpx.AsyncClient` 绑定 FastAPI app
- `authenticated_client` — 带有有效 JWT 的 test_client
- `mock_user` — 预创建的测试用户
- `mock_storage` — Mock 的 StorageService

### Phase T2：后端单元测试（共 ~25 个用例）

#### T2.1 AuthService 测试

| 用例 | 描述 | 关键断言 |
|------|------|----------|
| `test_send_sms_code_success` | 发送验证码 | 返回 True |
| `test_login_with_sms_new_user` | 新手机号登录自动注册 | 返回 TokenResponse, DB 新增 User |
| `test_login_with_sms_existing_user` | 已注册用户登录 | 返回 TokenResponse, 不新增 User |
| `test_login_with_sms_wrong_code` | 错误验证码 | 抛出 AuthenticationError |
| `test_refresh_token_success` | 刷新 token | 返回新的 token pair |
| `test_refresh_token_with_access_token` | 用 access token 刷新 | 抛出 AuthenticationError |
| `test_refresh_token_expired` | 过期 refresh token | 抛出异常 |

#### T2.2 TaskService 测试

| 用例 | 描述 | 关键断言 |
|------|------|----------|
| `test_create_task_success` | 正常创建任务 | Task 记录入库, status=pending |
| `test_create_task_quota_exceeded` | 配额不足 | 抛出 QuotaExceededError |
| `test_create_task_upload_failure_refund` | 上传失败回滚配额 | quota refunded |
| `test_get_task_success` | 查询自己的任务 | 返回 Task |
| `test_get_task_not_found` | 查询不存在任务 | 抛出 ResourceNotFoundError |
| `test_get_task_other_user` | 查询别人的任务 | 抛出 ResourceNotFoundError |
| `test_list_tasks` | 列表查询 | 仅返回当前用户任务, 按时间降序 |
| `test_update_task_progress` | 更新进度 | DB 更新 + WS 广播 |

#### T2.3 QuotaService 测试

| 用例 | 描述 | 关键断言 |
|------|------|----------|
| `test_check_quota_has_remaining` | 有剩余配额 | 返回 True |
| `test_check_quota_exhausted` | 配额耗尽 | 返回 False |
| `test_consume_quota` | 扣减配额 | monthly_used + 1 |
| `test_consume_quota_insufficient` | 超额扣减 | 抛出 QuotaExceededError |
| `test_refund_quota` | 退还配额 | monthly_used - 1, 不低于 0 |
| `test_get_quota_info` | 查询配额 | 返回正确的 total/used/remaining |

### Phase T3：后端集成测试（共 ~15 个用例）

使用 `httpx.AsyncClient` 对完整 API 端点进行测试：

| 端点 | 方法 | 用例 | 预期 |
|------|------|------|------|
| `/api/v1/auth/sms/send` | POST | 发送验证码 | 200 |
| `/api/v1/auth/sms/login` | POST | 正确验证码登录 | 200 + tokens |
| `/api/v1/auth/sms/login` | POST | 错误验证码 | 401 |
| `/api/v1/auth/refresh` | POST | 合法 refresh token | 200 + new tokens |
| `/api/v1/auth/refresh` | POST | 非法 token | 401 |
| `/api/v1/users/me` | GET | 带 token 查询 | 200 + UserResponse |
| `/api/v1/users/me` | GET | 无 token | 401 |
| `/api/v1/users/me/quota` | GET | 查询配额 | 200 + QuotaResponse |
| `/api/v1/tasks` | POST | 上传文件创建任务 | 200 + TaskResponse |
| `/api/v1/tasks` | POST | 无 token | 401 |
| `/api/v1/tasks` | GET | 查询任务列表 | 200 + list |
| `/api/v1/tasks/{id}` | GET | 查询存在的任务 | 200 |
| `/api/v1/tasks/{id}` | GET | 查询不存在任务 | 404 |
| `/api/v1/tasks/{id}/ws` | WS | 带 token 连接 | 连接成功 |
| `/api/v1/tasks/{id}/ws` | WS | 无 token | 4001 关闭 |

---

## 三、前端测试计划

> 由于项目未安装 Jest/Vitest，前端测试以**浏览器手动验证 + 联调**为主

### 页面可达性检查

| 路由 | 页面 | 状态 | 需验证 |
|------|------|------|--------|
| `/login` | 登录页 | ✅ 有组件 | 表单渲染、验证码倒计时 |
| `/` (protected) | 首页/上传 | ✅ 有组件 | 上传区域、URL 输入、配额、最近任务 |
| `/tasks` | 任务列表 | ✅ 有组件 | 列表加载、筛选 |
| `/tasks/[id]` | 任务详情 | ✅ 有目录 | 进度展示、WS 连接 |
| `/profile` | 个人中心 | ✅ 有组件 | 用户信息、配额 |

### 组件功能验证

| 组件 | 验证要点 |
|------|----------|
| `AuthGuard` | 未登录重定向到 `/login` |
| `UploadZone` | 拖拽上传、文件格式校验、进度条 |
| `TaskList` | 任务列表渲染、状态标签 |
| `TaskConfigPanel` | 侧边面板开关、配置提交 |
| `QuotaBar` | 配额数据展示 |

---

## 四、前后端联调方案（5 个阶段）

### 阶段 1：环境准备与基础连通

**前置条件**：
```bash
# 1. 启动基础设施
cd podcast_translator
docker-compose up -d   # PostgreSQL + Redis + MinIO

# 2. 数据库迁移
alembic upgrade head

# 3. 启动后端
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 4. 启动前端
cd frontend && npm run dev
```

**验证项**：
- [ ] `http://localhost:8000/health` 返回 `{"status": "ok", "db": "ok"}`
- [ ] `http://127.0.0.1:8080/login` 前端页面正常加载
- [ ] 前端 `/api/v1/...` 请求被 Next.js rewrite 正确代理到 `:8000`

---

### 阶段 2：认证流程联调

**流程**：前端发送验证码 → 输入 `123456` 登录 → Token 存 localStorage → 获取用户信息 → 跳转首页

**验证清单**：
- [ ] 输入手机号 → 点发送 → 60秒倒计时
- [ ] 输入验证码 `123456` → 登录成功 → 跳转首页
- [ ] `localStorage` 中存在 `access_token` 和 `refresh_token`
- [ ] 首页 AuthGuard 通过 → 用户信息正常展示
- [ ] 退出登录 → 清除 tokens → 跳转 `/login`
- [ ] Token 过期 → interceptor 自动刷新 → 请求重试成功

---

### 阶段 3：任务 CRUD + 文件上传联调

**流程**：拖拽文件 → 配置面板 → 提交上传 → Presigned URL 预览 → 列表查询

**验证清单**：
- [ ] 拖拽/选择音频文件 → 配置面板打开
- [ ] 提交配置 → 上传进度条显示 → 完成后跳转任务详情
- [ ] 任务列表显示新建的任务，状态为 `pending`
- [ ] 任务详情页展示 source_audio_url (presigned URL)
- [ ] 配额余量减 1
- [ ] 上传失败时配额回滚
- [ ] MinIO 控制台 (`localhost:9001`) 可看到上传的文件

---

### 阶段 4：WebSocket 进度推送联调

> [!WARNING]
> WebSocket 代理是已知风险点。Next.js rewrites 不支持 `ws://` 协议，需要额外处理。

**解决方案（三选一）**：
1. 前端 WS 直连后端 `ws://localhost:8000/api/v1/tasks/{id}/ws`（开发快速验证）
2. 使用 Next.js `middleware.ts` + custom server 代理 WS
3. 使用 nginx 做统一代理（推荐生产方案）

**验证清单**：
- [ ] 任务详情页打开 → WS 连接建立（控制台无报错）
- [ ] 后端推送进度 → 前端实时更新进度百分比和阶段名
- [ ] 任务完成 → WS 自动断开 → 页面 refetch 最终状态
- [ ] 无 token 连接 WS → 被拒绝（code 4001）
- [ ] 切换页面 → WS 自动断连（无内存泄漏）

---

### 阶段 5：异常场景与边界测试

| 场景 | 操作 | 预期行为 |
|------|------|----------|
| 未登录访问 | 直接访问 `/tasks` | 跳转 `/login` |
| Token 过期 | 等 30min 或手动过期 | interceptor 自动刷新 |
| Refresh Token 过期 | 手动清除 | 跳转 `/login` |
| 上传超大文件 | 上传 600MB+ | 流式处理，不 OOM |
| 配额为 0 | 耗尽后再上传 | 前端展示 403 错误提示 |
| 查询他人任务 | 伪造 task_id | 404 |
| 后端宕机 | 停止 uvicorn | 前端展示网络错误 |
| MinIO 宕机 | 停止 minio 容器 | 上传失败 + 配额退还 |
| 并发上传 | 同时上传多个文件 | 各任务独立，不干扰 |

---

## 五、执行优先级

```
第1天: 环境准备 + 认证联调 (阶段 1-2)
第2天: 任务 CRUD + 文件上传联调 (阶段 3)
第3天: WebSocket 联调 + 异常测试 (阶段 4-5)
第4天: 编写后端测试 (Phase T1-T2)
第5天: 编写集成测试 + 修复发现的 Bug (Phase T3)
```

## 六、Open Questions

> [!IMPORTANT]
> 1. **WebSocket 代理方案**：联调阶段先用直连方案（方案1）快速验证，还是直接搭建 nginx 统一代理？
> 2. **测试数据库**：单元测试使用 SQLite 内存库（轻量快速）还是 PostgreSQL 测试库（更接近生产）？
> 3. **Pipeline 阶段模拟**：联调时 Celery worker 是否启动？还是仅用 mock 数据模拟任务状态变化？
> 4. **前端测试框架**：是否需要引入 Vitest + Testing Library 做组件单元测试？
