import os
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import requests
import base64
from PIL import Image, ImageTk

# ===================== 配置区 =====================
OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY", "sk-68ddd072fd08f5e9c5c6627e114745bf0aba7bd148b480b81aa8104661217673"
)  # 替换为真实Key，或通过环境变量传入
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.ethan0x0000.work/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# ====================================================

# 配色方案
COLOR_MAIN = "#165DFF"
COLOR_ASSIST = "#36CFC9"
COLOR_BG = "#F5F7FA"
COLOR_CARD = "#FFFFFF"
COLOR_TEXT = "#1D2129"
COLOR_TEXT_SEC = "#4E5969"


class ExamJudgeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📝 中小学智能判题系统")
        self.root.geometry("1100x800")
        self.root.minsize(800, 600)
        self.root.configure(bg=COLOR_BG)

        self.image_path = None
        self.img_tk = None  # 保存图片引用，防止被回收
        self._build_ui()

    def _build_ui(self):
        # ========== 顶部标题栏 ==========
        title_frame = tk.Frame(self.root, bg=COLOR_MAIN, height=80)
        title_frame.pack(fill=tk.X, padx=0, pady=0)
        title_frame.pack_propagate(False)

        title_label = tk.Label(
            title_frame,
            text="📸 中小学智能判题系统",
            font=("微软雅黑", 22, "bold"),
            bg=COLOR_MAIN,
            fg="white",
        )
        title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # ========== 主体容器（grid布局） ==========
        main_container = tk.Frame(self.root, bg=COLOR_BG)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        main_container.grid_columnconfigure(
            0, weight=3, minsize=420
        )  # 左侧操作区更宽一点
        main_container.grid_columnconfigure(1, weight=7)
        main_container.grid_rowconfigure(0, weight=1)

        # ==================== 左侧操作区 ====================
        left_frame = tk.Frame(main_container, bg=COLOR_CARD, bd=1, relief=tk.SOLID)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 15))

        # 1. 图片上传区域（核心修复：给预览区足够高度）
        img_title = tk.Label(
            left_frame,
            text="🖼️ 题目图片",
            font=("微软雅黑", 14, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        )
        img_title.pack(anchor=tk.W, padx=20, pady=(20, 10))

        # 修复：预览区域高度拉满，允许垂直扩展
        self.image_label = tk.Label(
            left_frame,
            text="请选择题目图片\n（拍照后上传）",
            font=("微软雅黑", 12),
            bg=COLOR_BG,
            fg=COLOR_TEXT_SEC,
            relief=tk.SUNKEN,
        )
        # 关键：fill=tk.BOTH + expand=True，让预览区占满可用高度
        self.image_label.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        btn_select = tk.Button(
            left_frame,
            text="📂 选择图片文件",
            font=("微软雅黑", 12, "bold"),
            bg=COLOR_ASSIST,
            fg="white",
            relief=tk.FLAT,
            command=self._select_image,
        )
        btn_select.pack(fill=tk.X, padx=20, pady=(0, 20))

        # 2. 标准答案区域
        ans_title = tk.Label(
            left_frame,
            text="✍️ 标准答案（可选）",
            font=("微软雅黑", 14, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        )
        ans_title.pack(anchor=tk.W, padx=20, pady=(0, 10))

        self.std_answer_text = scrolledtext.ScrolledText(
            left_frame, font=("微软雅黑", 11), bg=COLOR_BG, fg=COLOR_TEXT, height=5
        )
        self.std_answer_text.pack(fill=tk.X, padx=20, pady=(0, 10))

        tip_label = tk.Label(
            left_frame,
            text="提示：兼容多种写法，如 1/2 = 0.5",
            font=("微软雅黑", 9),
            bg=COLOR_CARD,
            fg=COLOR_TEXT_SEC,
        )
        tip_label.pack(anchor=tk.W, padx=20, pady=(0, 20))

        # 3. 提交按钮（固定显示）
        self.btn_submit = tk.Button(
            left_frame,
            text="✅ 提交并判题",
            font=("微软雅黑", 16, "bold"),
            bg=COLOR_MAIN,
            fg="white",
            relief=tk.RAISED,
            borderwidth=2,
            height=2,
            command=self._judge_exam,
        )
        self.btn_submit.pack(fill=tk.X, padx=20, pady=(0, 20))

        # ==================== 右侧结果区 ====================
        right_frame = tk.Frame(main_container, bg=COLOR_CARD, bd=1, relief=tk.SOLID)
        right_frame.grid(row=0, column=1, sticky="nsew")

        res_title = tk.Label(
            right_frame,
            text="📊 判题结果",
            font=("微软雅黑", 14, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
        )
        res_title.pack(anchor=tk.W, padx=20, pady=20)

        self.result_text = scrolledtext.ScrolledText(
            right_frame, font=("Consolas", 11), bg=COLOR_BG, fg=COLOR_TEXT, wrap=tk.WORD
        )
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

    def _select_image(self):
        """修复：图片缩放更大，预览区域完整显示"""
        file_path = filedialog.askopenfilename(
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp")], title="选择题目图片"
        )
        if not file_path:
            return

        self.image_path = file_path
        try:
            img = Image.open(file_path)
            # 修复：放大图片缩放尺寸，让预览更清晰
            img.thumbnail((390, 240))  # 最大宽度390，最大高度240，保持比例
            self.img_tk = ImageTk.PhotoImage(img)
            # 显示图片，背景改为白色，和卡片一致
            self.image_label.config(image=self.img_tk, text="", bg=COLOR_CARD)
        except Exception as e:
            messagebox.showwarning("预览提示", f"图片预览失败：{str(e)}")
            self.image_label.config(
                text=f"已选择：{os.path.basename(file_path)}", bg=COLOR_BG
            )

    def _format_latex(self, text):
        """LaTeX公式转纯文本，解决乱码"""
        text = text.replace(r"\frac{", "(").replace(r"}{", ")/(").replace(r"}", ")")
        text = text.replace(r"\sqrt{", "√(").replace(r"}", ")")
        text = text.replace(r"\pi", "π").replace(r"\\", "")
        return text

    def _judge_exam(self):
        if OPENAI_API_KEY == "你的OpenAI API Key":
            messagebox.showerror("配置错误", "请先填写 OpenAI-compatible API Key！")
            return
        if not self.image_path:
            messagebox.showerror("操作错误", "请先选择题目图片！")
            return

        self.btn_submit.config(state=tk.DISABLED, text="⏳ 判题中...")
        self.root.update()

        try:
            with open(self.image_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode("utf-8")

            standard_answer = self.std_answer_text.get(1.0, tk.END).strip()
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, "📡 正在提交判题请求，请稍候...\n")
            self.root.update()

            prompt = """请你作为专业的中小学学科判题老师，严格按以下规则判题：
1. 识别题型（填空/简答/计算），自主判断正误（有标准答案则按答案核对）；
2. 计算题必须拆分过程分，填空题/简答题精准判断；
3. 输出格式（不要额外内容）：
   - 【题型】：xxx
   - 【识别内容】：xxx
   - 【正误判断】：正确/错误/部分正确
   - 【得分】：x分（满分10分）
   - 【详细解析】：xxx

标准答案（可选）：{}""".format(standard_answer if standard_answer else "无")

            request_url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}",
            }
            payload = {
                "model": OPENAI_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}",
                                    "detail": "auto",
                                },
                            },
                        ],
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 2000,
            }

            response = requests.post(
                request_url, headers=headers, json=payload, timeout=30
            )
            response.raise_for_status()
            result = response.json()
            judge_result = result["choices"][0]["message"]["content"]

            formatted_result = self._format_latex(judge_result)

            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, "===== 📝 提交成功 - 判题结果 =====\n\n")
            self.result_text.insert(tk.END, formatted_result)
            self.result_text.see(tk.END)

        except requests.exceptions.RequestException as e:
            error_info = f"❌ 提交失败：{str(e)}"
            response = e.response
            if response is not None:
                error_info += f"\n响应详情：{response.text}"
            self.result_text.insert(tk.END, error_info)
        except Exception as e:
            self.result_text.insert(tk.END, f"❌ 提交失败：{str(e)}")
        finally:
            self.btn_submit.config(state=tk.NORMAL, text="✅ 提交并判题")
            self.root.update()


if __name__ == "__main__":
    # 安装依赖：pip install requests pillow
    root = tk.Tk()
    app = ExamJudgeApp(root)
    root.mainloop()
