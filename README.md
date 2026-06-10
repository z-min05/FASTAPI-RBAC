# FastAPI-RBAC

基于 FastAPI 的 RBAC（基于角色的访问控制）权限管理系统，提供完整的用户、角色、权限、菜单、部门管理功能。

## 🌟 功能特性

- **用户管理** - 用户 CRUD、角色分配、密码重置
- **角色管理** - 角色 CRUD、权限分配、菜单分配
- **权限管理** - 权限 CRUD、模块分组
- **菜单管理** - 菜单树 CRUD、权限关联、树形结构
- **部门管理** - 部门树 CRUD、负责人管理
- **操作日志** - 请求日志记录、审计查询
- **JWT 认证** - 登录、注册、刷新令牌
- **RBAC 鉴权** - 基于角色的细粒度权限控制

## 🛠️ 技术栈

| 分类 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | 3.11+ |
| 框架 | FastAPI | 0.115+ |
| ORM | SQLAlchemy | 2.0+ |
| 数据库 | PostgreSQL | 16+ |
| 缓存 | Redis | 7+ |
| 认证 | JWT (python-jose) | 3.3+ |
| 密码 | bcrypt (passlib) | 1.7+ |
| 迁移 | Alembic | 1.14+ |
| 校验 | Pydantic | 2.10+ |
| 容器 | Docker / Docker Compose | - |

## 📁 项目结构

```
fastapi-rbac/
├── alembic/                    # 数据库迁移
│   ├── versions/              # 迁移版本文件
│   └── env.py
├── app/
│   ├── api/                   # 路由层
│   │   ├── v1/               # API v1 版本
│   │   │   ├── auth.py       # 认证接口
│   │   │   ├── users.py      # 用户管理
│   │   │   ├── roles.py      # 角色管理
│   │   │   ├── permissions.py# 权限管理
│   │   │   ├── menus.py      # 菜单管理
│   │   │   ├── departments.py# 部门管理
│   │   │   └── logs.py       # 日志查询
│   │   └── deps.py           # 路由依赖
│   ├── core/                  # 核心能力
│   │   ├── rbac.py           # RBAC 鉴权逻辑
│   │   ├── pagination.py     # 通用分页工具
│   │   └── response.py       # 统一响应封装
│   ├── db/                   # 数据库连接
│   │   ├── session.py        # SessionLocal、engine
│   │   └── init_db.py        # 初始化脚本
│   ├── middlewares/          # 中间件
│   │   ├── cors.py           # CORS 配置
│   │   └── logging.py        # 请求日志中间件
│   ├── models/               # SQLAlchemy ORM 模型
│   ├── schemas/              # Pydantic 请求/响应模型
│   ├── services/             # 业务逻辑层
│   ├── repositories/         # 数据访问层
│   ├── utils/                # 工具函数
│   ├── config.py             # 全局配置
│   ├── security.py           # JWT 生成/验证
│   ├── dependency.py         # 依赖注入
│   ├── exceptions.py         # 自定义异常
│   └── main.py               # 应用入口
├── tests/                    # 测试用例
├── scripts/                  # 运维脚本
│   └── seed_data.py          # 初始化种子数据
├── .env                      # 环境变量
├── .env.example              # 环境变量模板
├── docker-compose.yml        # Docker 编排
├── Dockerfile
├── requirements.txt          # 依赖管理
├── alembic.ini               # Alembic 配置
└── README.md
```

## 🚀 快速开始

### 方式一：使用 Docker Compose（推荐）

```bash
# 进入项目目录
cd fastapi-rbac

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 方式二：本地开发

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，修改数据库连接

# 初始化数据库（可选）
python -m scripts.seed_data

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 方式三：使用 ASGI 服务器

```bash
# 使用 gunicorn + uvicorn
pip install gunicorn
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 🗄️ 数据库迁移

```bash
# 创建迁移
alembic revision --autogenerate -m "描述信息"

# 执行迁移
alembic upgrade head

# 回滚到上一个版本
alembic downgrade -1

# 查看迁移历史
alembic history
```

## 📖 API 文档

启动服务后访问：

| 文档类型 | 地址 |
|----------|------|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

## 🔐 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123456 | 超级管理员 |

## 🔌 API 接口列表

### 认证接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/auth/login | 用户登录 |
| POST | /api/v1/auth/register | 用户注册 |
| POST | /api/v1/auth/refresh | 刷新令牌 |

### 用户管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/users | 获取用户列表 |
| GET | /api/v1/users/{id} | 获取用户详情 |
| POST | /api/v1/users | 创建用户 |
| PUT | /api/v1/users/{id} | 更新用户 |
| DELETE | /api/v1/users/{id} | 删除用户 |

### 角色管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/roles | 获取角色列表 |
| GET | /api/v1/roles/{id} | 获取角色详情 |
| POST | /api/v1/roles | 创建角色 |
| PUT | /api/v1/roles/{id} | 更新角色 |
| DELETE | /api/v1/roles/{id} | 删除角色 |

### 权限管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/permissions | 获取权限列表 |
| GET | /api/v1/permissions/{id} | 获取权限详情 |
| POST | /api/v1/permissions | 创建权限 |
| PUT | /api/v1/permissions/{id} | 更新权限 |
| DELETE | /api/v1/permissions/{id} | 删除权限 |

### 菜单管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/menus | 获取菜单列表 |
| GET | /api/v1/menus/tree | 获取菜单树 |
| GET | /api/v1/menus/{id} | 获取菜单详情 |
| POST | /api/v1/menus | 创建菜单 |
| PUT | /api/v1/menus/{id} | 更新菜单 |
| DELETE | /api/v1/menus/{id} | 删除菜单 |

### 部门管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/departments | 获取部门列表 |
| GET | /api/v1/departments/tree | 获取部门树 |
| GET | /api/v1/departments/{id} | 获取部门详情 |
| POST | /api/v1/departments | 创建部门 |
| PUT | /api/v1/departments/{id} | 更新部门 |
| DELETE | /api/v1/departments/{id} | 删除部门 |

### 日志管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/logs | 获取操作日志列表 |
| GET | /api/v1/logs/user/{id} | 获取指定用户日志 |

## 🛡️ 权限控制

系统采用 RBAC（基于角色的访问控制）模式：

1. **用户** ↔ **角色**（多对多）
2. **角色** ↔ **权限**（多对多）
3. **角色** ↔ **菜单**（多对多）

权限编码格式：`模块:操作`，例如：
- `user:list` - 用户列表
- `user:create` - 创建用户
- `role:delete` - 删除角色

## ⚙️ 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DATABASE_URL | 数据库连接 URL | postgresql+asyncpg://... |
| REDIS_URL | Redis 连接 URL | redis://localhost:6379/0 |
| SECRET_KEY | JWT 密钥 | - |
| ALGORITHM | JWT 算法 | HS256 |
| ACCESS_TOKEN_EXPIRE_MINUTES | 访问令牌过期时间（分钟） | 30 |
| REFRESH_TOKEN_EXPIRE_DAYS | 刷新令牌过期时间（天） | 7 |
| DEBUG | 调试模式 | false |
| LOG_LEVEL | 日志级别 | INFO |

## 🧪 测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio

# 运行测试
pytest tests/ -v

# 运行指定测试文件
pytest tests/test_auth.py -v
```

## 📝 License

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系

如有问题，请提交 GitHub Issue。
