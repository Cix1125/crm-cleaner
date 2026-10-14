"""规则配置：用 TOML 描述「字段叫什么」和「怎么判重」。

为什么用 TOML 而不是 YAML？
    Python 3.11 起 ``tomllib`` 进了标准库。用 TOML 就能做到 **零第三方依赖** ——
    别人 clone 下来不用 pip install 任何东西就能跑。
"""
from __future__ import annotations

import tomllib
from pathlib import Path

# 工具内部统一使用的字段名（规范化字段）
CANONICAL_FIELDS = ("company", "contact", "email", "phone", "city", "updated_at")

# 输出 CSV / 报告时用的中文表头
OUTPUT_HEADERS = {
    "company": "公司名称",
    "contact": "联系人",
    "email": "邮箱",
    "phone": "电话",
    "city": "城市",
    "updated_at": "更新时间",
}

DEFAULT_RULES: dict = {
    "columns": {
        "company": ["公司名称", "客户名称", "公司", "company", "company_name"],
        "contact": ["联系人", "contact", "contact_name"],
        "email": ["邮箱", "电子邮箱", "email", "e-mail"],
        "phone": ["电话", "手机", "联系电话", "phone", "tel", "mobile"],
        "city": ["城市", "地区", "city", "region"],
        "updated_at": ["更新时间", "更新日期", "updated_at", "update_time"],
    },
    "normalize": {
        # 见 normalize.normalize_company 的警告：默认不去括号
        "strip_parentheses": False,
    },
    "match": {
        # 第 1 层：精确键。命中任意一个就算同一客户。
        "exact_keys": ["email", "phone"],
        # 第 2 层：公司名规范化后相同
        "company_key": True,
        # 第 3 层：相似度阈值（0~1），设 0 表示关闭
        "similarity_threshold": 0.88,
        # 相似度比较前按首字过滤，省掉大量无意义比较
        "similarity_prefilter": True,
    },
    "merge": {
        # 一组重复里哪条当主记录：
        #   most_complete / source_priority / latest
        "master_policy": "most_complete",
        "source_order": [],
        # 主记录字段为空时用同组其他记录补上
        "fill_empty_from_others": True,
    },
}


def load_rules(path: str | Path | None) -> dict:
    """读规则文件；没给就返回默认规则。"""
    if path is None:
        return _deep_copy(DEFAULT_RULES)

    with Path(path).open("rb") as fh:
        user = tomllib.load(fh)

    return _merge_dict(_deep_copy(DEFAULT_RULES), user)


def resolve_columns(headers: list[str], rules: dict) -> dict[str, str]:
    """拿规则里的候选列名，去**这个文件**的表头里认。

    注意是「每个文件各认一次」—— 不同系统导出来的表，同一件事列名不一样。
    这是现实中最烦的一步，也是这个工具存在的理由之一。

    返回 {逻辑字段: 实际列名}，认不出来的字段不在结果里。
    """
    resolved: dict[str, str] = {}
    lower_map = {h.strip().lower(): h for h in headers if h}

    for logical, candidates in rules.get("columns", {}).items():
        for cand in candidates:
            if cand in headers:
                resolved[logical] = cand
                break
            if cand.strip().lower() in lower_map:
                resolved[logical] = lower_map[cand.strip().lower()]
                break

    return resolved


def _deep_copy(obj):
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return list(obj)
    return obj


def _merge_dict(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge_dict(base[key], value)
        else:
            base[key] = value
    return base
