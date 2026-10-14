"""读取、认领字段、合并多份客户名单。

现实里客户数据几乎不会在一个文件里 —— 从 CRM 导一份、从 Excel 台账导一份、
再从客服系统导一份，然后要对起来。

这个模块做三件事：
  1. 读 CSV（自动试编码，中文 Excel 导出的多半是 GBK）
  2. **按文件分别认领字段** —— 不同系统导出的表，同一件事列名不一样
  3. 转成工具内部的规范字段名，后面所有模块都只认规范名
"""
from __future__ import annotations

import csv
from pathlib import Path

from .config import CANONICAL_FIELDS, resolve_columns

# 中文 Excel 导出的 CSV 常见编码，按命中率排序
_ENCODINGS = ("utf-8-sig", "gbk", "utf-8", "utf-16")


def read_csv(path: str | Path) -> tuple[list[str], list[dict]]:
    """读一个 CSV，返回 (表头, 行列表)。

    会依次尝试几种编码 —— 从 Excel 另存的 CSV 在中文 Windows 上多半是 GBK，
    直接按 UTF-8 读会炸。这是数据清洗里最经典的第一道坑。
    """
    path = Path(path)
    last_error: Exception | None = None

    for enc in _ENCODINGS:
        try:
            with path.open(encoding=enc, newline="") as fh:
                reader = csv.DictReader(fh)
                rows = [dict(row) for row in reader]
                return list(reader.fieldnames or []), rows
        except (UnicodeDecodeError, UnicodeError) as exc:
            last_error = exc
            continue

    raise ValueError(f"读不出 {path}，试过的编码都不行：{last_error}")


def load_sources(paths: list[str | Path], rules: dict) -> list[dict]:
    """读入所有来源文件，输出规范化的记录列表。

    每条记录长这样::

        {
            "company": "郑州云启科技有限公司",     # 原始值，不美化
            "contact": "张伟",
            ...
            "_source": "customers_a.csv",
            "_row": 2,
            "_columns": {"company": "公司名称", ...},   # 这个文件是怎么认的
            "_norm": {"company": "郑州云启科技", "email": "zhangwei@yunqi.com", ...},
        }
    """
    from .normalize import build_norm

    records: list[dict] = []

    for path in paths:
        headers, rows = read_csv(path)
        columns = resolve_columns(headers, rules)
        source_name = Path(path).name

        for line_no, row in enumerate(rows, start=2):  # 第 1 行是表头
            record: dict = {}
            for field in CANONICAL_FIELDS:
                column = columns.get(field)
                value = row.get(column, "") if column else ""
                record[field] = str(value or "").strip()

            record["_source"] = source_name
            record["_row"] = line_no
            record["_columns"] = columns
            record["_norm"] = build_norm(record, rules)
            records.append(record)

    return records
