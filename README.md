# 智能判题系统

基于多模态大模型的大学智能判题系统，当前按 **Web 应用（B/S）** 架构设计：
- 用户通过浏览器拍照/上传题目
- 服务端调用大模型进行识别、判分与过程分解释
- 支持题库管理（Word/PDF 导入题目与答案）

> 说明：项目已在需求规格说明书中切换到 V0.2 架构方向（FastAPI + Web 前端）。

## 技术栈（V0.2）

| 层 | 技术 |
|---|---|
| 开发语言 | Python 3.10+ |
| 后端框架 | FastAPI |
| 数据库 | SQLite（后续可切 PostgreSQL） |
| ORM | SQLModel |
| 前端 | HTML + CSS + JavaScript |
| 网络请求 | httpx（异步） |
| 图像处理 | Pillow |
| 文档解析 | python-docx + pdfplumber |
| 模型调用 | OpenAI 兼容接口（多模态 Chat Completions） |

## 快速开始

### 1) 安装依赖

```bash
pip install fastapi uvicorn sqlmodel httpx python-multipart python-docx pdfplumber pillow jinja2
```

### 2) 配置环境变量

系统通过环境变量读取 LLM API 配置。

```bash
# Linux / macOS
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.ethan0x0000.work/v1"
export OPENAI_MODEL="gpt-4o-mini"

# Windows PowerShell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_BASE_URL="https://api.ethan0x0000.work/v1"
$env:OPENAI_MODEL="gpt-4o-mini"

# Windows CMD
set OPENAI_API_KEY=your-api-key
set OPENAI_BASE_URL=https://api.ethan0x0000.work/v1
set OPENAI_MODEL=gpt-4o-mini
```

| 变量名 | 说明 | 默认值 |
|---|---|---|
| `OPENAI_API_KEY` | LLM 服务 API Key | 无（必填） |
| `OPENAI_BASE_URL` | API 基地址 | `https://api.ethan0x0000.work/v1` |
| `OPENAI_MODEL` | 模型标识符 | `gpt-4o-mini` |

### 3) 启动服务

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

浏览器访问：`http://localhost:8000`

## 项目结构

```text
question-judgment/
├── backend/                      # 后端代码
│   ├── main.py                   # FastAPI 入口
│   ├── routers/                  # API 路由（判题/上传/题库）
│   ├── services/                 # 业务逻辑（判题/文档解析/匹配）
│   ├── models.py                 # 数据模型
│   └── utils/                    # 工具函数（图片、LaTeX）
├── frontend/                     # 前端页面与静态资源
│   ├── index.html                # 判题页
│   └── bank.html                 # 题库管理页
├── test/                         # 测试资源与测试代码
│   └── pdf/                      # 样卷与答案 PDF
├── docs/
│   ├── request/                  # 原始需求
│   ├── reply/                    # 需求规格说明书
│   └── architecture-proposal.md  # 架构建议文档
├── .ethan/
│   └── 项目上手指南.md            # 团队上手文档（含私有 GitLab SSH 说明）
├── AGENTS.md
└── README.md
```

## 功能概述

| 功能 | 说明 |
|---|---|
| 拍照/上传题目 | 浏览器拍照或选择图片上传 |
| 智能判题 | 识别题型、判断正误、输出得分与解析 |
| 过程分 | 计算题按步骤给分并说明依据 |
| 标准答案校准 | 有答案时进行二次校准与容错 |
| 题库管理 | 支持 Word/PDF 导入题目与答案 |
| 结果可追踪 | 保存判题记录，支持查询 |

## 开发指南

### 代码规范

请优先遵循 [AGENTS.md](./AGENTS.md) 与 [需求规格说明书](./docs/reply/需求规格说明书.md)。

核心规范：
- 命名：类 `PascalCase`，函数/变量 `snake_case`，常量 `UPPER_SNAKE_CASE`
- 缩进：4 空格
- 导入顺序：标准库 → 第三方 → 本地模块
- 类型标注：新增函数必须包含参数与返回值类型
- 错误处理：禁止裸 `except:`

### Lint / 格式化（推荐）

```bash
pip install ruff
ruff check .
ruff check --fix .
ruff format .
```

### 测试（推荐）

```bash
pip install pytest
pytest test/
pytest test/test_something.py
pytest test/test_something.py::test_name
pytest -x
```

## Git 与团队协作

### 提交信息规范

```text
feat:     新功能
fix:      修复缺陷
docs:     文档变更
refactor: 重构（不改变外部行为）
test:     测试相关
chore:    构建、依赖等杂项
```

分支命名建议：`feature/xxx`、`fix/xxx`、`docs/xxx`

## 安全须知

- 严禁在源码中硬编码 API Key
- 建议使用 `.env` 管理本地环境变量，并将 `.env` 加入 `.gitignore`
- 私钥文件（SSH）不得上传到仓库

## 相关文档

- [AGENTS.md](./AGENTS.md) — AI 编程代理执行规范
- [需求规格说明书（V0.2）](./docs/reply/需求规格说明书.md) — 功能/架构/验收标准
- [架构重构建议](./docs/architecture-proposal.md) — Web 架构迁移说明
- [项目上手指南](./.ethan/项目上手指南.md) — 团队上手与私有 GitLab SSH 配置

## License

内部项目，暂未设定开源协议。
