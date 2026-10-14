"""输出：清洗后的主数据、变更日志、重复组报告。

报告是给别人看的 —— 做数据迁移时，客户方的业务人员要能一眼看懂
「哪些被合并了、为什么」。所以 HTML 报告里原始值一个字都不美化。
"""
from __future__ import annotations

import csv
import html
from pathlib import Path

from .config import CANONICAL_FIELDS, OUTPUT_HEADERS

_HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>客户主数据 · 重复组报告</title>
<style>
  body { font-family: "Microsoft YaHei", -apple-system, sans-serif; margin: 0;
         background: #f5f6f8; color: #1f2328; font-size: 14px; line-height: 1.6; }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 28px 20px 60px; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: #6b7280; font-size: 13px; margin-bottom: 18px; }
  .cards { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
  .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
          padding: 12px 18px; min-width: 130px; }
  .card b { display: block; font-size: 22px; color: #c8102e; }
  .card span { color: #6b7280; font-size: 12px; }
  .group { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
           margin-bottom: 16px; overflow: hidden; }
  .group h2 { font-size: 15px; margin: 0; padding: 10px 16px; background: #fafbfc;
              border-bottom: 1px solid #eef0f3; font-weight: 600; }
  .group h2 em { font-style: normal; color: #c8102e; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; background: #fafbfc; color: #57606a; font-weight: 600;
       padding: 6px 10px; border-bottom: 1px solid #eef0f3; white-space: nowrap; }
  td { padding: 6px 10px; border-bottom: 1px solid #f4f5f7; vertical-align: top; }
  tr.master td { background: #fffdf5; }
  tr.master td:first-child::before { content: "★ "; color: #d97706; }
  .tag { display: inline-block; font-size: 11px; padding: 1px 6px; border-radius: 3px;
         background: #eef2ff; color: #4356a8; }
  .empty { color: #b9bfc7; }
  code { font-family: Consolas, monospace; font-size: 12px; }
</style>
</head>
<body>
<div class="wrap">
<h1>客户主数据 · 重复组报告</h1>
<div class="sub">由 crm-cleaner 生成 · 带 ★ 的是该组的主记录 · 表中显示的是客户原始写法</div>
"""

_HTML_TAIL = """</div>
</body>
</html>
"""

# 报告里横向展示的字段（更新时间太长，不放表里）
_DISPLAY_FIELDS = ("company", "contact", "email", "phone", "city")


def write_master_csv(masters: list[dict], path: str | Path) -> None:
    """写出清洗后的主数据。表头用中文，末尾附重复组编号和来源。"""
    path = Path(path)
    headers = [OUTPUT_HEADERS[f] for f in CANONICAL_FIELDS] + ["_重复组", "_来源"]

    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for row in masters:
            writer.writerow(
                [row.get(f, "") for f in CANONICAL_FIELDS]
                + [row.get("_重复组", ""), row.get("_来源", "")]
            )


def write_changes_csv(changes: list[dict], path: str | Path) -> None:
    """写出变更日志：哪一组、哪个字段、做了什么。"""
    path = Path(path)
    if not changes:
        path.write_text("", encoding="utf-8-sig")
        return

    fieldnames = list(changes[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(changes)


def write_html_report(
    duplicate_groups: list[dict],
    path: str | Path,
    *,
    total_records: int,
    match_stats: dict,
) -> None:
    """生成重复组报告。"""
    parts = [_HTML_HEAD]

    merged_count = sum(g["size"] for g in duplicate_groups)
    parts.append('<div class="cards">')
    parts.append(f'<div class="card"><b>{total_records}</b><span>读入记录</span></div>')
    parts.append(f'<div class="card"><b>{len(duplicate_groups)}</b><span>重复组</span></div>')
    parts.append(f'<div class="card"><b>{merged_count}</b><span>涉及记录</span></div>')
    parts.append(
        f'<div class="card"><b>{merged_count - len(duplicate_groups)}</b>'
        f'<span>可合并掉</span></div>'
    )
    parts.append("</div>")

    parts.append(
        f'<p class="sub">匹配来源：精确键 {match_stats.get("exact", 0)} 处 · '
        f'公司名规范化 {match_stats.get("company", 0)} 处 · '
        f'相似度 {match_stats.get("similar", 0)} 处</p>'
    )

    if not duplicate_groups:
        parts.append('<div class="group"><h2>没有发现重复客户</h2></div>')

    for group in duplicate_groups:
        master = group["master"]
        parts.append('<div class="group">')
        parts.append(
            f'<h2>{group["group_id"]} · <em>{group["size"]}</em> 条记录指向同一客户</h2>'
        )
        parts.append("<table><thead><tr><th>来源</th>")
        for field in _DISPLAY_FIELDS:
            parts.append(f"<th>{OUTPUT_HEADERS[field]}</th>")
        parts.append("</tr></thead><tbody>")

        for member in group["members"]:
            cls = ' class="master"' if member is master else ""
            parts.append(f"<tr{cls}>")
            parts.append(
                f'<td><span class="tag">{html.escape(str(member.get("_source", "")))}'
                f'#{member.get("_row", "")}</span></td>'
            )
            for field in _DISPLAY_FIELDS:
                cell = str(member.get(field, "") or "").strip()
                if cell:
                    parts.append(f"<td>{html.escape(cell)}</td>")
                else:
                    parts.append('<td class="empty">—</td>')
            parts.append("</tr>")

        parts.append("</tbody></table>")

        if group["changes"]:
            parts.append(
                "<table><thead><tr><th>字段</th><th>动作</th>"
                "<th>原值</th><th>新值</th><th>取值来源</th></tr></thead><tbody>"
            )
            for change in group["changes"]:
                parts.append(
                    "<tr>"
                    f'<td>{html.escape(OUTPUT_HEADERS.get(change["字段"], change["字段"]))}</td>'
                    f'<td>{html.escape(str(change["动作"]))}</td>'
                    f'<td class="empty">{html.escape(str(change["原值"]) or "—")}</td>'
                    f'<td>{html.escape(str(change["新值"]))}</td>'
                    f'<td><code>{html.escape(str(change["取值来源"]))}</code></td>'
                    "</tr>"
                )
            parts.append("</tbody></table>")

        parts.append("</div>")

    parts.append(_HTML_TAIL)
    Path(path).write_text("".join(parts), encoding="utf-8")
