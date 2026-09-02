# 认证与配额 API 组件实现计划

本项目基于我们之前确认的**“手机号 + 微信登录”**的认证方案以及**“MVP 每月 5 集免费额度”**的配额机制，设计完整的由端到端流转逻辑。
以下是针对 `src/` 各分层将要创建/修改的具体组件说明。

## ⚠️ 发现问题：Docker 启动失败
在开始设计前，我注意到你刚刚执行 `docker compose up -d` 报错 `no configuration file provided: not found`。
这主要是因为你**当前所在的目录**是 `podcast_translate/`，而由于我们规范统一的实际项目工作区在 `podcast_translator/` 中。你需要 `cd podcast_translator` 后再执行 Docker 命令即可成功。

---

## 1. 核心数据结构与契约 (Schemas)

#### [NEW] [auth.py](../../podcast_translator/src/schemas/auth.py)
定义前后端登录交互数据格式：
- `SMSSendRequest`: `phone`
- `SMSLoginRequest`: `phone`, `code`
- `WechatLoginRequest`: `code`
- `TokenResponse`: `access_token`, `token_type`

#### [NEW] [user.py](../../podcast_translator/src/schemas/user.py)
定义用户信息和配额的返回结构：
- `UserResponse`: 用户脱敏信息展示
- `QuotaResponse`: 当月可用/已用额度

## 2. 数据访问层 (Repository)

#### [NEW] [user_repo.py](../../podcast_translator/src/repositories/user_repo.py)
继承于 `BaseRepository`，扩展实现专属查询接口：
- `get_by_phone(phone)` 
- `get_by_wechat_openid(openid)`

## 3. 第三方平台接入 (Core Integrations)

我们需要对外部 SDK 或者 HTTP 请求进行剥离与防腐设计，本次将建立桩接口(stub)。
#### [NEW] [sms.py](../../podcast_translator/src/core/sms.py)
- `send_sms_code(phone)`：生成并发送 6 位数验证码（MVP 阶段只打 Log 并在 Redis 临时存储验证，不涉及真实资费调用）。

#### [NEW] [wechat.py](../../podcast_translator/src/core/wechat.py)
- `exchange_code_for_user_info(code)`：用 OAuth code 去微信服务器换取 openid （MVP 阶段返回 Mock 对象）。

## 4. 业务逻辑层 (Services)

#### [NEW] [auth_service.py](../../podcast_translator/src/services/auth_service.py)
编排登录逻辑：
1. 校验验证码正确性或微信 code 有效性。
2. 内部调研 Repo 查看是否存在用户，不存在则隐式创建注册并给予初始配额 (5 首/月)。
3. 调用 `create_access_token` 生成 JWT Token。

#### [NEW] [quota_service.py](../../podcast_translator/src/services/quota_service.py)
实现配额生命周期管理：
- `check_has_quota(user_id)`：检查余额是否 > 0。
- `deduct_quota(user_id, amount=1)`：任务启动或完成时扣除配额（带有并发锁预防超发）。

## 5. API 路由与鉴权依赖 (API & Dependencies)

#### [NEW] [dependencies.py](../../podcast_translator/src/dependencies.py)
提供统一的 FastAPI Depends 注入对象：
- `get_current_user`：读取全局 Authorization HTTP header，校验并提取鉴权上下文。确保需要登录的接口能够直接拿到 `User` 对象。

#### [NEW] [v1/auth.py](../../podcast_translator/src/api/v1/auth.py)
向外暴露规范的 REST 接口（与 ADS 白皮书中规划的完全对齐）：
- `POST /api/v1/auth/sms/send`
- `POST /api/v1/auth/sms/login`
- `POST /api/v1/auth/wechat/login`
- `GET /api/v1/auth/me`  (返回当前用户信息含配额)

---

## User Review Required

> [!CAUTION]
> **MVP 阶段是否支持刷新令牌 (Refresh Token)?**
> 当访问令牌 (Access Token) 过期后（通常是 2 小时无操作），在不提供完整重新接入门户的前提下，是否需要专门开发 Refresh Token 的双 Token 续订流水线？
> **建议：** 为了 MVP 加速冲刺，可适当将 Access Token 延长至 7 天，暂缓开发双 Token 逻辑，由纯 Access Token 兜底。您是否同意此建议？

如果您同意上述计划或有任何修改意见，请随时反馈，一旦获得您的绿灯，我将立即下入执行引擎为您生成代码并完成部署组装。
