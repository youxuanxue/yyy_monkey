import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import sys
import logging
import json
import os
import queue
import time
from pathlib import Path

# 确保能找到模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wechat_gzh.config import CONFIG_DIR, PROJECT_DIR, LOG_DIR
from wechat_gzh.auto_comment import AutoCommentBot
from wechat_gzh.automation.utils import interrupt_handler
from wechat_gzh.automation.calibration import CalibrationManager

class TextHandler(logging.Handler):
    """
    Custom logging handler that sends log messages to a queue
    so they can be displayed in a tkinter ScrolledText widget.
    """
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("微信公众号自动评论机器人")
        self.root.geometry("900x700")
        
        # 居中显示
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = int((screen_width - 900) / 2)
        y = int((screen_height - 700) / 2)
        self.root.geometry(f"900x700+{x}+{y}")

        # 数据模型
        self.calibration_mgr = CalibrationManager(CONFIG_DIR)
        self.task_prompt_path = os.path.join(CONFIG_DIR, "task_prompt.json")
        
        # 线程控制
        self.bot_thread = None
        self.is_running = False
        
        # 日志队列
        self.log_queue = queue.Queue()
        
        # 初始化 UI
        self._init_ui()
        
        # 配置日志重定向
        self._setup_logging()
        
        # 定时检查日志队列
        self.root.after(100, self._process_log_queue)

    def _init_ui(self):
        # 创建 Tab 控件
        self.tab_control = ttk.Notebook(self.root)
        
        self.tab_run = ttk.Frame(self.tab_control)
        self.tab_settings = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.tab_run, text='运行控制')
        self.tab_control.add(self.tab_settings, text='参数配置')
        
        self.tab_control.pack(expand=1, fill="both")
        
        # === Tab 1: 运行控制 ===
        self._init_run_tab()
        
        # === Tab 2: 参数配置 ===
        self._init_settings_tab()

    def _init_run_tab(self):
        frame = ttk.Frame(self.tab_run, padding="10")
        frame.pack(fill="both", expand=True)
        
        # 控制按钮区域
        btn_frame = ttk.LabelFrame(frame, text="操作面板", padding="10")
        btn_frame.pack(fill="x", pady=(0, 10))
        
        self.btn_start = ttk.Button(btn_frame, text="启动自动评论", command=self.start_bot)
        self.btn_start.pack(side="left", padx=5)
        
        self.btn_stop = ttk.Button(btn_frame, text="停止运行", command=self.stop_bot, state="disabled")
        self.btn_stop.pack(side="left", padx=5)
        
        self.btn_verify = ttk.Button(btn_frame, text="验证位置校准 (生成截图)", command=self.verify_calibration)
        self.btn_verify.pack(side="right", padx=5)

        # 状态显示
        self.lbl_status = ttk.Label(btn_frame, text="状态: 就绪", foreground="green")
        self.lbl_status.pack(side="left", padx=20)
        
        # 日志输出区域
        log_frame = ttk.LabelFrame(frame, text="运行日志", padding="5")
        log_frame.pack(fill="both", expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=20)
        self.log_text.pack(fill="both", expand=True)
        # 配置 Tag 样式
        self.log_text.tag_config("INFO", foreground="black")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("DEBUG", foreground="gray")

    def _init_settings_tab(self):
        main_frame = ttk.Frame(self.tab_settings)
        main_frame.pack(fill="both", expand=True)
        
        # 使用 Canvas 实现滚动
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, padding="10")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # --- 提示词配置 ---
        prompt_frame = ttk.LabelFrame(scrollable_frame, text="AI 提示词配置 (System Prompt)", padding="10")
        prompt_frame.pack(fill="x", pady=(0, 10))
        
        self.txt_prompt = tk.Text(prompt_frame, height=8, wrap="word")
        self.txt_prompt.pack(fill="x", pady=5)
        
        # 加载提示词
        self._load_prompt_to_ui()
        
        # --- 模型配置 ---
        model_frame = ttk.LabelFrame(scrollable_frame, text="模型配置 (Ollama)", padding="10")
        model_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(model_frame, text="模型名称:").pack(side="left")
        self.entry_model = ttk.Entry(model_frame)
        self.entry_model.pack(side="left", fill="x", expand=True, padx=5)
        self.entry_model.insert(0, os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"))
        
        # --- 位置校准配置 ---
        calib_frame = ttk.LabelFrame(scrollable_frame, text="位置校准 (坐标配置)", padding="10")
        calib_frame.pack(fill="x", pady=(0, 10))
        
        self.calib_entries = {}
        
        # 加载现有校准数据
        if self.calibration_mgr.has_calibration():
            data = self.calibration_mgr.data
        else:
            # 使用默认值或空值
            # 这里先不实例化，等用户保存
            data = None

        def add_section(parent, title, key_prefix, fields):
            lf = ttk.LabelFrame(parent, text=title, padding="5")
            lf.pack(fill="x", pady=5)
            
            for field, label in fields:
                f_frame = ttk.Frame(lf)
                f_frame.pack(fill="x", pady=2)
                ttk.Label(f_frame, text=label, width=25).pack(side="left")
                entry = ttk.Entry(f_frame)
                entry.pack(side="left", fill="x", expand=True)
                
                full_key = f"{key_prefix}.{field}"
                self.calib_entries[full_key] = entry
                
                # 填充值
                if data:
                    section_obj = getattr(data, key_prefix)
                    val = getattr(section_obj, field)
                    entry.insert(0, str(val))

        # Navigator
        add_section(calib_frame, "导航器 (Navigator)", "navigator", [
            ("account_list_x", "公众号列表 X 坐标"),
            ("account_list_y_start", "第一项 Y 坐标"),
            ("account_item_height", "列表项高度"),
            ("article_area_x", "文章区域 X 坐标"),
            ("article_area_y", "文章区域 Y 坐标"),
        ])
        
        # OCR
        add_section(calib_frame, "OCR 识别区域", "ocr", [
            ("account_name_x", "公众号名称 X"),
            ("account_name_y", "公众号名称 Y"),
            ("account_name_width", "公众号名称 宽度"),
            ("account_name_height", "公众号名称 高度"),
            ("article_title_x", "文章标题 X"),
            ("article_title_y", "文章标题 Y"),
            ("article_title_width", "文章标题 宽度"),
            ("article_title_height", "文章标题 高度"),
        ])
        
        # Commenter
        add_section(calib_frame, "留言器 (Commenter)", "commenter", [
            ("comment_button_x", "留言按钮 X"),
            ("comment_button_y", "留言按钮 Y"),
            ("comment_input_x", "输入框 X"),
            ("comment_input_y", "输入框 Y"),
            ("send_button_x", "发送按钮 X"),
            ("send_button_y", "发送按钮 Y"),
        ])
        
        # 保存按钮
        btn_save = ttk.Button(scrollable_frame, text="保存所有配置", command=self.save_settings)
        btn_save.pack(pady=10)

    def _setup_logging(self):
        logger = logging.getLogger("wechat-gzh")
        handler = TextHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO) # 确保 GUI 显示 INFO 级别

    def _process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.configure(state='normal')
                
                # 简单的颜色处理
                tag = "INFO"
                if "ERROR" in msg: tag = "ERROR"
                elif "WARNING" in msg: tag = "WARNING"
                elif "DEBUG" in msg: tag = "DEBUG"
                
                self.log_text.insert(tk.END, msg + "\n", tag)
                self.log_text.see(tk.END)
                self.log_text.configure(state='disabled')
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._process_log_queue)

    def _load_prompt_to_ui(self):
        try:
            with open(self.task_prompt_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 兼容旧版本和新版本配置结构
                # 新版本: task_comment_generation.default.system_prompt
                # 旧版本: system_prompt
                prompt = ""
                if "task_comment_generation" in config:
                    prompt = config["task_comment_generation"]["default"]["system_prompt"]
                else:
                    prompt = config.get("system_prompt", "")
                
                self.txt_prompt.delete("1.0", tk.END)
                self.txt_prompt.insert("1.0", prompt)
        except Exception as e:
            messagebox.showerror("错误", f"加载 Prompt 失败: {e}")

    def save_settings(self):
        # 0. 保存模型配置到环境变量 (运行时生效，不持久化到文件，除非我们写入配置文件)
        model_name = self.entry_model.get().strip()
        if model_name:
            os.environ["OLLAMA_MODEL"] = model_name
            # 也可以考虑保存到 config.py 或新的 json 中，这里暂且只在运行时生效
            logging.info(f"已更新模型名称为: {model_name}")

        # 1. 保存 Prompt
        try:
            new_prompt = self.txt_prompt.get("1.0", tk.END).strip()
            with open(self.task_prompt_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            if "task_comment_generation" in config:
                config["task_comment_generation"]["default"]["system_prompt"] = new_prompt
            else:
                config["system_prompt"] = new_prompt
                
            with open(self.task_prompt_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            messagebox.showerror("错误", f"保存 Prompt 失败: {e}")
            return

        # 2. 保存 Calibration
        # 由于 CalibrationManager 封装较深，这里我们直接加载 json 修改然后保存
        # 或者更简单的：更新 calibration_mgr.data 然后 save()
        if not self.calibration_mgr.has_calibration():
            messagebox.showwarning("提示", "未找到初始校准文件，无法保存修改（请先运行一次程序生成默认配置）")
            return

        data = self.calibration_mgr.data
        try:
            for key, entry in self.calib_entries.items():
                section, field = key.split(".")
                val = int(entry.get())
                setattr(getattr(data, section), field, val)
            
            self.calibration_mgr.save(data)
            messagebox.showinfo("成功", "配置已保存")
        except ValueError:
            messagebox.showerror("错误", "坐标值必须是整数")
        except Exception as e:
            messagebox.showerror("错误", f"保存校准失败: {e}")

    def start_bot(self):
        if self.is_running:
            return
            
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.lbl_status.configure(text="状态: 运行中", foreground="blue")
        self.is_running = True
        
        # 重置中断标志
        interrupt_handler.reset()
        
        # 在新线程运行
        self.bot_thread = threading.Thread(target=self._run_bot_logic)
        self.bot_thread.daemon = True
        self.bot_thread.start()

    def _run_bot_logic(self):
        try:
            logging.info("正在初始化机器人... (这可能需要几秒钟启动 Ollama)")
            bot = AutoCommentBot()
            bot.run()
        except Exception as e:
            logging.error(f"运行出错: {e}")
        finally:
            # 无论如何，恢复 UI 状态
            self.root.after(0, self._on_bot_finished)

    def _on_bot_finished(self):
        self.is_running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.lbl_status.configure(text="状态: 已停止", foreground="black")
        logging.info("任务结束")

    def stop_bot(self):
        if self.is_running:
            logging.info("正在停止... 请等待当前操作完成")
            interrupt_handler.set_interrupted()
            # 按钮状态不需要立即变，等线程真正结束调用 _on_bot_finished

    def verify_calibration(self):
        if self.is_running:
            messagebox.showwarning("提示", "请先停止正在运行的任务")
            return
            
        def _verify():
            try:
                logging.info("正在生成校验截图...")
                bot = AutoCommentBot(verify_only=True)
                bot.run_verify_only()
                messagebox.showinfo("完成", f"截图已生成，请查看 logs 目录")
            except Exception as e:
                logging.error(f"校验失败: {e}")
                
        threading.Thread(target=_verify, daemon=True).start()

def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
