# 智能判题系统

基于多模态大模型的中小学智能判题桌面应用，支持拍照上传题目图片，自动识别题型并完成评分。

## 技术栈

- **语言**：Python 3.10+
- **桌面框架**：tkinter
- **网络请求**：requests
- **图像处理**：Pillow
- **智能判题**：OpenAI 兼容接口（多模态 Chat Completions）

## 快速开始

### 1. 安装依赖

```bash
pip install requests pillow
```

### 2. 配置环境变量

系统通过环境变量读取 API 配置，请在运行前设置：

```bash
# Linux / macOS
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.ethan0x0000.work/v1"   # 可选，已有默认值
export OPENAI_MODEL="gpt-4o-mini"                           # 可选，已有默认值

# Windows (PowerShell)
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_BASE_URL="https://api.ethan0x0000.work/v1"
$env:OPENAI_MODEL="gpt-4o-mini"

# Windows (CMD)
set OPENAI_API_KEY=your-api-key
set OPENAI_BASE_URL=https://api.ethan0x0000.work/v1
set OPENAI_MODEL=gpt-4o-mini
```

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_API_KEY` | LLM 服务 API Key | — （必填） |
| `OPENAI_BASE_URL` | API 基地址 | `https://api.ethan0x0000.work/v1` |
| `OPENAI_MODEL` | 模型标识符 | `gpt-4o-mini` |

### 3. 启动应用

```bash
python backend/main.py
```

启动后将打开桌面窗口，按照界面提示上传题目图片并提交判题。

## 项目结构

```
question-judgment/
├── backend/              # 后端应用代码
│   └── main.py           # 程序入口，GUI + 判题逻辑
├── frontend/             # 前端（预留，暂未使用）
├── test/                 # 测试资源
│   └── pdf/              # 样卷与标准答案（PDF）
├── docs/                 # 项目文档
│   ├── request/          # 需求方原始要求
│   ├── reply/            # 需求规格说明书
│   └── 国内模型收费标准.md
├── AGENTS.md             # AI 编程代理参考文档
├── README.md             # 本文件
└── .gitignore
```

## 功能概述

| 功能 | 说明 |
|------|------|
| 图片上传与预览 | 支持 PNG / JPG / JPEG / BMP 格式，上传后即时预览 |
| 标准答案输入 | 可选填写标准答案，辅助校准判分 |
| 智能判题 | 调用多模态大模型识别题型、判断正误、输出评分与解析 |
| 题型支持 | 填空题、简答题、计算题（含过程分） |
| LaTeX 转换 | 将公式转为可读纯文本，避免乱码 |
| 防重复提交 | 判题期间禁用按钮，完成后自动恢复 |

## 开发指南

### 代码规范

详细规范见 [AGENTS.md](./AGENTS.md)，以下为核心要点：

- **命名**：类 `PascalCase`，函数/变量 `snake_case`，常量 `UPPER_SNAKE_CASE`
- **缩进**：4 空格
- **引号**：双引号 `"`
- **导入顺序**：标准库 → 第三方库 → 本地模块，各组之间空一行
- **类型标注**：新增函数必须添加参数和返回值类型标注
- **错误处理**：禁止裸 `except:`，必须指定异常类型

### Lint / 格式化（推荐）

项目尚未配置 Lint 工具，推荐使用 [Ruff](https://docs.astral.sh/ruff/)：

```bash
pip install ruff
ruff check .          # 检查
ruff check --fix .    # 自动修复
ruff format .         # 格式化
```

### 测试（推荐）

项目尚未配置测试框架，推荐使用 [pytest](https://docs.pytest.org/)：

```bash
pip install pytest
pytest test/                                 # 运行全部测试
pytest test/test_something.py                # 运行单个文件
pytest test/test_something.py::test_name     # 运行单个用例
pytest -x                                    # 遇到失败立即停止
```

### Git 提交规范

```
feat:     新功能
fix:      修复缺陷
docs:     文档变更
refactor: 重构（不改变外部行为）
test:     测试相关
chore:    构建、依赖等杂项
```

分支命名：`feature/xxx`、`fix/xxx`、`docs/xxx`

## 安全须知

- **禁止** 在源码中硬编码 API Key，一律通过环境变量传入
- 如使用 `.env` 文件管理本地配置，务必将其加入 `.gitignore`

## 相关文档

- [AGENTS.md](./AGENTS.md) — AI 编程代理完整参考
- [需求规格说明书](./docs/reply/需求规格说明书.md) — 系统功能与非功能需求
- [国内模型收费标准](./docs/国内模型收费标准.md) — API 选型与成本分析

## License

内部项目，暂未设定开源协议。
