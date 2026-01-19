import logging
import os
import sys
import threading
import queue
import json
from nicegui import ui

# 确保能找到模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wechat_gzh.config import CONFIG_DIR, PROJECT_DIR, LOG_DIR
from wechat_gzh.auto_comment import AutoCommentBot
from wechat_gzh.automation.utils import interrupt_handler
from wechat_gzh.automation.calibration import CalibrationManager

# === 日志处理 ===
class QueueHandler(logging.Handler):
    """将日志发送到队列"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

class StreamToLogger:
    """Redirect stdout/stderr to logger"""
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass

class WebApp:
    def __init__(self):
        self.calibration_mgr = CalibrationManager(CONFIG_DIR)
        self.task_prompt_path = os.path.join(CONFIG_DIR, "task_prompt.json")
        
        # 状态控制
        self.is_running = False
        self.bot_thread = None
        self.log_queue = queue.Queue()
        self.notify_queue = queue.Queue()  # 用于线程安全的通知
        
        # 按钮状态绑定变量
        self.start_enabled = True
        self.stop_enabled = False
        
        # UI 元素引用 (在 build_ui 中初始化)
        self.log_view = None
        self.status_label = None
        self.btn_start = None
        self.btn_stop = None
        
        # 配置数据绑定
        self.prompt_text = ""
        self.model_name = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self.calib_values = {}

        # 加载初始数据
        self._load_prompt()
        self._load_calibration()
        
        # 设置日志拦截
        self._setup_logging()

    def _setup_logging(self):
        # 配置根 logger，这样所有子 logger 的日志都会被捕获
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # 清除已有的 QueueHandler 避免重复
        for h in root_logger.handlers[:]:
            if isinstance(h, QueueHandler):
                root_logger.removeHandler(h)
        
        # 添加队列处理器到根 logger
        handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        
        # 同时配置 wechat-gzh logger（保持兼容）
        app_logger = logging.getLogger("wechat-gzh")
        app_logger.setLevel(logging.INFO)
        
        # 重定向 stdout 到 logger，以便捕获 print 输出
        # 注意：这会影响所有 print，包括 nicegui 自己的，可能导致递归，需小心
        # 这里只在 start_bot 时开启，或者只在 bot 线程中替换？
        # 简单起见，我们修改 bot 逻辑中的 print 为 logger 可能更好。
        # 但如果不修改 bot 代码，可以使用 context manager 在线程中替换 sys.stdout
        pass

    def _load_prompt(self):
        try:
            if os.path.exists(self.task_prompt_path):
                with open(self.task_prompt_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if "task_comment_generation" in config:
                        self.prompt_text = config["task_comment_generation"]["default"]["system_prompt"]
                    else:
                        self.prompt_text = config.get("system_prompt", "")
        except Exception as e:
            logging.error(f"加载 Prompt 失败: {e}")

    def _load_calibration(self):
        if self.calibration_mgr.has_calibration():
            data = self.calibration_mgr.data
            # 扁平化数据以便绑定
            self._fill_calib_dict("navigator", data.navigator)
            self._fill_calib_dict("ocr", data.ocr)

    def _fill_calib_dict(self, section, obj):
        for field in dir(obj):
            if not field.startswith("_"):
                val = getattr(obj, field)
                if isinstance(val, (int, float, str)):
                    self.calib_values[f"{section}.{field}"] = val

    def save_settings(self):
        # 1. 保存模型
        if self.model_name:
            os.environ["OLLAMA_MODEL"] = self.model_name.strip()
            ui.notify(f"模型名称已更新为: {self.model_name}")

        # 2. 保存 Prompt
        try:
            with open(self.task_prompt_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            new_prompt = self.prompt_text
            if "task_comment_generation" in config:
                config["task_comment_generation"]["default"]["system_prompt"] = new_prompt
            else:
                config["system_prompt"] = new_prompt
                
            with open(self.task_prompt_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            ui.notify("Prompt 已保存")
        except Exception as e:
            ui.notify(f"保存 Prompt 失败: {e}", type="negative")

        # 3. 保存校准
        if not self.calibration_mgr.has_calibration():
            ui.notify("未找到初始校准文件，无法保存修改", type="warning")
            return

        data = self.calibration_mgr.data
        try:
            for key, val in self.calib_values.items():
                section, field = key.split(".")
                # 确保是整数
                setattr(getattr(data, section), field, int(val))
            
            self.calibration_mgr.save(data)
            ui.notify("校准配置已保存", type="positive")
        except Exception as e:
            ui.notify(f"保存校准失败: {e}", type="negative")

    # --- 任务控制 ---
    def start_bot(self):
        if self.is_running: return
        
        self.is_running = True
        
        # 更新按钮状态（通过绑定变量）
        self.start_enabled = False
        self.stop_enabled = True
        
        if self.status_label:
            self.status_label.text = "状态: 运行中 🟢"
            self.status_label.classes(replace="text-lg font-bold text-green-500")
        
        if self.log_view:
            self.log_view.push("=== 任务启动 ===")
        
        interrupt_handler.reset()
        
        self.bot_thread = threading.Thread(target=self._run_bot_logic, daemon=True)
        self.bot_thread.start()

    def stop_bot(self):
        if self.is_running:
            if self.log_view:
                self.log_view.push("正在停止... 请等待当前操作完成")
            interrupt_handler.set_interrupted()

    def verify_calibration(self):
        if self.is_running:
            ui.notify("请先停止正在运行的任务", type="warning")
            return
            
        def _verify():
            try:
                logging.info("正在生成校验截图...")
                bot = AutoCommentBot(verify_only=True)
                bot.run_verify_only()
                self._safe_notify("截图已生成，请查看 logs 目录", "positive")
            except Exception as e:
                logging.error(f"校验失败: {e}")
                self._safe_notify(f"校验失败: {e}", "negative")

        threading.Thread(target=_verify, daemon=True).start()

    def _run_bot_logic(self):
        try:
            logging.info("正在初始化机器人... (这可能需要几秒钟启动 Ollama)")
            bot = AutoCommentBot()
            bot.run()
        except Exception as e:
            logging.error(f"运行出错: {e}")
        finally:
            self.is_running = False
            # 在结束时手动更新一次 UI 状态
            self._update_ui_state()

    def _process_log_queue(self):
        # 处理日志
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            if self.log_view:
                self.log_view.push(msg)
        
        # 处理通知队列（线程安全的 UI 更新）
        while not self.notify_queue.empty():
            notify_item = self.notify_queue.get()
            message = notify_item.get("message", "")
            notify_type = notify_item.get("type", "info")
            ui.notify(message, type=notify_type)
    
    def _safe_notify(self, message: str, notify_type: str = "info"):
        """线程安全的通知方法，将通知放入队列，由主线程处理"""
        self.notify_queue.put({"message": message, "type": notify_type})

    def _update_ui_state(self):
        # 更新 UI 状态（通过绑定变量控制按钮）
        try:
            if self.is_running:
                # 运行中：禁用启动按钮，启用停止按钮
                self.start_enabled = False
                self.stop_enabled = True
                if self.status_label:
                    self.status_label.text = "状态: 运行中 🟢"
                    self.status_label.classes(replace="text-lg font-bold text-green-500")
            else:
                # 已停止：启用启动按钮，禁用停止按钮
                self.start_enabled = True
                self.stop_enabled = False
                if self.status_label:
                    self.status_label.text = "状态: 就绪 ⚪"
                    self.status_label.classes(replace="text-lg font-bold text-grey-500")
        except Exception as e:
            pass  # 静默失败，避免日志刷屏

    def build_ui(self):
        with ui.header().classes(replace='row items-center') as header:
            ui.icon('smart_toy', size='md')
            ui.label('微信公众号自动评论机器人').classes('text-h6')

        with ui.tabs().classes('w-full') as tabs:
            tab_run = ui.tab('运行控制')
            tab_settings = ui.tab('参数配置')

        with ui.tab_panels(tabs, value=tab_run).classes('w-full p-4'):
            # === Tab 1: 运行控制 ===
            with ui.tab_panel(tab_run):
                with ui.row().classes('w-full items-center gap-4 mb-4'):
                    with ui.card():
                        with ui.row().classes('items-center'):
                            self.btn_start = ui.button('启动自动评论', on_click=self.start_bot, icon='play_arrow').props('color=primary').bind_enabled_from(self, 'start_enabled')
                            self.btn_stop = ui.button('停止运行', on_click=self.stop_bot, icon='stop').props('color=negative').bind_enabled_from(self, 'stop_enabled')
                            self.btn_verify = ui.button('验证校准 (生成截图)', on_click=self.verify_calibration, icon='screenshot').props('outline')
                    
                    self.status_label = ui.label('状态: 就绪 ⚪').classes('text-lg font-bold text-grey-500')

                ui.label('运行日志:').classes('font-bold mt-2')
                # Log 区域
                self.log_view = ui.log(max_lines=1000).classes('w-full h-96 bg-gray-100 rounded p-2 font-mono text-sm border')

            # === Tab 2: 参数配置 ===
            with ui.tab_panel(tab_settings):
                with ui.column().classes('w-full gap-4'):
                    # Prompt 配置
                    with ui.card().classes('w-full'):
                        ui.label('AI 提示词配置 (System Prompt)').classes('text-lg font-bold')
                        ui.textarea(label='System Prompt', value=self.prompt_text).bind_value(self, 'prompt_text').classes('w-full').props('rows=6')

                    # 模型配置
                    with ui.card().classes('w-full'):
                        ui.label('模型配置 (Ollama)').classes('text-lg font-bold')
                        ui.input(label='模型名称', value=self.model_name).bind_value(self, 'model_name').classes('w-full')

                    # 校准配置
                    with ui.card().classes('w-full'):
                        ui.label('位置校准 (坐标配置)').classes('text-lg font-bold')
                        with ui.row().classes('w-full wrap gap-4'):
                            # Navigator
                            self._build_calib_section("导航器 (Navigator)", "navigator", [
                                ("account_list_x", "公众号列表 X"),
                                ("account_list_y_start", "第一项 Y"),
                                ("account_item_height", "列表项高度"),
                                ("article_area_x", "文章区域 X"),
                                ("article_area_y", "文章区域 Y"),
                            ])
                            
                            # OCR
                            self._build_calib_section("OCR 识别区域", "ocr", [
                                ("account_name_x", "公众号名称 X"),
                                ("account_name_y", "公众号名称 Y"),
                                ("account_name_width", "名称宽"),
                                ("account_name_height", "名称高"),
                                ("article_title_x", "文章标题 X"),
                                ("article_title_y", "文章标题 Y"),
                                ("article_title_width", "标题宽"),
                                ("article_title_height", "标题高"),
                            ])

                    ui.button('保存所有配置', on_click=self.save_settings, icon='save').classes('w-full').props('color=secondary')

        # 启动定时器处理日志和状态
        ui.timer(0.1, self._process_log_queue)

    def _build_calib_section(self, title, key_prefix, fields):
        with ui.column().classes('border p-2 rounded'):
            ui.label(title).classes('font-bold text-gray-600')
            for field, label in fields:
                full_key = f"{key_prefix}.{field}"
                # 使用 bind_value_to 绑定字典中的值
                # 注意：nicegui 绑定字典需要特殊的写法，或者直接在保存时读取
                # 这里我们简化，直接使用 input 并且手动同步或者使用 lambda
                with ui.row().classes('items-center'):
                    ui.label(label).classes('w-32 text-sm')
                    # 初始化值
                    val = self.calib_values.get(full_key, 0)
                    ui.number(value=val).bind_value(self.calib_values, full_key).props('dense outlined').classes('w-24')

# 启动应用
def main():
    # 允许在非主线程运行 (对于某些打包情况)
    # reload=False 适合生产/打包
    app_instance = WebApp()
    app_instance.build_ui()
    # native=True 会尝试打开为独立窗口模式 (类似 Electron 体验)，如果失败会退化为浏览器
    # port=native 自动选择端口
    ui.run(title="微信公众号自动评论机器人", native=False, reload=False, port=8080)

if __name__ in {"__main__", "__mp_main__"}:
    main()
