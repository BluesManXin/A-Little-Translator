
# 本地离线同声传译 — 15种语言任意互译 | Local Offline Simultaneous Translation — 15 Languages

> 🌍 **15种语言任意互译，完全离线，零API费用**
> 
> **15 Languages, Any-to-Any Translation, Fully Offline, Zero API Cost**
>
## 快速开始 | Quick Start

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/你的仓库名.git
cd 你的仓库名

# 2. 安装 Python 依赖
pip install -r requirements-local.txt

# 3. 下载 Piper 语音合成引擎
# 从 https://github.com/rhasspy/piper/releases 下载 piper_windows_amd64.zip
# 解压到 piper/ 目录

# 4. 下载语音模型
# 见 README 第5节，下载需要的语言模型到 voices/ 目录

# 5. 运行
python main_local.py --target ru --mode both
# 或 GUI 模式
python gui.py
---

## 目录 | Table of Contents

1. [功能特性 | Features](#1-功能特性--features)
2. [支持语言 | Supported Languages](#2-支持语言--supported-languages)
3. [硬件要求 | Hardware Requirements](#3-硬件要求--hardware-requirements)
4. [环境安装 | Environment Setup](#4-环境安装--environment-setup)
5. [下载语音模型 | Download Voice Models](#5-下载语音模型--download-voice-models)
6. [运行方式 | Usage](#6-运行方式--usage)
7. [快捷键 | Hotkeys](#7-快捷键--hotkeys)
8. [GUI模式 | GUI Mode](#8-gui模式--gui-mode)
9. [调优指南 | Tuning Guide](#9-调优指南--tuning-guide)
10. [常见问题 | FAQ](#10-常见问题--faq)
11. [打包发给朋友 | Share with Friends](#11-打包发给朋友--share-with-friends)
12. [项目文件结构 | Project Structure](#12-项目文件结构--project-structure)

---

## 1. 功能特性 | Features

| 功能 | 说明 |
|------|------|
| **完全离线** | 首次下载模型后，断网也能用 |
| **15种语言任意互译** | 不限于中文↔外语，任意两种语言之间可直接翻译 |
| **双向翻译** | 你说A语 → 对方听到B语；对方说B语 → 你听到A语 |
| **即按即说 (PTT)** | 按住空格说话，松开发送翻译 |
| **自动切句** | 连续模式下用VAD自动检测说话停顿 |
| **防自循环** | TTS播放期间自动屏蔽采集，避免无限循环 |
| **静音控制** | F5静音麦克风，F6静音扬声器 |
| **暂停朗读** | F7暂停/恢复TTS语音播放（翻译仍继续） |
| **防假死** | 自动关闭Windows控制台快速编辑模式，后台运行不卡顿 |
| **幻觉过滤** | 自动过滤"谢谢""订阅"等Whisper常见幻觉输出 |
| **GUI界面** | 图形界面，支持后台加载、实时日志、自定义快捷键 |

| Feature | Description |
|---------|-------------|
| **Fully Offline** | Works without internet after first model download |
| **15 Languages, Any-to-Any** | Translate between any two languages, not just Chinese↔X |
| **Bidirectional** | You speak A → they hear B; they speak B → you hear A |
| **Push-to-Talk (PTT)** | Hold spacebar to speak, release to send |
| **Auto Segmentation** | VAD auto-detects speech pauses in continuous mode |
| **Anti-Loop** | Mutes input during TTS playback to prevent feedback loops |
| **Mute Controls** | F5 = mute mic, F6 = mute speakers |
| **Pause TTS** | F7 = pause/resume voice output (translation continues) |
| **No Console Freeze** | Auto-disables Windows QuickEdit mode for background running |
| **Hallucination Filter** | Filters Whisper hallucinations like "thanks for watching" |
| **GUI** | Graphical interface with background loading, real-time logs |

---

## 2. 支持语言 | Supported Languages

| 代码 | 语言 | Language | Whisper | NLLB | Piper TTS |
|------|------|----------|---------|------|-----------|
| `zh` | 中文 | Chinese | ✅ | ✅ | ✅ |
| `cs` | 捷克语 | Czech | ✅ | ✅ | ✅ |
| `ru` | 俄语 | Russian | ✅ | ✅ | ✅ |
| `en` | 英语 | English | ✅ | ✅ | ✅ |
| `ja` | 日语 | Japanese | ✅ | ✅ | ⚠️ 无Piper模型 |
| `es` | 西班牙语 | Spanish | ✅ | ✅ | ✅ |
| `de` | 德语 | German | ✅ | ✅ | ✅ |
| `uk` | 乌克兰语 | Ukrainian | ✅ | ✅ | ✅ |
| `el` | 希腊语 | Greek | ✅ | ✅ | ✅ (low) |
| `bg` | 保加利亚语 | Bulgarian | ✅ | ✅ | ✅ |
| `ro` | 罗马尼亚语 | Romanian | ✅ | ✅ | ✅ |
| `sr` | 塞尔维亚语 | Serbian | ✅ | ✅ | ✅ |
| `sq` | 阿尔巴尼亚语 | Albanian | ✅ | ✅ | ⚠️ 需手动转换 |
| `pl` | 波兰语 | Polish | ✅ | ✅ | ✅ |
| `fr` | 法语 | French | ✅ | ✅ | ✅ |

> NLLB-200 支持这15种语言之间**直接互译**，不需要经过英语中转。  
> NLLB-200 supports direct translation between any of these 15 languages without routing through English.

---

## 3. 硬件要求 | Hardware Requirements

| 配置 | 效果 | Configuration | Performance |
|------|------|---------------|-------------|
| **最低** | CPU + 8GB 内存，每句延迟约 3~5 秒 | CPU + 8GB RAM, ~3-5s latency | Minimum |
| **推荐** | NVIDIA RTX 3060 + 16GB 内存，延迟约 1~2 秒 | RTX 3060 + 16GB RAM, ~1-2s latency | Recommended |
| **最佳** | RTX 4070+ + 16GB 显存，可加载 large-v3 | RTX 4070+ + 16GB VRAM, large-v3 model | Best |

> 磁盘空间：模型下载后约 **4~5 GB**  
> Disk space: ~**4-5 GB** after model download

---

## 4. 环境安装 | Environment Setup

### 4.1 安装 Python 依赖 | Install Python Dependencies

```bash
pip install -r requirements-local.txt
```

`requirements-local.txt` 包含：
- `faster-whisper` — 本地语音识别
- `transformers` + `torch` — NLLB-200 翻译模型
- `sentencepiece` — NLLB 分词器
- `webrtcvad-wheels` — 语音端点检测
- `numpy` — 数值计算
- `PyAudioWPatch` — Windows音频采集（支持WASAPI Loopback）
- `keyboard` — 全局键盘监听

### 4.2 安装 CUDA 版 PyTorch（有N卡必做）| Install CUDA PyTorch (Required for NVIDIA GPUs)

```bash
# 先卸载默认的CPU版
pip uninstall torch torchvision torchaudio -y

# CUDA 12.8（RTX 50系如5070Ti/5080/5090）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# CUDA 12.4（RTX 40系 / RTX 30系）
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# CUDA 11.8（GTX 10系 / RTX 20系 / GTX 1060）
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

验证安装 | Verify:
```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

---

## 5. 下载语音模型 | Download Voice Models

### 5.1 下载 Piper 语音合成引擎 | Download Piper TTS Engine

1. 打开 [Piper Releases](https://github.com/rhasspy/piper/releases)
2. 下载 `piper_windows_amd64.zip`
3. 解压到项目目录下的 `piper/` 文件夹，确保里面有 `piper.exe`

### 5.2 下载 Piper 语音模型 | Download Piper Voice Models

在项目目录下新建 `voices/` 文件夹，下载以下文件（每个语言需要 `.onnx` 和 `.onnx.json` 两个文件）：

```bash
# 🇨🇳 中文（女声）Chinese
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json

# 🇨🇿 捷克语（男声）Czech
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/cs/cs_CZ/jirka/medium/cs_CZ-jirka-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/cs/cs_CZ/jirka/medium/cs_CZ-jirka-medium.onnx.json

# 🇷🇺 俄语（女声）Russian
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx.json

# 🇺🇸 英语（男声）English
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json

# 🇪🇸 西班牙语（男声）Spanish
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json

# 🇩🇪 德语（男声）German
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json

# 🇺🇦 乌克兰语（女声）Ukrainian
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/uk/uk_UA/ukrainian_tts/medium/uk_UA-ukrainian_tts-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/uk/uk_UA/ukrainian_tts/medium/uk_UA-ukrainian_tts-medium.onnx.json

# 🇬🇷 希腊语（女声，low质量）Greek (low quality)
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/el/el_GR/rapunzelina/low/el_GR-rapunzelina-low.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/el/el_GR/rapunzelina/low/el_GR-rapunzelina-low.onnx.json

# 🇧🇬 保加利亚语（男声）Bulgarian
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/bg/bg_BG/dimitar/medium/bg_BG-dimitar-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/bg/bg_BG/dimitar/medium/bg_BG-dimitar-medium.onnx.json

# 🇷🇴 罗马尼亚语（男声）Romanian
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/ro/ro_RO/mihai/medium/ro_RO-mihai-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/ro/ro_RO/mihai/medium/ro_RO-mihai-medium.onnx.json

# 🇷🇸 塞尔维亚语（女声）Serbian
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/sr/sr_RS/serbski_institut/medium/sr_RS-serbski_institut-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/sr/sr_RS/serbski_institut/medium/sr_RS-serbski_institut-medium.onnx.json

# 🇵🇱 波兰语（女声）Polish
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/gosia/medium/pl_PL-gosia-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/gosia/medium/pl_PL-gosia-medium.onnx.json

# 🇫🇷 法语（女声）French
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json
```

> ⚠️ **阿尔巴尼亚语 (sq_AL)** 不在官方仓库中，需要从 sherpa-onnx 转换。详见下方 FAQ。  
> ⚠️ **Albanian (sq_AL)** is not in the official repo; needs conversion from sherpa-onnx. See FAQ below.

---

## 6. 运行方式 | Usage

### 6.0 查看音频设备 | List Audio Devices

```bash
python main_local.py --list-devices
```

### 6.1 任意两种语言互译 | Any Two Languages

```bash
# 中文 <-> 俄语（默认）Chinese <-> Russian
python main_local.py --target ru --mode both

# 英语 <-> 法语 English <-> French
python main_local.py --my-lang en --target fr --mode both

# 俄语 <-> 德语 Russian <-> German
python main_local.py --my-lang ru --target de --mode both

# 西班牙语 <-> 日语 Spanish <-> Japanese
python main_local.py --my-lang es --target ja --mode both

# 保加利亚语 <-> 波兰语 Bulgarian <-> Polish
python main_local.py --my-lang bg --target pl --mode both

# 只翻译我说的话 | Translate only my speech
python main_local.py --my-lang en --target fr --mode mic

# 只翻译对方说的话 | Translate only their speech
python main_local.py --my-lang en --target fr --mode loopback
```

### 6.2 即按即说模式 (PTT) | Push-to-Talk Mode

```bash
python main_local.py --my-lang en --target fr --mode both --ptt
```

### 6.3 GUI 模式 | GUI Mode

```bash
python gui.py
```

GUI 支持：双向语言选择、后台加载模型、实时日志、自定义快捷键、静音按钮、暂停朗读按钮。

---

## 7. 快捷键 | Hotkeys

| 按键 | 作用 | Key | Function |
|------|------|-----|----------|
| 按住空格 | 采集麦克风（我方说话）| Hold Space | Capture microphone (my speech) |
| 松开空格 | 发送翻译，播放外语 | Release Space | Send translation, play foreign voice |
| 按住 Ctrl | 采集系统声音（对方说话）| Hold Ctrl | Capture system audio (their speech) |
| 松开 Ctrl | 发送翻译，播放中文 | Release Ctrl | Send translation, play my language |
| F1 | 切换连续采集/即按即说 | F1 | Toggle continuous / PTT mode |
| F5 | 静音/开启麦克风 | F5 | Mute/unmute microphone |
| F6 | 静音/开启扬声器 | F6 | Mute/unmute speakers |
| F7 | 暂停/恢复朗读 | F7 | Pause/resume TTS playback |
| Ctrl+C | 退出程序 | Ctrl+C | Exit program |

> Windows 下建议用管理员权限运行 PowerShell，否则 keyboard 库可能无法监听全局按键。  
> On Windows, run PowerShell as administrator for global hotkeys to work.

---

## 8. GUI模式 | GUI Mode

```bash
python gui.py
```

功能：
- 两个下拉菜单分别选择"我说"和"对方说"的语言
- 后台加载模型（不卡界面）
- 实时翻译日志
- 自定义快捷键（支持组合键如 `ctrl+shift+a`）
- 静音按钮（🎤/🔇 麦克风，🔊/🔇 扬声器）
- 暂停朗读按钮（▶️/⏸️）
- 设置自动保存

Features:
- Two dropdowns for "I speak" and "They speak" languages
- Background model loading (non-blocking UI)
- Real-time translation logs
- Customizable hotkeys (supports combos like `ctrl+shift+a`)
- Mute buttons (mic & speakers)
- Pause TTS button
- Auto-save settings

---

## 9. 调优指南 | Tuning Guide

### 9.1 觉得太慢 | Too Slow?

| 修改位置 | 原值 | 建议值 | File | Original | Suggested |
|----------|------|--------|------|----------|-----------|
| `local_asr.py` | `model_size="medium"` | `"small"` | `local_asr.py` | `"medium"` | `"small"` |
| `local_mt.py` | `nllb-200-1.3B` | `nllb-200-distilled-600M` | `local_mt.py` | `1.3B` | `distilled-600M` |
| `vad.py` | `silence_ms=300` | `200` | `vad.py` | `300` | `200` |

### 9.2 GTX 1060 (6GB) 特别调优 | GTX 1060 (6GB) Tuning

```python
# local_asr.py
self.model = WhisperModel("small", device="cuda", compute_type="float16")

# local_mt.py
model_name="facebook/nllb-200-distilled-600M"
```

### 9.3 显存不够 (OOM) | Out of Memory?

```python
# local_mt.py 加载模型时加量化
self.model = AutoModelForSeq2SeqLM.from_pretrained(
    model_name,
    device_map="auto",
    load_in_8bit=True,  # 8-bit quantization
)
```

---

## 10. 常见问题 | FAQ

**Q: 第一次运行为什么很慢？**

A: faster-whisper 和 NLLB 模型需要自动从 HuggingFace 下载。下载完成后完全离线。

**Q: 为什么 PowerShell 放久了会假死？**

A: 这是 Windows 控制台快速编辑模式的特性。程序已自动关闭此模式，无需手动设置。

**Q: 阿尔巴尼亚语怎么没有语音？**

A: Piper 官方仓库没有阿尔巴尼亚语模型。需要从 sherpa-onnx 转换：
1. 下载 `vits-piper-sq_AL-LanguageWeaver-medium.tar.bz2` 从 [sherpa-onnx releases](https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models)
2. 解压后用 `convert_sherpa_to_piper.py` 生成 `.onnx.json`
3. 复制到 `voices/` 目录

**Q: 日语怎么没有语音？**

A: Piper 官方暂无日语模型。可选方案：
- 使用 MeloTTS（本地运行，支持日语）
- 使用 Edge-TTS（需联网）
- 只显示文字不播放语音

**Q: 可以换其他音色吗？**

A: 可以。去 [Piper Voices](https://huggingface.co/rhasspy/piper-voices/tree/main) 挑选喜欢的音色，下载对应的 `.onnx` + `.onnx.json`，修改代码里的 `VOICE_MODELS` 路径即可。

**Q: 支持更多语言吗？**

A: NLLB-200 支持200种语言互译，只要 Piper 有对应语音模型就能加。Whisper 也支持99种语言识别。

---

## 11. 打包发给朋友 | Share with Friends

### 发给朋友的文件清单 | Files to Share

```
同声传译/
├── main_local.py          # CLI 入口
├── gui.py                 # GUI 入口
├── config.py
├── local_asr.py
├── local_mt.py
├── local_tts.py
├── playback.py
├── vad.py
├── audio_io.py
├── build.py
├── requirements-local.txt
├── README-local.md
├── piper/
│   └── piper.exe
└── voices/                # 下载好的语音模型
    ├── zh_CN-huayan-medium.onnx
    ├── zh_CN-huayan-medium.onnx.json
    └── ...（其他语言的模型）
```

> 排除：`build/`、`dist/`、`__pycache__/`、`*.spec`、`settings.json`

### 朋友需要装什么 | What Your Friend Needs

1. **Python 3.11** — [下载](https://www.python.org/downloads/release/python-3119/)，勾选 "Add Python to PATH"
2. **依赖** — `pip install -r requirements-local.txt`
3. **CUDA 11.8**（GTX 1060）或 **CUDA 12.4**（RTX 30/40系）

首次运行会自动下载 ASR + MT 模型（约 2-4GB），保持联网。

---

## 12. 项目文件结构 | Project Structure

```
同声传译/
├── main_local.py          # CLI 主程序
├── gui.py                 # GUI 主程序
├── config.py              # 配置和命令行参数
├── local_asr.py           # 本地语音识别（faster-whisper）
├── local_mt.py            # 本地翻译（NLLB-200）
├── local_tts.py           # 本地语音合成（Piper）
├── playback.py            # 音频播放 + 防自循环 + 暂停朗读
├── vad.py                 # 语音端点检测（webrtcvad）
├── audio_io.py            # 音频采集（麦克风 + Loopback）
├── build.py               # PyInstaller 打包脚本
├── requirements-local.txt # Python依赖
├── settings.json          # GUI设置（运行时自动生成）
├── piper/
│   └── piper.exe          # Piper语音合成引擎
└── voices/                # Piper 语音模型
    ├── zh_CN-huayan-medium.onnx
    ├── zh_CN-huayan-medium.onnx.json
    └── ...
```

---

## 打包为 .exe（可选）| Build as .exe (Optional)

```bash
python build.py
```

打包完成后，输出目录为 `dist/VoiceTranslator/`，双击 `VoiceTranslator.exe` 即可运行。

> 提示：首次运行需要下载模型（约 4GB），请保持联网。运行时请以管理员身份运行，否则快捷键无效。

---

**祝你使用愉快！| Enjoy using it!**
