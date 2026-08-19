"""
配置文件：设置Azure语音服务密钥、区域，以及语言对
支持任意两种语言之间互译（不仅限于中文↔外语）
"""
import argparse

AZURE_SPEECH_KEY = "你的AZURE_SPEECH_KEY"
AZURE_SPEECH_REGION = "你的区域"

# 语言代码映射：简写 -> 完整代码
LANG_MAP = {
    "zh": "zh-CN",   # 中文
    "cs": "cs-CZ",   # 捷克语
    "ru": "ru-RU",   # 俄语
    "en": "en-US",   # 英语
    "ja": "ja-JP",   # 日语
    "es": "es-ES",   # 西班牙语
    "de": "de-DE",   # 德语
    "uk": "uk-UA",   # 乌克兰语
    "el": "el-GR",   # 希腊语
    "bg": "bg-BG",   # 保加利亚语
    "ro": "ro-RO",   # 罗马尼亚语
    "sr": "sr-RS",   # 塞尔维亚语
    "sq": "sq-AL",   # 阿尔巴尼亚语
    "pl": "pl-PL",   # 波兰语
    "fr": "fr-FR",   # 法语
}

# 语音合成使用的神经网络语音
TTS_VOICE_MAP = {
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "cs-CZ": "cs-CZ-VlastaNeural",
    "ru-RU": "ru-RU-SvetlanaNeural",
    "en-US": "en-US-JennyNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "es-ES": "es-ES-ElviraNeural",
    "de-DE": "de-DE-KatjaNeural",
    "uk-UA": "uk-UA-PolinaNeural",
    "el-GR": "el-GR-AthinaNeural",
    "bg-BG": "bg-BG-KalinaNeural",
    "ro-RO": "ro-RO-AlinaNeural",
    "sr-RS": "sr-RS-SophieNeural",
    "sq-AL": "sq-AL-AnilaNeural",
    "pl-PL": "pl-PL-AgnieszkaNeural",
    "fr-FR": "fr-FR-DeniseNeural",
}


def parse_args():
    all_langs = "/".join(LANG_MAP.keys())
    parser = argparse.ArgumentParser(
        description="15种语言实时双向语音互译 Demo（支持任意两种语言之间互译）"
    )
    parser.add_argument(
        "--my-lang", choices=list(LANG_MAP.keys()), default="zh",
        help=f"我方使用的语言：{all_langs}（默认：zh=中文）"
    )
    parser.add_argument(
        "--target", choices=list(LANG_MAP.keys()), required=False,
        help=f"对方使用的语言：{all_langs}"
    )
    parser.add_argument(
        "--mode", choices=["mic", "loopback", "both"], default="both",
        help="mic=只翻译我的麦克风输入；loopback=只翻译系统播放的对方语音；both=双向同时进行"
    )
    parser.add_argument("--list-devices", action="store_true", help="列出所有音频设备后退出")
    parser.add_argument(
        "--ptt", action="store_true",
        help="启动时进入即按即说模式（按住空格说话，松开发送），运行中按 F1 可随时切换"
    )
    args = parser.parse_args()

    if not args.list_devices and not args.target:
        parser.error(f"需要指定 --target {all_langs}（除非使用 --list-devices）")

    # 不允许自己和对方是同一种语言
    if args.target and args.my_lang == args.target:
        parser.error("--my-lang 和 --target 不能是同一种语言")

    return args
