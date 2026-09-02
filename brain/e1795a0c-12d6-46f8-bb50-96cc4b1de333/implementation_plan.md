# Authentication and Quota API Components Implementation

本计划旨在实现 PodCast Translator 的 Phase 1 用户体系（认证与配额 API 组件），基于 PRD v1.1 的最新规划，并修复之前代码审计（Code Audit）中发现的所有问题。

## User Review Required

> [!WARNING]
> 本计划涉及对**受保护文件**的修改。请 Chief Architect 审核批准：
> 1. `src/config.py` - 需要追加 JWT、SMS 和 WeChat 的配置项。
> 2. 此审查也会一并解决之前遗留的 `src/repositories/base.py` 中 `str` 类型问题，如果获得了授权的话。请确认我们在同一阶段修复它们。

## Proposed Changes

---

### Models and Repositories

#### [MODIFY] [user.py](../../podcast_translator/src/models/user.py)
- 补充缺失字段：`updated_at`, `is_active`, `quota_reset_at`。
- 解决循环引用：增加 `from typing import TYPE_CHECKING`。
- 添加 `CheckConstraint` 确保 `phone` 和 `wechat_openid` 至少有一个非空。
- 补充所有字段及类的 Google Style Docstring。

#### [NEW] [user_repo.py](../../podcast_translator/src/repositories/user_repo.py)
- 继承 `BaseRepository[User]`。
- 提供按 `phone` 和按 `wechat_openid` 查找用户的方法：
  - `async def get_by_phone(self, phone: str) -> User | None`
  - `async def get_by_wechat_openid(self, openid: str) -> User | None`

---

### Core Security & Infrastructure

#### [MODIFY] [config.py](../../podcast_translator/src/config.py)
- 追加配置项：
  - Token相关：`PCT_ACCESS_TOKEN_EXPIRE_MINUTES`, `PCT_REFRESH_TOKEN_EXPIRE_DAYS`
  - SMS相关：`PCT_SMS_PROVIDER`, `PCT_SMS_ACCESS_KEY_ID`, `PCT_SMS_ACCESS_KEY_SECRET`, `PCT_SMS_SIGN_NAME`, `PCT_SMS_TEMPLATE_CODE`
  - 微信相关：`PCT_WECHAT_APP_ID`, `PCT_WECHAT_APP_SECRET`
  - 配额相关：`PCT_DEFAULT_MONTHLY_QUOTA`

#### [MODIFY] [security.py](../../podcast_translator/src/core/security.py)
- 在 Payload 中增加 Token 类型的区分 (`token_type: access | refresh`)。
- 新增 `create_refresh_token` 方法。
- 重构 `decode_token` 以处理 `ExpiredSignatureError` 和 `InvalidTokenError` 等异常。
- 消除硬编码（将 `ALGORITHM` 等变量配置关联到 Settings），补充 Docstring。

#### [NEW] [exceptions.py](../../podcast_translator/src/core/exceptions.py)
- 定义全局体系异常基类 `PCTException`。
- 增加 `AuthenticationError` (401), `TokenExpiredError` (401), `QuotaExceededError` (403), `ValidationError` (400) 等。

#### [NEW] [sms.py](../../podcast_translator/src/core/sms.py)
- 封装 SMS 发送服务，当前提供基础的 Mock / 日志打印或者接入阿里云/腾讯云的占位实现，确保后续业务逻辑可以正常调用。

#### [NEW] [wechat.py](../../podcast_translator/src/core/wechat.py)
- 封装微信 OAuth2 交互逻辑，暴露如 `get_openid_by_code(code: str) -> str` 接口。

---

### Schemas

#### [NEW] [auth.py](../../podcast_translator/src/schemas/auth.py)
- 创建 `SMSLoginRequest` (phone, code)
- 创建 `WechatLoginRequest` (code)
- 创建 `TokenResponse` (access_token, refresh_token, token_type, exp)

#### [NEW] [user.py](../../podcast_translator/src/schemas/user.py)
- 创建 `UserResponse` (id, phone, nickname, avatar_url, monthly_quota, monthly_used, created_at)
- 创建 `QuotaResponse` (total, used, remaining, reset_at)

---

### Services (Business Logic)

#### [NEW] [auth_service.py](../../podcast_translator/src/services/auth_service.py)
- `send_sms_code(phone: str)`
- `login_with_sms(phone: str, code: str) -> TokenResponse`
- `login_with_wechat(code: str) -> TokenResponse`
- `refresh_token(refresh_token: str) -> TokenResponse`

#### [NEW] [quota_service.py](../../podcast_translator/src/services/quota_service.py)
- `check_quota(user_id: UUID) -> bool`
- `consume_quota(user_id: UUID, amount: int = 1)`
- `get_quota_info(user_id: UUID) -> QuotaResponse`

---

### API Routing Layer

#### [MODIFY] [dependencies.py](../../podcast_translator/src/dependencies.py)
- 注入 `get_auth_service(db)`
- 注入 `get_quota_service(db)`
- 实现 `get_current_user(...)` 作为 FastAPI Dependency，用于从 Header 的 Access Token 验证身份并返回 User。

#### [NEW] [auth.py](../../podcast_translator/src/api/v1/auth.py)
- 注册如下端点：
  - `POST /api/v1/auth/sms/send`
  - `POST /api/v1/auth/sms/login`
  - `POST /api/v1/auth/wechat/login`
  - `POST /api/v1/auth/refresh`
  - `POST /api/v1/auth/logout`

#### [NEW] [users.py](../../podcast_translator/src/api/v1/users.py)
- 注册如下端点：
  - `GET /api/v1/users/me`
  - `GET /api/v1/users/me/quota`

## Open Questions

1. 由于受保护文件 `config.py` 和 `base.py` 需要更新，我们是否可以在本次 Implement 中连同之前查出的低优先级问题（如 `BaseRepository` 没有 `list` 方法等）一起修正？
2. 事务层面，在 `Service` 层面是否需要开启显式的提交机制？即通过在 Service 方法终点显式调用 `await db.commit()` 来提交。

## Verification Plan

### Automated Tests
- 基于 `pytest` 运行单元测试套件：重点测试 Token 签发、刷新过期逻辑；测试配额扣减拦截；测试参数验证正确性。

### Manual Verification
- 启动 Swagger UI `http://localhost:8000/docs`。
- 测试模拟发送验证码。
- 使用错误的验证码进行登录，应获得 `401 Unauthorized` 对应的详细提示。
- 获取 Token，将其配置进 Authorization 头，访问 `/api/v1/users/me` 和 `/api/v1/users/me/quota` 验证返回体正确性。
