# 启动前后端服务流程计划

本计划旨在描述并执行启动 `podcast_translator` 项目完整服务链的流程，包括基础架构、后端 API 和前端界面。

## 用户审查确认

> [!IMPORTANT]
> 确保本地已安装 Docker 并且正在运行，以便启动数据库和缓存服务。
> 需要确保 Python 环境（.venv）已正确配置。

## 拟议变更

### 1. 基础架构启动
- 进入 `podcast_translator` 目录。
- 运行 `docker-compose up -d` 确保 Postgres, Redis 和 MinIO 服务在线。

### 2. 后端虚拟环境与依赖配置 [NEW]
- 进入 `podcast_translator` 目录。
- **创建虚拟环境**（如果不存在）：`python -m venv .venv`。
- **激活虚拟环境**：
  - Windows: `.\.venv\Scripts\activate`
  - Linux/Mac: `source .venv/bin/activate`
- **安装依赖**：
  - 升级 pip: `pip install --upgrade pip`
  - 安装项目依赖：`pip install -e .`
  - 安装开发依赖（如需）：`pip install -e ".[dev]"`

### 3. 后端服务初始化
- 检查并运行数据库迁移：使用 `.\.venv\Scripts\python -m alembic upgrade head`。
- 启动后端 API：运行 `.\.venv\Scripts\python -m uvicorn src.main:app --reload`。
- (可选) 启动 Celery Worker：`.\.venv\Scripts\python -m celery -A src.workers.worker worker --loglevel=info`。

### 4. 前端服务启动
- 进入 `podcast_translator/frontend` 目录。
- 运行 `npm install` (如有必要)。
- 运行 `npm run dev` 启动 Next.js 开发服务器。

## 验证计划

### 自动化/命令行验证
- 检查后端健康接口：`curl http://localhost:8000/health`。
- 检查前端连接：访问 `http://127.0.0.1:8080`。

### 手动验证
- 打开浏览器确认登录页面和上传页面正常渲染。
