"""
基于 webrtcvad 的简单语音端点检测（VAD）：
把持续输入的16kHz单声道PCM流，按"检测到停顿"切分成一句句完整语音，
再交给本地ASR识别。这是因为本地Whisper不是真正流式的，需要喂完整语音片段效果才好。
"""
import webrtcvad

FRAME_MS = 30
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2
FRAME_BYTES = int(SAMPLE_RATE * FRAME_MS / 1000) * BYTES_PER_SAMPLE


class Segmenter:
    def __init__(self, on_utterance, silence_ms=100, aggressiveness=2, min_utterance_frames=10):
        """
        on_utterance(pcm_bytes): 检测到一句话说完时的回调
        silence_ms: 说话结束后，静音持续多久才判定为一句话结束
        aggressiveness: VAD灵敏度 0~3，越大越严格（越不容易把噪音当成语音）
        min_utterance_frames: 短于这么多帧的"语音"会被当噪音丢弃
        """
        self.vad = webrtcvad.Vad(aggressiveness)
        self.on_utterance = on_utterance
        self.silence_frames_needed = max(1, silence_ms // FRAME_MS)
        self.min_utterance_frames = min_utterance_frames

        self._buffer = b""
        self._voiced_frames = []
        self._silence_count = 0
        self._in_speech = False

    def feed(self, pcm_bytes: bytes):
        self._buffer += pcm_bytes
        while len(self._buffer) >= FRAME_BYTES:
            frame = self._buffer[:FRAME_BYTES]
            self._buffer = self._buffer[FRAME_BYTES:]
            self._process_frame(frame)

    def _process_frame(self, frame: bytes):
        try:
            is_speech = self.vad.is_speech(frame, SAMPLE_RATE)
        except Exception:
            is_speech = False

        if is_speech:
            self._in_speech = True
            self._silence_count = 0
            self._voiced_frames.append(frame)
        elif self._in_speech:
            self._silence_count += 1
            self._voiced_frames.append(frame)  # 保留一点尾部静音，避免截断
            if self._silence_count >= self.silence_frames_needed:
                self._flush()

    def _flush(self):
        frames = self._voiced_frames
        self._voiced_frames = []
        self._in_speech = False
        self._silence_count = 0
        if len(frames) >= self.min_utterance_frames:
            self.on_utterance(b"".join(frames))