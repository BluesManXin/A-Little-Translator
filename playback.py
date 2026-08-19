"""
播放PCM音频数据到默认扬声器（本地Demo阶段用；接入真实通话时可改为播放到虚拟声卡设备）

暂停朗读：设置环境变量或调用 toggle_pause_tts()
  F7 = 暂停/恢复 TTS 朗读
"""
import pyaudiowpatch as pyaudio
import threading
import time


class PlaybackGate:
    """播放门：TTS 播放期间及结束后一段冷却时间内，阻塞音频采集，防止自循环"""
    def __init__(self, cooldown_ms: int = 800):
        self._playing = threading.Event()
        self._cooldown_until = 0.0
        self.cooldown_ms = cooldown_ms
        self._lock = threading.Lock()

    def start(self):
        self._playing.set()

    def stop(self):
        self._playing.clear()
        with self._lock:
            self._cooldown_until = time.time() + self.cooldown_ms / 1000.0

    def is_active(self) -> bool:
        if self._playing.is_set():
            return True
        with self._lock:
            return time.time() < self._cooldown_until


# 全局单例，供 main_local.py 的 Pipeline 查询
gate = PlaybackGate(cooldown_ms=800)

# ==== 全局 TTS 暂停状态 ====
_pause_tts = threading.Event()
# ============================


def toggle_pause_tts() -> bool:
    """切换 TTS 暂停状态，返回当前是否已暂停"""
    if _pause_tts.is_set():
        _pause_tts.clear()
        return False
    else:
        _pause_tts.set()
        return True


def is_tts_paused() -> bool:
    return _pause_tts.is_set()


def play_pcm(pcm_bytes: bytes, sample_rate: int, channels: int = 1):
    if not pcm_bytes:
        return

    # 如果 TTS 被暂停，直接跳过播放
    if _pause_tts.is_set():
        return

    gate.start()
    try:
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=pyaudio.paInt16, channels=channels, rate=sample_rate, output=True)
            stream.write(pcm_bytes)
            stream.stop_stream()
            stream.close()
        finally:
            p.terminate()
    finally:
        gate.stop()
