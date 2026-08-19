"""
本地翻译：基于 Meta 开源的 NLLB-200（No Language Left Behind）
中文/捷克语/俄语/英语/日语/西班牙语/德语/乌克兰语/希腊语/保加利亚语/罗马尼亚语/塞尔维亚语/阿尔巴尼亚语/波兰语/法语之间可以直接互译，不需要绕道英语。
首次运行需联网下载一次模型（约2.4GB）。
"""
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

# 我们内部用的语言标记 -> NLLB的语言代码
NLLB_CODES = {
    "zh-CN": "zho_Hans",
    "cs-CZ": "ces_Latn",
    "ru-RU": "rus_Cyrl",
    "en-US": "eng_Latn",
    "ja-JP": "jpn_Jpan",
    "es-ES": "spa_Latn",
    "de-DE": "deu_Latn",
    "uk-UA": "ukr_Cyrl",
    "el-GR": "ell_Grek",
    "bg-BG": "bul_Cyrl",
    "ro-RO": "ron_Latn",
    "sr-RS": "srp_Cyrl",
    "sq-AL": "sqi_Latn",
    "pl-PL": "pol_Latn",
    "fr-FR": "fra_Latn",
}


class LocalTranslator:
    def __init__(self, model_name="facebook/nllb-200-1.3B", device="cuda"):
        """
        distilled-600M 是速度和效果的平衡版本，纯CPU也能跑（但较慢）。
        如果显卡显存够（8GB+）且CUDA库装好了，可以传 device="cuda" 启用加速；
        默认写死"cpu"，避免自动检测判断错误导致崩溃。
        如果显卡显存够（8GB+），可以换成 facebook/nllb-200-1.3B 效果更好。
        """
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(self.device)
        self.model.eval()

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        if not text:
            return ""
        src_code = NLLB_CODES[src_lang]
        tgt_code = NLLB_CODES[tgt_lang]

        self.tokenizer.src_lang = src_code
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(tgt_code)

        with torch.no_grad():
            output_tokens = self.model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_new_tokens=256,
                max_length=None,   # 覆盖 tokenizer 默认的 max_length=200，消除警告
            )
        return self.tokenizer.batch_decode(output_tokens, skip_special_tokens=True)[0].strip()
