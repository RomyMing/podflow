# PRD 分阶段计划对齐 SAD + 用户体系代码审查

## 一、PRD 与 SAD 分阶段计划差异分析

### 当前状态

**PRD（第七节）** 的阶段划分是按 **功能模块** 划分的：
- 一期 MVP：核心翻译链路 + 用户注册/登录 + 免费额度
- 二期：多说话人(3+) + 校对编辑 + 付费订阅
- 三期：多语种 + API 开放平台

**SAD（第 5.3 节）** 的阶段划分是按 **技术交付里程碑** 划分的：
- Phase 1 MVP（单/双人播客）：音源分离+ASR集成 → 说话人分段 → 双说话人TTS克隆 → 基础Web UI
- Phase 2 体验优化：多说话人(3-5人) + 时间轴对齐优化 + 背景音分离与混音 + 中英文校对编辑
- Phase 3 生产强化：GPU弹性伸缩 + 降级与限流 + 可观测性 + 人工校对工作流

> [!WARNING]
> **核心差异**：PRD 缺少 Phase 0（项目初始化），且 PRD 的阶段命名和范围与 SAD 不完全一致。SAD 无 Phase 0 但代码中已有 Phase 0 的产出（ORM Base、Repository Base、PipelineContext）。PRD 的分阶段描述偏产品功能视角，需要与 SAD 的技术阶段保持映射一致。

### 需要修改 PRD 的内容

将 PRD 第七节"MVP 一期范围总结"替换为与 SAD 5.3 节一致的**分阶段交付路线**，包含以下阶段：

| PRD 阶段 | SAD 阶段 | 需对齐的内容 |
|----------|----------|-------------|
| (缺失) | Phase 0: 项目初始化 | 架构基础搭建（ORM、Repository、PipelineContext） |
| 一期 MVP | Phase 1: MVP（单/双人播客） | 核心翻译链路 + 用户体系 + 基础 Web UI |
| 二期 | Phase 2: 体验优化 | 多说话人 + 校对编辑 + 背景音混音 |
| (缺失) | Phase 3: 生产强化 | GPU 弹性伸缩 + 降级策略 + 可观测性 |
| 三期 | (PRD 独有) | 多语种 + API 开放 + 商业化 → 作为 Phase 4 |

---

## 二、用户体系代码审查结果

### 2.1 已实现的文件（有实际代码）

| 文件 | 状态 | 说明 |
|------|------|------|
| [user.py](../../podcast_translator/src/models/user.py) | ⚠️ 部分实现 | ORM 模型已定义，但有规范问题 |
| [security.py](../../podcast_translator/src/core/security.py) | ⚠️ 部分实现 | JWT 基本功能，但有安全漏洞 |
| [base.py](../../podcast_translator/src/models/base.py) | ✅ 已完成 | ORM Base 类 |
| [base.py](../../podcast_translator/src/repositories/base.py) | ⚠️ 部分实现 | BaseRepository 已定义，但有规范问题 |
| [database.py](../../podcast_translator/src/core/database.py) | ✅ 已完成 | 数据库引擎配置 |
| [context.py](../../podcast_translator/src/pipeline/context.py) | ✅ 已完成 | PipelineContext 定义 |
| [base_stage.py](../../podcast_translator/src/pipeline/base_stage.py) | ✅ 已完成 | StageProcessor 抽象基类 |
| [config.py](../../podcast_translator/src/config.py) | ⚠️ 部分实现 | 缺少认证/SMS/微信相关配置项 |

### 2.2 空文件（仅占位，无任何代码）

| 文件 | 应有内容 |
|------|----------|
| `src/schemas/auth.py` | SMSLoginRequest, WechatLoginRequest, TokenResponse |
| `src/schemas/user.py` | UserResponse, QuotaResponse |
| `src/schemas/common.py` | 公共分页、错误响应 |
| `src/services/auth_service.py` | 登录、Token、微信OAuth编排 |
| `src/services/quota_service.py` | 配额检查、扣减、重置 |
| `src/repositories/user_repo.py` | 用户数据查询（按手机号/openid查找等） |
| `src/core/sms.py` | 短信验证码发送 |
| `src/core/wechat.py` | 微信 OAuth 2.0 封装 |
| `src/core/exceptions.py` | 自定义异常体系 |
| `src/core/redis.py` | Redis 连接池 |
| `src/core/logging.py` | structlog 配置 |
| `src/api/v1/auth.py` | 认证路由端点 |
| `src/api/router.py` | 路由注册总入口 |
| `src/main.py` | FastAPI 应用入口 |
| `src/dependencies.py` | FastAPI 依赖注入 |

### 2.3 具体代码问题清单

---

#### 🔴 高优先级（安全漏洞 / 规范严重违反）

**问题 #1：`security.py` — 缺少 Refresh Token 机制**

```python
# 当前实现只有 Access Token, 缺少 Refresh Token
# SAD API 定义了 POST /api/v1/auth/refresh
# 但 security.py 没有 create_refresh_token 和相关验证
```

> [!CAUTION]
> Access Token 过期后用户需重新登录，严重影响体验。需要实现 Refresh Token 生成/验证。

**问题 #2：`security.py` — `decode_token` 缺少异常处理**

```python
# 当前代码：
def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.PCT_SECRET_KEY.get_secret_value(), algorithms=[ALGORITHM])

# 问题：没有 try-except 处理 ExpiredSignatureError, InvalidTokenError 等
# 恶意Token或过期Token会导致 500 错误而非友好的 401
```

**问题 #3：`security.py` — 缺少 Token 类型区分**

```python
# Access Token 和 Refresh Token 需要不同的 type 字段
# 否则 Refresh Token 可被滥用为 Access Token
# 应在 payload 中加入 "token_type": "access" / "refresh"
```

**问题 #4：`security.py` — 违反 PY-06 (Docstring 必须)**

```python
# create_access_token 和 decode_token 都没有 Google 风格 Docstring
```

**问题 #5：`security.py` — 违反 PY-08 (硬编码零容忍)**

```python
# ACCESS_TOKEN_EXPIRE_MINUTES = 30 硬编码在顶层
# 应通过 config.py 的环境变量控制
ALGORITHM = "HS256"  # 也应该可配置
```

**问题 #6：`User` 模型 — 缺少密码哈希/更新时间等关键字段**

```python
# 当前 User 模型缺少：
# - updated_at: 更新时间戳（审计需要）
# - is_active: 用户状态（封禁/停用场景）
# - quota_reset_at: 配额重置时间点（否则无法实现"每月重置"）
```

> [!IMPORTANT]
> 没有 `quota_reset_at` 字段，配额重置逻辑无法正确实现。

**问题 #7：`User` 模型 — 违反 PY-06 (Docstring 必须)**

模型类缺少 Google 风格 Docstring。

---

#### 🟡 中优先级（规范违反 / 设计缺陷）

**问题 #8：`BaseRepository` — `get()` 方法 id 参数类型为 `str`**

```python
# 当前: async def get(self, id: str) -> ModelType | None:
# User.id 是 uuid.UUID 类型，传入 str 可能导致类型不匹配
# 应改为 uuid.UUID 或使用 Any
```

**问题 #9：`BaseRepository` — 缺少 `list` 方法**

```python
# ADS 8.3 节明确要求 BaseRepository 应提供: get, list, create, update, delete
# 当前缺少 list 方法
```

**问题 #10：`BaseRepository` — `create` 方法缺少 `commit`**

```python
# 只做了 flush，未 commit
# 需要确认事务管理策略：是在 Repository 层 commit 还是在 Service 层统一 commit
# 按照最佳实践，应在 Service 层控制事务边界（commit/rollback）
# 但需要确保 database.py 的 session 在请求结束时有自动 commit/rollback
```

**问题 #11：`database.py` — Session 没有 `expire_on_commit` 配置**

```python
# 默认 expire_on_commit=True 会导致 flush 后访问属性触发额外查询
# 建议设为 False 以提升性能
```

**问题 #12：`config.py` — 缺少用户体系所需的配置项**

```python
# 缺少以下配置项：
# PCT_ACCESS_TOKEN_EXPIRE_MINUTES
# PCT_REFRESH_TOKEN_EXPIRE_DAYS
# PCT_SMS_PROVIDER: Literal["aliyun", "tencent"]
# PCT_SMS_ACCESS_KEY_ID: SecretStr
# PCT_SMS_ACCESS_KEY_SECRET: SecretStr
# PCT_SMS_SIGN_NAME: str
# PCT_SMS_TEMPLATE_CODE: str
# PCT_WECHAT_APP_ID: str
# PCT_WECHAT_APP_SECRET: SecretStr
# PCT_DEFAULT_MONTHLY_QUOTA: int = 5
```

**问题 #13：`User` 模型 — `phone` 和 `wechat_openid` 都可为 None**

```python
# 两个登录标识都可为空，意味着可以创建一个没有任何登录凭证的用户
# 需要在业务层或数据库层添加 CHECK 约束：phone 和 wechat_openid 至少有一个非空
```

---

#### 🟢 低优先级（代码质量改进）

**问题 #14：`User` 模型 — 未使用 `TYPE_CHECKING` 解决循环引用**

```python
# relationship 中引用 "Task" 使用字符串，但未导入 TYPE_CHECKING
# 建议添加:
from __future__ import annotations
# 或
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.models.task import Task
```

**问题 #15：`BaseRepository` — 违反 PY-06 (Docstring 必须)**

`get`, `create`, `update`, `delete` 方法均无 Docstring。

**问题 #16：`database.py` — 违反 PY-06 (Docstring 必须)**

`get_db_session` 有简短 docstring 但格式不符合 Google 风格。

---

## 三、需要对齐的变更方案

### 3.1 PRD 修改

将 PRD 第七节替换为与 SAD 对齐的分阶段交付路线，新增 Phase 0 和调整阶段编号。

#### [MODIFY] [PROJECT_PRD.md](../../PROJECT_PRD.md)

将第七节 "MVP 一期范围总结" 重写为 "分阶段交付路线"，包含：
- Phase 0: 项目初始化（已完成）
- Phase 1: MVP（单/双人播客）— 对应原一期
- Phase 2: 体验优化 — 对应原二期
- Phase 3: 生产强化 — 新增
- Phase 4: 商业化与多语种 — 对应原三期

同时更新 1.2 节的 "阶段性目标"，使之与新的 Phase 编号对应。

### 3.2 代码修复（不修改受保护文件）

> [!IMPORTANT]
> 以下文件为 **受保护文件**，本次 **不会修改**：
> - `src/models/base.py`
> - `src/repositories/base.py`
> - `src/pipeline/context.py`
> - `src/pipeline/base_stage.py`
> - `src/config.py`
> - `src/core/database.py`

仅修复非受保护文件中的问题：

| 文件 | 修复内容 |
|------|----------|
| `src/models/user.py` | 添加 `updated_at`, `is_active`, `quota_reset_at` 字段 + Docstring |
| `src/core/security.py` | 添加 Refresh Token 支持 + 异常处理 + Token 类型区分 + Docstring |

> [!WARNING]
> **受保护文件中的问题** (如 `base.py` 的 `list` 方法缺失、`config.py` 缺少配置项)需要 Chief Architect 批准后才能修改。本报告先记录问题，后续提交 Architecture Review Request。

## 四、Open Questions

1. **受保护文件修改审批**：`config.py` 需要添加认证/SMS/微信相关配置项，这是受保护文件。是否需要立即申请 Architect 审批？还是先只生成审查报告？

2. **事务管理策略**：`BaseRepository` 的 `flush` vs `commit` 策略需要明确 — 是在 Repository 层还是 Service 层管理事务边界？当前 `get_db_session` 只做了 yield 没有自动 commit。

3. **Phase 0 范围确认**：当前已完成的 Phase 0 包括 ORM Base、Repository Base、PipelineContext、基础配置。是否还有其他需要补充的内容？

## 五、Verification Plan

### Automated Tests
- PRD 修改后，逐节对比 SAD 5.3 的里程碑与 PRD 的分阶段计划，确认一致
- 代码修改后，运行 `python -c "from src.models.user import User"` 验证 ORM 模型无语法错误
- 代码修改后，运行 `python -c "from src.core.security import create_access_token, create_refresh_token, decode_token"` 验证模块导入

### Manual Verification
- 肉眼比对 PRD Phase 编号与 SAD 5.3 节 Gantt 图的阶段命名
