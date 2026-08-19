"""
本地语音合成：调用 Piper（一个又快又轻量的本地神经网络TTS）的可执行文件 piper.exe
Piper本身不提供Python官方稳定binding，最省心的方式是直接调用命令行程序，用 --output-raw 拿到原始PCM。

调试开关：设置环境变量 TTS_DEBUG=1 开启详细输出
  $env:TTS_DEBUG=1  (PowerShell)
  set TTS_DEBUG=1   (CMD)
"""
import os
import subprocess
import threading

# Piper 不是线程安全的，所有 TTS 实例共享一个全局锁
_GLOBAL_PIPER_LOCK = threading.Lock()
_TTS_DEBUG = os.environ.get("TTS_DEBUG", "0") == "1"


class LocalTTS:
    def __init__(self, piper_exe_path: str, voice_model_path: str, sample_rate: int = 22050):
        """
        piper_exe_path: piper.exe 的路径（从 https://github.com/rhasspy/piper/releases 下载解压后得到）
        voice_model_path: 对应语言的 .onnx 语音模型路径（同时需要旁边有同名的 .onnx.json 配置文件）
        sample_rate: 该模型的输出采样率，medium音质的piper模型通常是22050Hz
        """
        self.piper_exe = piper_exe_path
        self.voice_model = voice_model_path
        self.sample_rate = sample_rate

        # 检查模型文件是否完整
        json_path = voice_model_path + ".json"
        self._available = os.path.exists(voice_model_path) and os.path.exists(json_path)

        if _TTS_DEBUG:
            print(f"[TTS调试] 初始化: exe={piper_exe_path}, model={voice_model_path}, sr={sample_rate}")
            if not os.path.exists(voice_model_path):
                print(f"[TTS调试] ⚠️ 模型文件不存在: {voice_model_path}")
            if not os.path.exists(json_path):
                print(f"[TTS调试] ⚠️ 配置文件不存在: {json_path}")
            if not self._available:
                print(f"[TTS调试] ⚠️ 模型不完整，TTS将跳过播放（只显示文字）")

    def synthesize_to_pcm(self, text: str):
        """返回 (pcm_bytes, sample_rate)，pcm为16-bit单声道原始数据"""
        if not text:
            return b"", self.sample_rate

        # 如果模型文件不完整，跳过合成
        if not self._available:
            if _TTS_DEBUG:
                print(f"[TTS调试] 跳过合成（模型缺失）: '{text[:30]}...'")
            return b"", self.sample_rate

        cmd = [self.piper_exe, "--model", self.voice_model, "--output-raw"]

        if _TTS_DEBUG:
            print(f"[TTS调试] 合成命令: {' '.join(cmd)}")
            print(f"[TTS调试] 合成文本: '{text}'")

        # 全局锁：防止两个 Pipeline 同时调用 Piper 导致崩溃
        with _GLOBAL_PIPER_LOCK:
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
            )

            if _TTS_DEBUG:
                print(f"[TTS调试] 返回码: {proc.returncode}")
                if proc.stderr:
                    print(f"[TTS调试] stderr: {proc.stderr.decode('utf-8', errors='ignore')[:500]}")
                print(f"[TTS调试] 输出PCM大小: {len(proc.stdout)} bytes")

            if proc.returncode != 0:
                err = proc.stderr.decode('utf-8', errors='ignore')
                raise RuntimeError(f"piper合成失败 (模型: {os.path.basename(self.voice_model)}): {err[:200]}")

            if len(proc.stdout) == 0:
                raise RuntimeError(f"piper合成返回空音频 (模型: {os.path.basename(self.voice_model)})")

            return proc.stdout, self.sample_rate
