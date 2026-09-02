"""
WebSocket 集成测试

注意：WebSocket 的完整自动化测试需要 `websockets` 库或实际启动服务。
以下用例标记为手动联调验证项。

联调时的验证清单:
1. ws://localhost/api/v1/tasks/{task_id}/ws?token=xxx → 连接成功
2. ws://localhost/api/v1/tasks/{task_id}/ws → 4001 关闭（无 token）
3. ws://localhost/api/v1/tasks/{task_id}/ws?token=invalid → 4003 关闭
"""
import pytest


@pytest.mark.skip(reason="WebSocket 测试需要实际服务运行，通过手动联调验证")
class TestWebSocketAuth:
    async def test_ws_without_token(self):
        """无 token 连接 WebSocket → 应被拒绝 (code=4001)"""
        pass

    async def test_ws_with_valid_token(self):
        """带 token 连接 WebSocket → 应成功建立连接"""
        pass

    async def test_ws_with_invalid_token(self):
        """非法 token 连接 WebSocket → 应被拒绝 (code=4003)"""
        pass
