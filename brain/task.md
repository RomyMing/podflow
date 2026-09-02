# PodFlow 测试与联调执行任务

## Phase 0: 代码缺陷修复（阻塞项）
- [ ] 修复 `main.py` — 整理 import、移除 traceback 泄露
- [ ] 修复 `tasks.py` — 移除 error.log 写文件，改用 logger
- [ ] 修复前端 `TokenResponse.exp` 类型 string → datetime 兼容

## Phase 1: Nginx 统一代理配置
- [ ] 创建 `deploy/nginx/nginx.conf` — HTTP + WebSocket 代理
- [ ] 更新 `docker-compose.yml` — 添加 nginx 服务
- [ ] 更新前端 `next.config.ts` — 移除 rewrites（由 nginx 接管）
- [ ] 更新前端 WebSocket URL 构造逻辑

## Phase 2: 测试基础设施搭建
- [ ] 创建 `tests/conftest.py` — PostgreSQL 测试库 fixtures
- [ ] 安装测试依赖 (pytest-asyncio, httpx, etc.)

## Phase 3: 后端单元测试
- [ ] `tests/unit/test_services/test_auth_service.py` (~7 用例)
- [ ] `tests/unit/test_services/test_task_service.py` (~8 用例)
- [ ] `tests/unit/test_services/test_quota_service.py` (~6 用例)

## Phase 4: 后端集成测试
- [ ] `tests/integration/test_api/test_auth_api.py` (~5 用例)
- [ ] `tests/integration/test_api/test_tasks_api.py` (~5 用例)
- [ ] `tests/integration/test_api/test_users_api.py` (~3 用例)
- [ ] `tests/integration/test_api/test_websocket.py` (~2 用例)

## Phase 5: 验证
- [ ] 运行全部测试并确认通过
- [ ] 启动完整环境验证 nginx 代理
