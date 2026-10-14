"""命令行入口。"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__, report
from .config import CANONICAL_FIELDS, OUTPUT_HEADERS, load_rules
from .loader import load_sources
from .matcher import find_groups
from .merger import merge_all

# 退出码约定（方便接 CI）：
#   0 = 跑通，且没有发现重复
#   1 = 跑通，但发现了重复（有需要人工确认的东西）
#   2 = 运行出错（文件读不了、规则写错等）
EXIT_OK = 0
EXIT_FOUND_DUPLICATES = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crm-cleaner",
        description="客户主数据清洗与去重：合并多份客户名单，找出重复，输出主数据与变更日志。",
    )
    parser.add_argument(
        "-i", "--input", nargs="+", required=True, metavar="CSV",
        help="一个或多个客户名单 CSV（列名可以不一样，工具会按规则自动认领）",
    )
    parser.add_argument(
        "-r", "--rules", default=None, metavar="TOML",
        help="规则文件（不填则用内置默认规则）",
    )
    parser.add_argument(
        "-o", "--outdir", default="out", metavar="DIR",
        help="输出目录（默认 out/）",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="只输出结果，不打印过程")
    parser.add_argument("--version", action="version", version=f"crm-cleaner {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def say(*parts: object) -> None:
        if not args.quiet:
            print(*parts)

    started = time.perf_counter()

    # ── 1. 读规则 ──
    try:
        rules = load_rules(args.rules)
    except Exception as exc:  # noqa: BLE001 —— CLI 边界，统一报错
        print(f"[错误] 规则文件读不了：{exc}", file=sys.stderr)
        return EXIT_ERROR

    # ── 2. 读数据 ──
    try:
        records = load_sources(args.input, rules)
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 数据读不了：{exc}", file=sys.stderr)
        return EXIT_ERROR

    if not records:
        print("[错误] 输入文件里没有数据。", file=sys.stderr)
        return EXIT_ERROR

    say(f"读入 {len(records)} 条记录，来自 {len(args.input)} 个文件")

    # 每个文件各自认到了哪些列 —— 现实里这一步经常认不全，先摊开来看
    seen_sources: dict[str, dict] = {}
    for rec in records:
        seen_sources.setdefault(rec["_source"], rec["_columns"])
    for source, columns in seen_sources.items():
        missing = [OUTPUT_HEADERS[f] for f in CANONICAL_FIELDS if f not in columns]
        line = f"  {source}：认到 {len(columns)} 个字段"
        if missing:
            line += f"（没认到：{'、'.join(missing)}）"
        say(line)

    # ── 3. 判重 ──
    groups, match_stats = find_groups(records, rules)
    duplicate_count = sum(1 for idx in groups.values() if len(idx) > 1)
    say(f"发现 {duplicate_count} 组重复客户")

    # ── 4. 合并 ──
    masters, duplicate_groups, changes = merge_all(groups, records, rules)
    say(f"合并后主数据 {len(masters)} 条，变更日志 {len(changes)} 条")

    # ── 5. 输出 ──
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    master_path = outdir / "master.csv"
    dup_path = outdir / "duplicates.html"
    change_path = outdir / "changes.csv"

    report.write_master_csv(masters, master_path)
    report.write_changes_csv(changes, change_path)
    report.write_html_report(
        duplicate_groups,
        dup_path,
        total_records=len(records),
        match_stats=match_stats,
    )

    elapsed = time.perf_counter() - started
    say(f"\n输出：\n  {master_path}\n  {dup_path}\n  {change_path}")
    say(f"耗时 {elapsed:.2f} 秒")

    return EXIT_FOUND_DUPLICATES if duplicate_groups else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
