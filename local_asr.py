"""
本地语音识别：基于 faster-whisper（Whisper的CTranslate2高速本地实现）
支持中文/捷克语/俄语/英语/日语/西班牙语/德语/乌克兰语/希腊语等多语言，完全离线运行（首次运行需联网下载一次模型）

调试开关：设置环境变量 ASR_DEBUG=1 开启详细输出
  $env:ASR_DEBUG=1  (PowerShell)
  set ASR_DEBUG=1   (CMD)
"""
import os
import numpy as np
from faster_whisper import WhisperModel

_ASR_DEBUG = os.environ.get("ASR_DEBUG", "0") == "1"

# 已知幻觉文本黑名单（Whisper 对静音/噪音常输出的高频短语）
_HALLUCINATION_PATTERNS = [
    # 中文
    "谢谢", "感谢", "订阅", "小铃铛", "关注", "点赞", "收藏", "分享",
    "谢谢大家", "感谢观看", "记得订阅", "打开小铃铛", "感谢关注",
    # 英文
    "thanks for watching", "subscribe", "like and subscribe", "hit the bell",
    "thank you for watching", "please subscribe", "don't forget to subscribe",
    # 俄语
    "спасибо за внимание", "подпишись", "ставь лайк", "благодарю",
    "спасибо", "до свидания",
    # 通用
    "subtitle", "subtitles", "caption", "captions",
]


class LocalASR:
    def __init__(self, model_size="large-v3", device="cuda", compute_type="float16"):
        """
        model_size: tiny/base/small/medium/large-v3，越大越准但越慢
                    - 只有CPU：建议 small 或 medium
                    - 有独立显卡(6GB+显存)：可以用 medium 甚至 large-v3
        device: "auto"会自动选择有GPU用GPU，没有就用CPU
        compute_type: "int8"在CPU上速度较快，GPU上可用"float16"
        """
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, pcm16k_bytes: bytes, language: str) -> str:
        """pcm16k_bytes: 16kHz单声道16-bit PCM；language: 'zh'/'cs'/'ru'/'uk'/'el' 等"""
        if not pcm16k_bytes:
            if _ASR_DEBUG:
                print("[ASR调试] 收到空音频")
            return ""

        audio = np.frombuffer(pcm16k_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # ===== 能量检查：过滤静音/噪音片段，防止 Whisper 幻觉 =====
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < 0.015:
            if _ASR_DEBUG:
                print(f"[ASR调试] RMS={rms:.4f} 过低，判定为静音/噪音，跳过识别")
            return ""
        # ==========================================================

        if _ASR_DEBUG:
            duration = len(audio) / 16000
            max_amp = np.max(np.abs(audio))
            print(f"[ASR调试] 音频长度: {duration:.2f}秒, RMS={rms:.4f}, 最大振幅: {max_amp:.4f}")

        segments, info = self.model.transcribe(
            audio, language=language, beam_size=1, vad_filter=False
        )

        text = "".join(seg.text for seg in segments).strip()

        # ===== 幻觉过滤：命中已知幻觉模式直接丢弃 =====
        text_lower = text.lower()
        for pattern in _HALLUCINATION_PATTERNS:
            if pattern.lower() in text_lower:
                if _ASR_DEBUG:
                    print(f"[ASR调试] ⚠️ 命中幻觉黑名单 '{pattern}'，丢弃: '{text}'")
                return ""
        # ================================================

        if _ASR_DEBUG:
            print(f"[ASR调试] 语言检测: {info.language} (概率: {info.language_probability:.2f})")
            print(f"[ASR调试] 识别结果: '{text}'")

        return text