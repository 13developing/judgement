# 架构重构建议：从桌面端迁移至 Web 应用

> 版本：V1.0 | 更新日期：2026-03-23

## 1. 为什么要改

当前系统是一个 tkinter 桌面单体（`backend/main.py`，273 行），全部逻辑耦合在一个类中。
对照实际需求，存在以下 **不可调和的矛盾**：

| 需求 | 桌面端的困境 | Web 端如何解决 |
|------|-------------|---------------|
| 全校 1 万人使用 | 每台电脑需装 Python + 依赖 | 打开浏览器即用，零安装 |
| "充一个账号全部人使用" | API Key 暴露在客户端 | Key 仅在服务器，用户不可见 |
| 题库管理（Word/PDF 上传） | 无数据库，无文档解析 | 服务端存储 + 解析，全校共享 |
| 调用量统计与限流 | 无法实现 | 服务端中间件统一管控 |
| 拍照上传 | tkinter 的摄像头支持很弱 | 浏览器原生支持 `<input capture>` |
| 部署维护 | 逐台更新 | 服务端一处更新，全部生效 |

**结论**：即使代码质量再高，桌面架构也无法支撑"全校上线"这个核心目标。

---

## 2. 推荐技术栈

全部保持 **Python 生态**，团队无需学习新语言。

| 层 | 技术 | 选型理由 |
|----|------|---------|
| 后端框架 | **FastAPI** | 异步、自动生成 API 文档、类型安全、学习曲线低 |
| 数据库 | **SQLite**（开发）→ PostgreSQL（生产） | SQLite 零配置，单文件部署；后续按需切换 |
| ORM | **SQLModel** | FastAPI 作者出品，Pydantic + SQLAlchemy 合一 |
| 前端 | **原生 HTML + CSS + JS** | 无需 Node.js 工具链，团队成员直接上手 |
| 文档解析 | **python-docx** + **pdfplumber** | 解析 Word/PDF 中的题目与答案 |
| LLM 调用 | **httpx**（异步） | 替代 requests，不阻塞服务器 |
| 图像处理 | **Pillow** | 沿用现有依赖 |

### 新增依赖清单

```bash
pip install fastapi uvicorn sqlmodel httpx python-multipart python-docx pdfplumber pillow jinja2
```

---

## 3. 目录结构

```
question-judgment/
├── backend/
│   ├── main.py                 # FastAPI 入口，挂载路由 + 静态文件
│   ├── config.py               # 集中配置（env vars → Pydantic Settings）
│   ├── database.py             # SQLite/SQLModel 初始化
│   ├── models.py               # 数据模型（Question, Answer, JudgeResult）
│   ├── schemas.py              # 请求/响应的 Pydantic 模型
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── judge.py            # POST /api/judge — 提交判题
│   │   ├── question_bank.py    # CRUD /api/questions — 题库管理
│   │   └── upload.py           # POST /api/upload — 图片/文档上传
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_client.py       # LLM API 封装（httpx 异步调用）
│   │   ├── grading.py          # 判题核心逻辑 + prompt 工程
│   │   ├── doc_parser.py       # Word/PDF 解析 → 题目-答案对
│   │   └── question_matcher.py # 拍照题目 ↔ 题库答案匹配
│   └── utils/
│       ├── __init__.py
│       ├── image.py            # 图片压缩、base64 编码
│       └── latex.py            # LaTeX → 可读文本转换
├── frontend/
│   ├── index.html              # 主页面（判题）
│   ├── bank.html               # 题库管理页
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           ├── app.js          # 判题页逻辑
│           └── bank.js         # 题库页逻辑
├── data/                       # 运行时数据（.gitignore）
│   ├── db.sqlite               # 数据库文件
│   └── uploads/                # 上传的图片和文档
├── test/
│   ├── pdf/                    # 测试用样卷（已有）
│   ├── test_grading.py         # 判题服务单测
│   ├── test_doc_parser.py      # 文档解析单测
│   └── conftest.py             # pytest fixtures
├── docs/                       # 文档（已有）
├── requirements.txt            # 依赖锁定
├── .env.example                # 环境变量模板
├── .gitignore
├── AGENTS.md
└── README.md
```

---

## 4. 核心模块设计

### 4.1 数据模型（`models.py`）

```python
from sqlmodel import SQLModel, Field
from datetime import datetime

class Question(SQLModel, table=True):
    """题库中的题目"""
    id: int | None = Field(default=None, primary_key=True)
    content: str                    # 题面文本
    question_type: str              # fill_blank / short_answer / calculation
    standard_answer: str | None     # 标准答案（可选）
    source_file: str | None         # 来源文件名
    created_at: datetime = Field(default_factory=datetime.now)

class JudgeResult(SQLModel, table=True):
    """判题记录"""
    id: int | None = Field(default=None, primary_key=True)
    image_path: str                 # 上传图片路径
    question_type: str              # 识别出的题型
    recognized_content: str         # OCR 识别内容
    judgment: str                   # 正确/错误/部分正确
    score: float                    # 得分
    total_score: float              # 满分
    explanation: str                # 详细解析
    step_scores: str | None         # 过程分 JSON（计算题）
    matched_question_id: int | None # 匹配到的题库题目 ID
    created_at: datetime = Field(default_factory=datetime.now)
```

### 4.2 判题服务（`services/grading.py`）

核心改进：**结构化 prompt + 结构化输出解析**

```python
SYSTEM_PROMPT = """你是一名专业的高等数学阅卷老师。请严格按照 JSON 格式输出判题结果。

输出格式（纯 JSON，不要 markdown 代码块）：
{
  "question_type": "fill_blank|short_answer|calculation",
  "recognized_content": "识别出的题面和作答内容",
  "judgment": "correct|wrong|partial",
  "score": 8,
  "total_score": 10,
  "explanation": "判分理由",
  "steps": [
    {"step": "第一步：...", "correct": true, "score": 3, "comment": "正确"},
    {"step": "第二步：...", "correct": false, "score": 0, "comment": "符号错误"}
  ]
}"""

async def grade_image(
    image_base64: str,
    standard_answer: str | None = None,
) -> dict:
    """异步调用 LLM 判题，返回结构化结果"""
    ...
```

关键改进点：
- **JSON 输出**：让 LLM 返回结构化 JSON，而非自由文本，便于前端渲染和数据存储
- **过程分拆分**：`steps` 数组明确每一步的得分和点评，满足"可解释性和可交互性"要求
- **异步调用**：`httpx.AsyncClient` 不阻塞服务器，支持并发请求

### 4.3 文档解析（`services/doc_parser.py`）

满足"老师上传 Word 文档，自动配对题目和答案"的核心需求：

```python
async def parse_word_document(file_path: str) -> list[dict]:
    """
    解析 Word 文档，提取题目-答案对。
    
    支持的格式约定：
    - 题目以数字编号开头（1. / 1、/ （1）等）
    - 答案紧随题目后，或位于"答案"/"参考答案"标记之后
    
    Returns:
        [{"content": "题面", "answer": "标准答案", "type": "calculation"}, ...]
    """
    ...
```

### 4.4 API 路由设计（`routers/`）

```
POST   /api/judge              # 上传图片 + 可选答案 → 判题结果
POST   /api/judge/with-bank    # 上传图片 → 自动匹配题库答案 → 判题
GET    /api/results             # 查询历史判题记录
POST   /api/upload/document    # 上传 Word/PDF → 解析入库
GET    /api/questions           # 题库列表
POST   /api/questions           # 手动添加题目
DELETE /api/questions/{id}      # 删除题目
```

### 4.5 前端页面

只需 **两个 HTML 页面**，无需前端框架：

**判题页（`index.html`）**：
- 拍照/选择图片 → 预览 → 可选填写答案 / 选择"从题库匹配" → 提交 → 展示结构化结果
- 计算题结果渲染为步骤表格（每步得分 + 点评）

**题库页（`bank.html`）**：
- 上传 Word/PDF → 自动解析展示 → 确认入库
- 题目列表 → 搜索/筛选/删除
- 手动添加题目+答案

---

## 5. 部署方案

### 开发环境

```bash
# 安装依赖
pip install -r requirements.txt

# 启动（热重载）
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

浏览器打开 `http://localhost:8000` 即可使用。

### 生产环境（校内部署）

```bash
# 最简方案：一台校内服务器
uvicorn backend.main:app --host 0.0.0.0 --port 80 --workers 4
```

- 全校用户通过校园网访问 `http://判题系统服务器IP`
- API Key 仅在服务器 `.env` 中，不暴露给任何用户
- SQLite 单文件数据库，备份只需复制一个文件

### 进阶部署（可选）

```
Nginx（反向代理 + HTTPS）
  └─ uvicorn × 4 workers
       └─ SQLite → PostgreSQL（如果并发超过 50）
```

---

## 6. 迁移策略（7 天可行性）

现有代码中可直接复用的部分：

| 现有代码 | 迁移到 | 改动量 |
|---------|--------|-------|
| `_judge_exam()` 中的 prompt | `services/grading.py` | 低（改为 JSON 输出） |
| `_format_latex()` | `utils/latex.py` | 零（直接移动） |
| API 调用逻辑 | `services/llm_client.py` | 低（requests → httpx） |
| 配色方案 / UI 布局思路 | `frontend/static/css/` | 中（tkinter → HTML/CSS） |

### 建议分工

| 人员 | 职责 | 天数 |
|------|------|------|
| 胡经东 | 后端：FastAPI 框架 + LLM 服务 + 判题逻辑 | 5 天 |
| 李霖 | 前端：两个 HTML 页面 + JS 交互 | 4 天 |
| 王琛 | 架构搭建 + 文档解析服务 + 整体联调 | 5 天 |
| 徐全 | 测试：API 测试 + 端到端测试 | 3 天 |
| 钟佳明 | 文档 + 部署脚本 + 环境配置 | 3 天 |

---

## 7. 对比总结

| 维度 | 当前（tkinter 桌面端） | 推荐（FastAPI Web 端） |
|------|----------------------|----------------------|
| 部署 | 每台电脑装 Python | 一台服务器，浏览器访问 |
| API Key 安全 | 暴露在客户端 | 仅服务端持有 |
| 题库共享 | 不支持 | SQLite 集中存储 |
| Word/PDF 解析 | 不支持 | python-docx + pdfplumber |
| 并发 | 单用户 | uvicorn 多 worker |
| 过程分展示 | 纯文本 | 结构化 JSON → 表格渲染 |
| 调用量管控 | 不可能 | 中间件统计 + 限流 |
| 手机拍照 | 不支持 | 浏览器 `<input capture="camera">` |
| 团队学习成本 | — | FastAPI 与 Flask 相似，1 天上手 |

---

## 8. 风险与备选

| 风险 | 应对 |
|------|------|
| 团队不熟悉 FastAPI | FastAPI 文档极好，且与 Flask 语法相似；前 1 天可安排集中学习 |
| 前端开发经验不足 | 不用任何框架，纯 HTML + fetch API；可参考 FastAPI 官方 Jinja2 模板方案 |
| SQLite 并发性能 | 10,000 用户不会同时在线，SQLite WAL 模式足够；真不够再切 PostgreSQL |
| 7 天工期紧张 | 核心判题逻辑已有，迁移为主而非重写；先做判题页，题库管理可第二周迭代 |
