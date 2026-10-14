"""字段归一化：把「同一个客户的不同写法」变成可比较的形式。

这个模块是整个工具的地基 —— 去重的准确率，八成取决于这里的规则定得对不对。
"""
from __future__ import annotations

import re
import unicodedata

# ── 全角 → 半角 ──────────────────────────────────────────
# 全角字母数字交给 unicodedata.normalize("NFKC") 处理；
# 这里只补上 NFKC 不负责的中文标点。
_PUNCT_TABLE = str.maketrans(
    {
        "　": " ",   # 表意空格
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "－": "-",
        "—": "-",
        "、": ",",
        "，": ",",
        "．": ".",
    }
)

# ── 公司名后缀（法律形式），去掉它们才算「同一个公司」 ──
_CN_SUFFIX = re.compile(
    r"(股份有限公司|有限责任公司|有限公司|集团有限公司|集团|公司)$"
)
_EN_SUFFIX = re.compile(
    r"\b(limited|ltd|incorporated|inc|corporation|corp|company|co|llc|gmbh|plc)\b\.?$"
)
# 结尾的标点和空白
_TAIL_NOISE = re.compile(r"[\s\.\,\-_·]+$")


def to_halfwidth(text: str) -> str:
    """全角字符转半角。中文用户从 Excel 复制出来的数据里特别常见。"""
    return text.translate(_PUNCT_TABLE)


def normalize_text(value: str | None) -> str:
    """通用清洗：全角转半角、去掉首尾空白、把连续空白压成一个空格。"""
    if value is None:
        return ""
    value = str(value)
    value = unicodedata.normalize("NFKC", value)   # 全角字母数字 → 半角
    value = value.translate(_PUNCT_TABLE)          # 中文标点 → 半角
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_email(value: str | None) -> str:
    """邮箱：统一小写。RFC 说本地部分区分大小写，但现实中没人这么用。"""
    return normalize_text(value).lower()


def normalize_phone(value: str | None) -> str:
    """电话：只留数字，并去掉国家码前缀。

    '(+86) 138-0013-8000' → '13800138000'
    """
    digits = re.sub(r"\D", "", normalize_text(value))
    # 去掉 86 / 0086 国家码（仅当剩下的是 11 位手机号时才去）
    if len(digits) == 13 and digits.startswith("86"):
        digits = digits[2:]
    elif len(digits) == 14 and digits.startswith("0086"):
        digits = digits[4:]
    return digits


def normalize_company(value: str | None, *, strip_parentheses: bool = False) -> str:
    """公司名规范化。

    做的几件事：
      1. 全角转半角、压空白
      2. 去掉法律形式后缀（有限公司 / Ltd. / Inc. …）
      3. 去掉所有空格（中文公司名里的空格基本是噪音）
      4. 可选：去掉括号内容（默认关 —— 见下面的警告）

    警告：``strip_parentheses`` 默认是 **False**。
    「XX(上海)」和「XX(北京)」是两家不同的公司，去掉括号会把它们错误合并。
    只有当你的数据里括号内容明确是「备注」而不是「地区/分支」时才打开。
    """
    text = normalize_text(value).lower()
    if not text:
        return ""

    if strip_parentheses:
        text = re.sub(r"[\(\[]([^\)\]]*)[\)\]]", "", text)

    # 反复剥后缀：「XX有限公司集团」这种要剥两次才干净
    for _ in range(3):
        before = text
        text = _TAIL_NOISE.sub("", text)
        text = _CN_SUFFIX.sub("", text)
        text = _EN_SUFFIX.sub("", text)
        text = _TAIL_NOISE.sub("", text)
        if text == before:
            break

    return text.replace(" ", "")


def build_norm(record: dict, rules: dict) -> dict:
    """对一条规范记录跑归一化，结果放在 ``_norm`` 里给判重层用。

    原始值一个字都不动 —— 报告里仍要显示客户原来的写法。
    """
    return {
        "company": normalize_company(
            record.get("company", ""),
            strip_parentheses=bool(
                rules.get("normalize", {}).get("strip_parentheses", False)
            ),
        ),
        "email": normalize_email(record.get("email", "")),
        "phone": normalize_phone(record.get("phone", "")),
        "contact": normalize_text(record.get("contact", "")),
        "city": normalize_text(record.get("city", "")),
    }
