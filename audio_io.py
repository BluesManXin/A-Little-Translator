"""
音频采集模块（Windows专用）：
- 麦克风采集：我方说的中文
- WASAPI Loopback采集：系统扬声器正在播放的声音（例如Teams/Zoom里对方说的话）

依赖 PyAudioWPatch（对PyAudio的Windows WASAPI增强版，支持loopback录制系统声音）
"""
import pyaudiowpatch as pyaudio
import numpy as np

TARGET_RATE = 16000  # Azure语音识别要求/推荐的采样率


def list_devices():
    p = pyaudio.PyAudio()
    print("=== 输入设备（麦克风等） ===")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            print(f"[{i}] {info['name']}  (输入声道:{info['maxInputChannels']}, 采样率:{int(info['defaultSampleRate'])})")

    print("\n=== WASAPI Loopback 设备（用于捕获系统播放的声音，即对方语音）===")
    for loopback in p.get_loopback_device_info_generator():
        print(f"[{loopback['index']}] {loopback['name']}")
    p.terminate()


def _resample_to_16k_mono(data_bytes, channels, src_rate):
    """把采集到的PCM数据转换为 16kHz / 单声道 / 16-bit，供Azure语音识别使用"""
    audio = np.frombuffer(data_bytes, dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1).astype(np.int16)
    if src_rate != TARGET_RATE and len(audio) > 0:
        duration = len(audio) / src_rate
        target_len = max(int(duration * TARGET_RATE), 1)
        audio = np.interp(
            np.linspace(0, len(audio), target_len, endpoint=False),
            np.arange(len(audio)),
            audio,
        ).astype(np.int16)
    return audio.tobytes()


class AudioStreamer:
    """
    通用音频采集器：不断从指定设备读取音频，转换为16kHz单声道PCM，
    通过回调函数 on_data(bytes) 持续吐出数据块，供上层送入Azure识别器。
    """

    def __init__(self, device_index, on_data):
        self.p = pyaudio.PyAudio()
        self.on_data = on_data
        self.device_index = device_index
        self._stream = None

    def start(self):
        info = self.p.get_device_info_by_index(self.device_index)
        channels = int(info["maxInputChannels"])
        rate = int(info["defaultSampleRate"])

        def _callback(in_data, frame_count, time_info, status):
            pcm16k = _resample_to_16k_mono(in_data, channels, rate)
            self.on_data(pcm16k)
            return (in_data, pyaudio.paContinue)

        self._stream = self.p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=1024,
            stream_callback=_callback,
        )
        self._stream.start_stream()

    def stop(self):
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        self.p.terminate()


def get_default_loopback_device():
    """获取默认扬声器对应的loopback设备index（用于捕获对方语音）"""
    p = pyaudio.PyAudio()
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        if not default_speakers.get("isLoopbackDevice", False):
            for loopback in p.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    break
        return default_speakers["index"]
    finally:
        p.terminate()


def get_default_mic_device():
    p = pyaudio.PyAudio()
    try:
        return p.get_default_input_device_info()["index"]
    finally:
        p.terminate()
