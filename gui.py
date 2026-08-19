"""
同声传译 GUI 主程序
支持：双向翻译、即按即说(PTT)、自定义快捷键(支持组合键)、实时日志、后台加载模型、静音控制

用法：
  python gui.py
"""
import os
import sys
import json
import time
import queue
import threading
import ctypes


def _disable_quickedit():
    """关闭 Windows 控制台的快速编辑模式，防止后台假死"""
    if sys.platform != "win32":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        hStdin = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        if hStdin == -1 or hStdin == 0:
            return
        mode = ctypes.c_uint()
        if not kernel32.GetConsoleMode(hStdin, ctypes.byref(mode)):
            return
        new_mode = (mode.value & ~0x0040) | 0x0080
        kernel32.SetConsoleMode(hStdin, new_mode)
    except Exception:
        pass


_disable_quickedit()

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime

import keyboard

# ========== PyInstaller 资源路径兼容 ==========
def resource_path(relative_path):
    """获取资源文件的绝对路径，兼容 PyInstaller 打包后的临时目录"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# 把项目目录加入路径，确保能 import 现有模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LANG_MAP
from audio_io import AudioStreamer, get_default_mic_device, get_default_loopback_device, list_devices
from vad import Segmenter
from local_asr import LocalASR
from local_mt import LocalTranslator
from local_tts import LocalTTS
from playback import play_pcm, gate, toggle_pause_tts, is_tts_paused

# Whisper 语言代码映射
WHISPER_LANG = {
    "zh-CN": "zh", "cs-CZ": "cs", "ru-RU": "ru",
    "en-US": "en", "ja-JP": "ja", "es-ES": "es", "de-DE": "de",
    "uk-UA": "uk", "el-GR": "el", "bg-BG": "bg", "ro-RO": "ro",
    "sr-RS": "sr", "sq-AL": "sq", "pl-PL": "pl", "fr-FR": "fr",
}

# Piper 路径（使用 resource_path 兼容打包）
PIPER_EXE = resource_path("piper/piper.exe")
VOICE_MODELS = {
    "zh-CN": resource_path("voices/zh_CN-huayan-medium.onnx"),
    "cs-CZ": resource_path("voices/cs_CZ-jirka-medium.onnx"),
    "ru-RU": resource_path("voices/ru_RU-irina-medium.onnx"),
    "en-US": resource_path("voices/en_US-lessac-medium.onnx"),
    "ja-JP": resource_path("voices/ja_JP-shirou-medium.onnx"),
    "es-ES": resource_path("voices/es_ES-davefx-medium.onnx"),
    "de-DE": resource_path("voices/de_DE-thorsten-medium.onnx"),
    "uk-UA": resource_path("voices/uk_UA-ukrainian_tts-medium.onnx"),
    "el-GR": resource_path("voices/el_GR-rapunzelina-low.onnx"),
    "bg-BG": resource_path("voices/bg_BG-dimitar-medium.onnx"),
    "ro-RO": resource_path("voices/ro_RO-mihai-medium.onnx"),
    "sr-RS": resource_path("voices/sr_RS-serbski_institut-medium.onnx"),
    "sq-AL": resource_path("voices/sq_AL-LanguageWeaver-medium.onnx"),
    "pl-PL": resource_path("voices/pl_PL-gosia-medium.onnx"),
    "fr-FR": resource_path("voices/fr_FR-siwis-medium.onnx"),
}

# 配置文件路径
SETTINGS_FILE = "settings.json"

# 默认快捷键配置
DEFAULT_HOTKEYS = {
    "ptt_mic": "space",
    "ptt_loopback": "ctrl",
    "toggle_mode": "f1",
    "start_stop": "f2",
    "clear_log": "f3",
    "mute_mic": "f5",
    "mute_loopback": "f6",
    "pause_tts": "f7",
}

# 语言显示名称
LANG_NAMES = {
    "cs": "捷克语", "ru": "俄语", "en": "英语",
    "ja": "日语", "es": "西班牙语", "de": "德语",
    "uk": "乌克兰语", "el": "希腊语",
    "bg": "保加利亚语", "ro": "罗马尼亚语", "sr": "塞尔维亚语",
    "sq": "阿尔巴尼亚语", "pl": "波兰语", "fr": "法语",
}


def load_settings():
    """加载配置文件"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "my_lang": "zh",
        "target_lang": "ru",
        "mode": "both",
        "model_size": "medium",
        "ptt_enabled": False,
        "hotkeys": DEFAULT_HOTKEYS.copy(),
        "window_geometry": "900x700+100+100",
    }


def save_settings(settings):
    """保存配置文件"""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


# 全局 PTT 事件
_ptt_pressed_mic = threading.Event()
_ptt_pressed_loopback = threading.Event()
_ptt_mode = threading.Event()

# 全局静音事件
_mute_mic = threading.Event()
_mute_loopback = threading.Event()


# ==================== 核心翻译逻辑 ====================

class TranslationPipeline:
    """翻译管道，适配 GUI 的日志和状态回调"""

    def __init__(self, src_lang, tgt_lang, label, asr, mt,
                 ptt_event=None, mute_event=None, log_callback=None, status_callback=None):
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.label = label
        self.asr = asr
        self.mt = mt
        self.tts = LocalTTS(PIPER_EXE, VOICE_MODELS.get(tgt_lang, VOICE_MODELS["en-US"]))
        self.segmenter = Segmenter(on_utterance=self._on_utterance)
        self._q = queue.Queue()

        self.ptt_event = ptt_event
        self.mute_event = mute_event
        self._ptt_buffer = bytearray()
        self._ptt_lock = threading.Lock()

        self.log_callback = log_callback
        self.status_callback = status_callback
        self._running = True
        self._audio_count = 0

        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def push_audio(self, pcm_bytes):
        # 如果该方向被静音，直接丢弃音频
        if self.mute_event and self.mute_event.is_set():
            return

        if gate.is_active():
            return
        if self.ptt_event and self.ptt_event.is_set():
            if _ptt_pressed_mic.is_set() if self.ptt_event == _ptt_pressed_mic else _ptt_pressed_loopback.is_set():
                with self._ptt_lock:
                    self._ptt_buffer.extend(pcm_bytes)
            return

        self._audio_count += 1
        if self._audio_count % 100 == 0 and self.log_callback:
            self.log_callback(f"[DEBUG] {self.label} 收到音频 #{self._audio_count}")

        self.segmenter.feed(pcm_bytes)

    def ptt_flush(self):
        with self._ptt_lock:
            pcm = bytes(self._ptt_buffer)
            self._ptt_buffer.clear()
        min_bytes = int(16000 * 0.15 * 2)
        if len(pcm) >= min_bytes:
            self._q.put(pcm)
            if self.status_callback:
                self.status_callback(f"[{self.label}] 处理中...")
        else:
            if self.status_callback:
                self.status_callback(f"[{self.label}] 音频太短，已忽略")

    def _on_utterance(self, pcm_bytes):
        if self.log_callback:
            self.log_callback(f"[DEBUG] {self.label} VAD触发, {len(pcm_bytes)} bytes")
        self._q.put(pcm_bytes)

    def _run(self):
        while self._running:
            try:
                pcm_bytes = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if self.log_callback:
                    self.log_callback(f"[DEBUG] {self.label} ASR开始识别, {len(pcm_bytes)} bytes")

                text = self.asr.transcribe(pcm_bytes, WHISPER_LANG[self.src_lang])

                if self.log_callback:
                    self.log_callback(f"[DEBUG] {self.label} ASR结果: '{text}'")

                if not text:
                    continue

                translation = self.mt.translate(text, self.src_lang, self.tgt_lang)
                log_msg = f"[{self.label}] {text} -> {translation}"
                if self.log_callback:
                    self.log_callback(log_msg)

                if translation:
                    pcm, rate = self.tts.synthesize_to_pcm(translation)
                    play_pcm(pcm, rate)
            except Exception as e:
                if self.log_callback:
                    self.log_callback(f"[{self.label}] 错误: {e}")

    def stop(self):
        self._running = False


# ==================== GUI ====================

class LoadingDialog(tk.Toplevel):
    """加载中模态对话框"""

    def __init__(self, parent, title="加载中"):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x120")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        self.label = ttk.Label(self, text="正在加载模型，请稍候...", font=("Microsoft YaHei", 12))
        self.label.pack(pady=10)

        self.progress = ttk.Progressbar(self, mode="indeterminate", length=350)
        self.progress.pack(pady=5)
        self.progress.start(15)

        self.detail = ttk.Label(self, text="", font=("Microsoft YaHei", 9), foreground="#666666")
        self.detail.pack(pady=5)

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def set_detail(self, text):
        self.detail.config(text=text)
        self.update()


class HotkeyCaptureDialog(tk.Toplevel):
    """快捷键捕获对话框"""

    def __init__(self, parent, current_key, title="设置快捷键"):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x150")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.captured_key = None
        self.listening = True

        ttk.Label(self, text=f"当前快捷键: {current_key}", font=("Microsoft YaHei", 11)).pack(pady=10)
        self.hint = ttk.Label(self, text="请按下新的组合键...", font=("Microsoft YaHei", 12, "bold"))
        self.hint.pack(pady=5)

        ttk.Button(self, text="取消", command=self._on_close).pack(pady=10)

        self._hook = keyboard.hook(self._on_key)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _on_key(self, event):
        if not self.listening:
            return
        if event.name in ("left ctrl", "right ctrl", "left shift", "right shift",
                          "left alt", "right alt", "left windows", "right windows"):
            return

        parts = []
        if keyboard.is_pressed("ctrl") or keyboard.is_pressed("left ctrl") or keyboard.is_pressed("right ctrl"):
            parts.append("ctrl")
        if keyboard.is_pressed("shift") or keyboard.is_pressed("left shift") or keyboard.is_pressed("right shift"):
            parts.append("shift")
        if keyboard.is_pressed("alt") or keyboard.is_pressed("left alt") or keyboard.is_pressed("right alt"):
            parts.append("alt")
        parts.append(event.name)

        self.captured_key = "+".join(parts)
        self.hint.config(text=f"已捕获: {self.captured_key}", foreground="green")
        self.listening = False
        self.after(500, self._on_close)

    def _on_close(self):
        self.listening = False
        try:
            keyboard.unhook(self._hook)
        except Exception:
            pass
        self.destroy()


class SettingsWindow(tk.Toplevel):
    """设置窗口"""

    def __init__(self, parent, settings, on_save):
        super().__init__(parent)
        self.title("设置")
        self.geometry("520x580")
        self.resizable(False, False)
        self.transient(parent)
        self.settings = settings
        self.on_save = on_save

        frame_hotkeys = ttk.LabelFrame(self, text="快捷键设置（支持组合键如 ctrl+shift+a）", padding=10)
        frame_hotkeys.pack(fill=tk.X, padx=10, pady=5)

        self.hotkey_entries = {}
        hotkey_labels = {
            "ptt_mic": "我方说话 (中->外)",
            "ptt_loopback": "对方说话 (外->中)",
            "toggle_mode": "切换 PTT/连续模式",
            "start_stop": "开始/停止翻译",
            "clear_log": "清空日志",
            "mute_mic": "静音/开启麦克风",
            "mute_loopback": "静音/开启扬声器",
            "pause_tts": "暂停/恢复朗读",
        }

        for i, (key, label) in enumerate(hotkey_labels.items()):
            ttk.Label(frame_hotkeys, text=label, width=22).grid(row=i, column=0, sticky=tk.W, pady=4)
            entry = ttk.Entry(frame_hotkeys, width=22)
            entry.insert(0, settings["hotkeys"].get(key, DEFAULT_HOTKEYS[key]))
            entry.grid(row=i, column=1, padx=5)
            entry.config(state="readonly")
            self.hotkey_entries[key] = entry

            btn = ttk.Button(frame_hotkeys, text="修改", width=8,
                             command=lambda e=entry, k=key: self._capture_hotkey(e, k))
            btn.grid(row=i, column=2, padx=5)

        frame_other = ttk.LabelFrame(self, text="其他设置", padding=10)
        frame_other.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(frame_other, text="语音识别模型:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.model_var = tk.StringVar(value=settings.get("model_size", "medium"))
        ttk.Combobox(frame_other, textvariable=self.model_var,
                     values=["tiny", "base", "small", "medium", "large-v3"], width=15).grid(row=0, column=1, padx=5)

        ttk.Label(frame_other, text="启动模式:").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.start_mode_var = tk.StringVar(value=settings.get("mode", "both"))
        ttk.Combobox(frame_other, textvariable=self.start_mode_var,
                     values=["mic", "loopback", "both"], width=15).grid(row=1, column=1, padx=5)

        self.ptt_var = tk.BooleanVar(value=settings.get("ptt_enabled", False))
        ttk.Checkbutton(frame_other, text="默认启用 PTT 模式", variable=self.ptt_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=4)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="保存", command=self._save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="恢复默认", command=self._reset).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=5)

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _capture_hotkey(self, entry, key_name):
        dialog = HotkeyCaptureDialog(self, entry.get(), title=f"设置: {key_name}")
        self.wait_window(dialog)
        if dialog.captured_key:
            entry.config(state="normal")
            entry.delete(0, tk.END)
            entry.insert(0, dialog.captured_key)
            entry.config(state="readonly")

    def _save(self):
        new_hotkeys = {k: v.get() for k, v in self.hotkey_entries.items()}
        self.settings["hotkeys"] = new_hotkeys
        self.settings["model_size"] = self.model_var.get()
        self.settings["mode"] = self.start_mode_var.get()
        self.settings["ptt_enabled"] = self.ptt_var.get()
        save_settings(self.settings)
        if self.on_save:
            self.on_save(self.settings)
        self.destroy()

    def _reset(self):
        for k, v in self.hotkey_entries.items():
            v.config(state="normal")
            v.delete(0, tk.END)
            v.insert(0, DEFAULT_HOTKEYS[k])
            v.config(state="readonly")
        self.model_var.set("medium")
        self.start_mode_var.set("both")
        self.ptt_var.set(False)


class TranslatorGUI:
    """主 GUI 界面"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("同声传译 - 本地离线版")
        self.settings = load_settings()
        self.root.geometry(self.settings.get("window_geometry", "900x700+100+100"))

        self.asr = None
        self.mt = None
        self.mic_pipeline = None
        self.loopback_pipeline = None
        self.streamers = []
        self._running = False
        self._hotkey_hooks = []
        self._ptt_states = {}
        self._loading_dialog = None

        self._build_ui()
        self._apply_hotkeys()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(fill=tk.X)

        ttk.Label(toolbar, text="我说:").pack(side=tk.LEFT, padx=(0, 2))
        self.my_lang_var = tk.StringVar(value=self.settings.get("my_lang", "zh"))
        my_lang_combo = ttk.Combobox(toolbar, textvariable=self.my_lang_var,
                                      values=list(LANG_MAP.keys()), width=6, state="readonly")
        my_lang_combo.pack(side=tk.LEFT, padx=(0, 2))
        my_lang_combo.bind("<<ComboboxSelected>>", lambda e: self._update_lang_label())

        ttk.Label(toolbar, text="对方说:").pack(side=tk.LEFT, padx=(5, 2))
        self.their_lang_var = tk.StringVar(value=self.settings.get("target_lang", "ru"))
        their_lang_combo = ttk.Combobox(toolbar, textvariable=self.their_lang_var,
                                         values=list(LANG_MAP.keys()), width=6, state="readonly")
        their_lang_combo.pack(side=tk.LEFT, padx=(0, 10))
        their_lang_combo.bind("<<ComboboxSelected>>", lambda e: self._update_lang_label())

        ttk.Label(toolbar, text="模式:").pack(side=tk.LEFT, padx=(0, 2))
        self.mode_var = tk.StringVar(value=self.settings.get("mode", "both"))
        mode_combo = ttk.Combobox(toolbar, textvariable=self.mode_var,
                                  values=["mic", "loopback", "both"], width=10, state="readonly")
        mode_combo.pack(side=tk.LEFT, padx=(0, 10))

        self.ptt_btn = ttk.Button(toolbar, text="PTT: 关", command=self._toggle_ptt, width=10)
        self.ptt_btn.pack(side=tk.LEFT, padx=(0, 10))
        if self.settings.get("ptt_enabled", False):
            _ptt_mode.set()
            self.ptt_btn.config(text="PTT: 开")

        self.start_btn = ttk.Button(toolbar, text="开始", command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_btn = ttk.Button(toolbar, text="停止", command=self._stop, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(toolbar, text="设置", command=self._open_settings).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="设备", command=self._list_devices).pack(side=tk.LEFT, padx=(0, 5))

        # 静音按钮
        self.mute_mic_btn = ttk.Button(toolbar, text="🎤", command=self._toggle_mute_mic, width=4)
        self.mute_mic_btn.pack(side=tk.LEFT, padx=(0, 2))
        self.mute_loopback_btn = ttk.Button(toolbar, text="🔊", command=self._toggle_mute_loopback, width=4)
        self.mute_loopback_btn.pack(side=tk.LEFT, padx=(0, 2))

        # 暂停朗读按钮
        self.pause_tts_btn = ttk.Button(toolbar, text="▶️", command=self._toggle_pause_tts, width=4)
        self.pause_tts_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.lang_label = ttk.Label(self.root, text="", font=("Microsoft YaHei", 14, "bold"))
        self.lang_label.pack(pady=5)
        self._update_lang_label()

        log_frame = ttk.LabelFrame(self.root, text="翻译日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Microsoft YaHei", 11), state="disabled")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_config("mic", foreground="#0066cc")
        self.log_text.tag_config("loopback", foreground="#cc6600")
        self.log_text.tag_config("system", foreground="#666666")
        self.log_text.tag_config("error", foreground="#cc0000")

        self.status_var = tk.StringVar(value="就绪 - 点击开始启动翻译")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.ptt_frame = ttk.Frame(self.root, padding=5)
        self.ptt_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.ptt_mic_label = ttk.Label(self.ptt_frame, text="我方: 待机", font=("Microsoft YaHei", 10))
        self.ptt_mic_label.pack(side=tk.LEFT, padx=10)

        self.ptt_loopback_label = ttk.Label(self.ptt_frame, text="对方: 待机", font=("Microsoft YaHei", 10))
        self.ptt_loopback_label.pack(side=tk.LEFT, padx=10)

        self.ptt_hint = ttk.Label(self.ptt_frame, text="", font=("Microsoft YaHei", 9), foreground="#888888")
        self.ptt_hint.pack(side=tk.RIGHT, padx=10)

    def _update_lang_label(self):
        my_lang = LANG_MAP[self.my_lang_var.get()]
        their_lang = LANG_MAP[self.their_lang_var.get()]
        my_name = LANG_NAMES.get(my_lang, my_lang)
        their_name = LANG_NAMES.get(their_lang, their_lang)
        self.lang_label.config(text=f"{my_name} <-> {their_name}")

    def _log(self, message, tag="system"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def _toggle_ptt(self):
        if _ptt_mode.is_set():
            _ptt_mode.clear()
            self.ptt_btn.config(text="PTT: 关")
            self._log("已切换为连续采集模式", "system")
        else:
            _ptt_mode.set()
            self.ptt_btn.config(text="PTT: 开")
            self._log("已切换为即按即说模式", "system")

    def _toggle_mute_mic(self):
        if _mute_mic.is_set():
            _mute_mic.clear()
            self.mute_mic_btn.config(text="🎤")
            self._log("🔊 麦克风已开启", "system")
        else:
            _mute_mic.set()
            self.mute_mic_btn.config(text="🔇")
            self._log("🔇 麦克风已静音", "system")

    def _toggle_mute_loopback(self):
        if _mute_loopback.is_set():
            _mute_loopback.clear()
            self.mute_loopback_btn.config(text="🔊")
            self._log("🔊 扬声器已开启", "system")
        else:
            _mute_loopback.set()
            self.mute_loopback_btn.config(text="🔇")
            self._log("🔇 扬声器已静音", "system")

    def _toggle_pause_tts(self):
        paused = toggle_pause_tts()
        if paused:
            self.pause_tts_btn.config(text="⏸️")
            self._log("⏸️ 朗读已暂停（翻译仍继续）", "system")
        else:
            self.pause_tts_btn.config(text="▶️")
            self._log("▶️ 朗读已恢复", "system")

    # ========== 后台加载模型 ==========

    def _start(self):
        if self._running:
            return

        self.start_btn.config(state="disabled")
        self._loading_dialog = LoadingDialog(self.root, title="加载模型中")
        self._log("后台加载模型中，请稍候...", "system")

        load_thread = threading.Thread(
            target=self._load_models_thread,
            args=(self.lang_var.get(), self.mode_var.get()),
            daemon=True
        )
        load_thread.start()

    def _load_models_thread(self, target_lang_code, mode):
        """后台线程：加载模型，避免阻塞 GUI"""
        try:
            model_size = self.settings.get("model_size", "medium")
            self._loading_dialog.set_detail("正在加载语音识别模型...")
            asr = LocalASR(model_size=model_size)

            self._loading_dialog.set_detail("正在加载翻译模型...")
            mt = LocalTranslator()

            self.root.after(0, lambda a=asr, m=mt, t=target_lang_code, md=mode, ms=model_size:
                self._on_models_loaded(a, m, t, md, ms))
        except Exception as exc:
            error_msg = str(exc)
            self.root.after(0, lambda msg=error_msg: self._on_models_load_failed(msg))

    def _on_models_loaded(self, asr, mt, target_lang_code, mode, model_size):
        if self._loading_dialog:
            self._loading_dialog.destroy()
            self._loading_dialog = None

        self.asr = asr
        self.mt = mt
        my_lang = LANG_MAP[self.my_lang_var.get()]
        their_lang = LANG_MAP[self.their_lang_var.get()]
        self.streamers = []

        if mode in ("mic", "both"):
            self.mic_pipeline = TranslationPipeline(
                my_lang, their_lang, "我方",
                self.asr, self.mt,
                ptt_event=_ptt_pressed_mic,
                mute_event=_mute_mic,
                log_callback=lambda msg: self._log(msg, "mic"),
                status_callback=lambda msg: self.status_var.set(msg)
            )
            mic_device = get_default_mic_device()
            streamer = AudioStreamer(mic_device, on_data=self.mic_pipeline.push_audio)
            streamer.start()
            self.streamers.append(streamer)
            self._log(f"麦克风已启动 (设备 {mic_device})", "system")

        if mode in ("loopback", "both"):
            self.loopback_pipeline = TranslationPipeline(
                their_lang, my_lang, "对方",
                self.asr, self.mt,
                ptt_event=_ptt_pressed_loopback,
                mute_event=_mute_loopback,
                log_callback=lambda msg: self._log(msg, "loopback"),
                status_callback=lambda msg: self.status_var.set(msg)
            )
            loop_device = get_default_loopback_device()
            streamer = AudioStreamer(loop_device, on_data=self.loopback_pipeline.push_audio)
            streamer.start()
            self.streamers.append(streamer)
            self._log(f"Loopback已启动 (设备 {loop_device})", "system")

        self._running = True
        self.stop_btn.config(state="normal")
        self.status_var.set("运行中 - 翻译已启动")
        self._log(f"模型加载完成 (ASR: {model_size})", "system")
        self._refresh_ptt_status()

    def _on_models_load_failed(self, error_msg):
        if self._loading_dialog:
            self._loading_dialog.destroy()
            self._loading_dialog = None

        self.start_btn.config(state="normal")
        messagebox.showerror("模型加载失败", f"加载模型时出错:\n{error_msg}")
        self.status_var.set("模型加载失败")
        self._log(f"模型加载失败: {error_msg}", "error")

    def _stop(self):
        if not self._running:
            return
        self._running = False

        for s in self.streamers:
            s.stop()
        self.streamers.clear()

        if self.mic_pipeline:
            self.mic_pipeline.stop()
            self.mic_pipeline = None
        if self.loopback_pipeline:
            self.loopback_pipeline.stop()
            self.loopback_pipeline = None

        self.asr = None
        self.mt = None

        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set("已停止")
        self._log("翻译已停止", "system")

    def _refresh_ptt_status(self):
        if not self._running:
            return

        if _ptt_pressed_mic.is_set():
            self.ptt_mic_label.config(text="我方: 采集中", foreground="red")
        else:
            self.ptt_mic_label.config(text="我方: 待机", foreground="green")

        if _ptt_pressed_loopback.is_set():
            self.ptt_loopback_label.config(text="对方: 采集中", foreground="red")
        else:
            self.ptt_loopback_label.config(text="对方: 待机", foreground="green")

        self.root.after(100, self._refresh_ptt_status)

    # ========== 快捷键系统 ==========

    def _parse_hotkey(self, hotkey_str):
        return [k.strip().lower() for k in hotkey_str.split("+") if k.strip()]

    def _all_pressed(self, keys):
        for k in keys:
            if not keyboard.is_pressed(k):
                return False
        return True

    def _apply_hotkeys(self):
        hk = self.settings.get("hotkeys", DEFAULT_HOTKEYS)

        for h in self._hotkey_hooks:
            try:
                keyboard.unhook(h)
            except Exception:
                pass
        self._hotkey_hooks = []
        self._ptt_states = {"mic": False, "loopback": False}

        mic_keys = self._parse_hotkey(hk.get("ptt_mic", "space"))
        loopback_keys = self._parse_hotkey(hk.get("ptt_loopback", "ctrl"))
        toggle_key = hk.get("toggle_mode", "f1")
        start_stop_key = hk.get("start_stop", "f2")
        clear_key = hk.get("clear_log", "f3")
        mute_mic_key = hk.get("mute_mic", "f5")
        mute_loopback_key = hk.get("mute_loopback", "f6")
        pause_tts_key = hk.get("pause_tts", "f7")

        def _on_key_event(event):
            if not self._running and event.name not in (start_stop_key, toggle_key, mute_mic_key, mute_loopback_key, pause_tts_key):
                return

            if mic_keys:
                all_mic = self._all_pressed(mic_keys)
                if all_mic and not self._ptt_states["mic"]:
                    self._ptt_states["mic"] = True
                    if _ptt_mode.is_set():
                        _ptt_pressed_mic.set()
                elif not all_mic and self._ptt_states["mic"]:
                    self._ptt_states["mic"] = False
                    if _ptt_mode.is_set() and _ptt_pressed_mic.is_set():
                        _ptt_pressed_mic.clear()
                        if self.mic_pipeline:
                            self.mic_pipeline.ptt_flush()

            if loopback_keys:
                all_lb = self._all_pressed(loopback_keys)
                if all_lb and not self._ptt_states["loopback"]:
                    self._ptt_states["loopback"] = True
                    if _ptt_mode.is_set():
                        _ptt_pressed_loopback.set()
                elif not all_lb and self._ptt_states["loopback"]:
                    self._ptt_states["loopback"] = False
                    if _ptt_mode.is_set() and _ptt_pressed_loopback.is_set():
                        _ptt_pressed_loopback.clear()
                        if self.loopback_pipeline:
                            self.loopback_pipeline.ptt_flush()

        self._hotkey_hooks.append(keyboard.hook(_on_key_event))

        try:
            self._hotkey_hooks.append(
                keyboard.add_hotkey(toggle_key, lambda: self.root.after(0, self._toggle_ptt)))
            self._hotkey_hooks.append(
                keyboard.add_hotkey(start_stop_key, lambda: self.root.after(0, self._stop if self._running else self._start)))
            self._hotkey_hooks.append(
                keyboard.add_hotkey(clear_key, lambda: self.root.after(0, self._clear_log)))
            self._hotkey_hooks.append(
                keyboard.add_hotkey(mute_mic_key, lambda: self.root.after(0, self._toggle_mute_mic)))
            self._hotkey_hooks.append(
                keyboard.add_hotkey(mute_loopback_key, lambda: self.root.after(0, self._toggle_mute_loopback)))
            self._hotkey_hooks.append(
                keyboard.add_hotkey(pause_tts_key, lambda: self.root.after(0, self._toggle_pause_tts)))
        except Exception as e:
            self._log(f"快捷键注册失败: {e}", "error")

        mic_str = hk.get("ptt_mic", "space")
        lb_str = hk.get("ptt_loopback", "ctrl")
        toggle_str = hk.get("toggle_mode", "f1")
        start_str = hk.get("start_stop", "f2")
        clear_str = hk.get("clear_log", "f3")
        mute_mic_str = hk.get("mute_mic", "f5")
        mute_lb_str = hk.get("mute_loopback", "f6")
        pause_str = hk.get("pause_tts", "f7")
        self.ptt_hint.config(
            text=f"快捷键: {mic_str}=我方 | {lb_str}=对方 | {toggle_str}=切换 | {start_str}=启停 | {clear_str}=清空 | {mute_mic_str}=静音麦 | {mute_lb_str}=静音扬声器 | {pause_str}=暂停朗读")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")

    def _open_settings(self):
        def on_save(new_settings):
            self.settings = new_settings
            self._apply_hotkeys()
            self._log("设置已保存，快捷键已更新", "system")
        SettingsWindow(self.root, self.settings, on_save)

    def _list_devices(self):
        win = tk.Toplevel(self.root)
        win.title("音频设备列表")
        win.geometry("600x400")
        text = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        import io
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        try:
            list_devices()
        except Exception as e:
            print(f"错误: {e}")
        finally:
            sys.stdout = old_stdout
        text.insert(tk.END, buffer.getvalue())
        text.config(state="disabled")

    def _on_close(self):
        self._stop()
        self.settings["window_geometry"] = self.root.geometry()
        self.settings["my_lang"] = self.my_lang_var.get()
        self.settings["target_lang"] = self.their_lang_var.get()
        self.settings["mode"] = self.mode_var.get()
        self.settings["ptt_enabled"] = _ptt_mode.is_set()
        save_settings(self.settings)
        keyboard.unhook_all()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = TranslatorGUI()
    app.run()
