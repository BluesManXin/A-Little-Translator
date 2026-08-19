"""
本地离线双向语音翻译 Demo 主程序（不依赖任何云端API，识别/翻译/合成全部在本机运行）
支持15种语言之间任意互译！

组件：
  webrtcvad（语音端点检测） + faster-whisper（识别） + NLLB-200（翻译） + Piper（合成）

用法：
  # 中文 <-> 俄语（默认，和原来一样）
  python main_local.py --target ru --mode both

  # 英语 <-> 法语（我说英语，对方说法语）
  python main_local.py --my-lang en --target fr --mode both

  # 俄语 <-> 德语（我说俄语，对方说德语）
  python main_local.py --my-lang ru --target de --mode both

  # 西班牙语 <-> 日语
  python main_local.py --my-lang es --target ja --mode both
"""
import sys
import ctypes


def _disable_quickedit():
    """关闭 Windows 控制台的快速编辑模式，防止后台假死"""
    if sys.platform != "win32":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        hStdin = kernel32.GetStdHandle(-10)
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

import queue
import threading
import time

import keyboard

from config import parse_args, LANG_MAP
from audio_io import AudioStreamer, get_default_mic_device, get_default_loopback_device, list_devices
from vad import Segmenter
from local_asr import LocalASR
from local_mt import LocalTranslator
from local_tts import LocalTTS
from playback import play_pcm, gate, toggle_pause_tts

# Whisper 语言代码映射
WHISPER_LANG = {
    "zh-CN": "zh", "cs-CZ": "cs", "ru-RU": "ru",
    "en-US": "en", "ja-JP": "ja", "es-ES": "es", "de-DE": "de",
    "uk-UA": "uk", "el-GR": "el", "bg-BG": "bg", "ro-RO": "ro",
    "sr-RS": "sr", "sq-AL": "sq", "pl-PL": "pl", "fr-FR": "fr",
}

# 语言显示名称
LANG_NAMES = {
    "zh-CN": "中文", "cs-CZ": "捷克语", "ru-RU": "俄语",
    "en-US": "英语", "ja-JP": "日语", "es-ES": "西班牙语", "de-DE": "德语",
    "uk-UA": "乌克兰语", "el-GR": "希腊语", "bg-BG": "保加利亚语", "ro-RO": "罗马尼亚语",
    "sr-RS": "塞尔维亚语", "sq-AL": "阿尔巴尼亚语", "pl-PL": "波兰语", "fr-FR": "法语",
}

PIPER_EXE = "piper/piper.exe"
VOICE_MODELS = {
    "zh-CN": "voices/zh_CN-huayan-medium.onnx",
    "cs-CZ": "voices/cs_CZ-jirka-medium.onnx",
    "ru-RU": "voices/ru_RU-irina-medium.onnx",
    "en-US": "voices/en_US-lessac-medium.onnx",
    "ja-JP": "voices/ja_JP-shirou-medium.onnx",
    "es-ES": "voices/es_ES-davefx-medium.onnx",
    "de-DE": "voices/de_DE-thorsten-medium.onnx",
    "uk-UA": "voices/uk_UA-ukrainian_tts-medium.onnx",
    "el-GR": "voices/el_GR-rapunzelina-low.onnx",
    "bg-BG": "voices/bg_BG-dimitar-medium.onnx",
    "ro-RO": "voices/ro_RO-mihai-medium.onnx",
    "sr-RS": "voices/sr_RS-serbski_institut-medium.onnx",
    "sq-AL": "voices/sq_AL-LanguageWeaver-medium.onnx",
    "pl-PL": "voices/pl_PL-gosia-medium.onnx",
    "fr-FR": "voices/fr_FR-siwis-medium.onnx",
}

# ==== 全局 PTT 状态 ====
_ptt_mode = threading.Event()
_ptt_space = threading.Event()
_ptt_ctrl = threading.Event()
# =======================

# ==== 全局静音状态 ====
_mute_mic = threading.Event()
_mute_loopback = threading.Event()
# ======================


class Pipeline:
    """一条方向的完整处理链：VAD分句 -> 本地识别 -> 本地翻译 -> 本地合成播放"""

    def __init__(self, src_lang, tgt_lang, label, asr, mt,
                 ptt_event=None, mute_event=None):
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.label = label
        self.asr = asr
        self.mt = mt
        self.tts = LocalTTS(PIPER_EXE, VOICE_MODELS[tgt_lang])
        self.segmenter = Segmenter(on_utterance=self._on_utterance)
        self._q = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

        self.ptt_event = ptt_event
        self.mute_event = mute_event
        self._ptt_buffer = bytearray()
        self._ptt_lock = threading.Lock()

    def push_audio(self, pcm_bytes):
        if self.mute_event and self.mute_event.is_set():
            return
        if gate.is_active():
            return
        if self.ptt_event and _ptt_mode.is_set():
            if self.ptt_event.is_set():
                with self._ptt_lock:
                    self._ptt_buffer.extend(pcm_bytes)
            return
        self.segmenter.feed(pcm_bytes)

    def ptt_flush(self):
        with self._ptt_lock:
            pcm = bytes(self._ptt_buffer)
            self._ptt_buffer.clear()
        min_bytes = int(16000 * 0.15 * 2)
        if len(pcm) >= min_bytes:
            self._q.put(pcm)
            print(f"\n[{self.label}] 已采集 {len(pcm)/32000:.1f}秒音频，处理中...")
        else:
            print(f"\n[{self.label}] 音频太短（{len(pcm)/32000:.2f}秒），已忽略")

    def _on_utterance(self, pcm_bytes):
        self._q.put(pcm_bytes)

    def _run(self):
        while True:
            pcm_bytes = self._q.get()
            try:
                text = self.asr.transcribe(pcm_bytes, WHISPER_LANG[self.src_lang])
                if not text:
                    continue
                translation = self.mt.translate(text, self.src_lang, self.tgt_lang)
                print(f"\n[{self.label} 原文] {text}")
                print(f"[{self.label} 译文] {translation}\n")
                if translation:
                    try:
                        pcm, rate = self.tts.synthesize_to_pcm(translation)
                        play_pcm(pcm, rate)
                    except Exception as e:
                        print(f"[{self.label}] TTS 播放失败: {e}")
            except Exception as e:
                print(f"[{self.label}] 处理出错: {e}")


def _setup_keyboard_handlers(mic_pipeline, loopback_pipeline):
    """设置全局键盘监听"""

    def on_space_press(_e):
        if _ptt_mode.is_set() and mic_pipeline:
            _ptt_space.set()
            print(f"\r[我方] 🎤 按住说话...               ", end="")

    def on_space_release(_e):
        if _ptt_mode.is_set() and _ptt_space.is_set() and mic_pipeline:
            _ptt_space.clear()
            print(f"\r[我方] ⏹ 松开发送                 ")
            mic_pipeline.ptt_flush()

    def on_ctrl_press(_e):
        if _ptt_mode.is_set() and loopback_pipeline:
            _ptt_ctrl.set()
            print(f"\r[对方] 🎤 按住说话...               ", end="")

    def on_ctrl_release(_e):
        if _ptt_mode.is_set() and _ptt_ctrl.is_set() and loopback_pipeline:
            _ptt_ctrl.clear()
            print(f"\r[对方] ⏹ 松开发送                 ")
            loopback_pipeline.ptt_flush()

    def on_f1(_e):
        if _ptt_mode.is_set():
            _ptt_mode.clear()
            print("\n[系统] 已切换 → 连续采集模式（自动VAD切句）")
        else:
            _ptt_mode.set()
            print("\n[系统] 已切换 → 即按即说模式")
            print("        空格 = 我方说话 | Ctrl = 对方说话 | 松开发送")

    def on_f5(_e):
        if _mute_mic.is_set():
            _mute_mic.clear()
            print("\n[系统] 🔊 麦克风已开启（我方语音正常采集）")
        else:
            _mute_mic.set()
            print("\n[系统] 🔇 麦克风已静音（我方语音不再采集）")

    def on_f6(_e):
        if _mute_loopback.is_set():
            _mute_loopback.clear()
            print("\n[系统] 🔊 扬声器已开启（对方语音正常采集）")
        else:
            _mute_loopback.set()
            print("\n[系统] 🔇 扬声器已静音（对方语音不再采集）")

    def on_f7(_e):
        paused = toggle_pause_tts()
        if paused:
            print("\n[系统] ⏸️ 朗读已暂停（翻译仍继续，只不播放语音）")
        else:
            print("\n[系统] ▶️ 朗读已恢复")

    keyboard.on_press_key("space", on_space_press)
    keyboard.on_release_key("space", on_space_release)
    keyboard.on_press_key("ctrl", on_ctrl_press)
    keyboard.on_release_key("ctrl", on_ctrl_release)
    keyboard.on_press_key("f1", on_f1)
    keyboard.on_press_key("f5", on_f5)
    keyboard.on_press_key("f6", on_f6)
    keyboard.on_press_key("f7", on_f7)


def main():
    args = parse_args()
    if args.list_devices:
        list_devices()
        return

    my_lang = LANG_MAP[args.my_lang]
    their_lang = LANG_MAP[args.target]

    print("正在加载本地模型（首次运行会自动下载一次，之后完全离线可用，请耐心等待）...")
    asr = LocalASR(model_size="medium")
    mt = LocalTranslator()
    print("模型加载完成。\n")

    streamers = []
    mic_pipeline = None
    loopback_pipeline = None

    my_name = LANG_NAMES.get(my_lang, my_lang)
    their_name = LANG_NAMES.get(their_lang, their_lang)

    if args.mode in ("mic", "both"):
        mic_pipeline = Pipeline(my_lang, their_lang, f"我方({my_name}->{their_name})", asr, mt,
                                  ptt_event=_ptt_space, mute_event=_mute_mic)
        mic_device = get_default_mic_device()
        streamer = AudioStreamer(mic_device, on_data=mic_pipeline.push_audio)
        streamer.start()
        streamers.append(streamer)
        print(f"已开始采集麦克风（设备index={mic_device}），{my_name} -> {their_name}")

    if args.mode in ("loopback", "both"):
        loopback_pipeline = Pipeline(their_lang, my_lang, f"对方({their_name}->{my_name})", asr, mt,
                                     ptt_event=_ptt_ctrl, mute_event=_mute_loopback)
        loop_device = get_default_loopback_device()
        streamer = AudioStreamer(loop_device, on_data=loopback_pipeline.push_audio)
        streamer.start()
        streamers.append(streamer)
        print(f"已开始采集系统播放声音（loopback index={loop_device}），{their_name} -> {my_name}")

    if mic_pipeline or loopback_pipeline:
        _setup_keyboard_handlers(mic_pipeline, loopback_pipeline)

    if args.ptt:
        _ptt_mode.set()
        print(f"\n[系统] 启动模式：即按即说")
        print(f"        我说 {my_name}，对方说 {their_name}")
        print("        空格 = 我方说话 | Ctrl = 对方说话 | 松开发送 | F1 切换模式")
    else:
        print(f"\n[系统] 启动模式：连续采集（自动VAD切句）")
        print(f"        我说 {my_name}，对方说 {their_name}")
        print("        按 F1 切换为即按即说")

    print("\n快捷键对照：")
    print("  空格 = 我方PTT | Ctrl = 对方PTT | F1 = 切换模式")
    print("  F5 = 静音/开启麦克风 | F6 = 静音/开启扬声器 | F7 = 暂停/恢复朗读")
    print("\n翻译已启动，按 Ctrl+C 停止...\n")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n正在停止...")
        keyboard.unhook_all()
        for s in streamers:
            s.stop()


if __name__ == "__main__":
    main()
