"""合并：每一组重复客户，收敛成一条主记录，并留下变更日志。

变更日志是这个工具最容易被忽略、但客户最在意的东西：
    迁移完必须能回答「到底合并了哪些、动了哪个字段」。
    没有它，数据团队不敢用这个工具。
"""
from __future__ import annotations


def pick_master(group: list[dict], rules: dict) -> dict:
    """一组里挑一条当主记录。"""
    policy = rules.get("merge", {}).get("master_policy", "most_complete")

    if policy == "source_priority":
        order = rules.get("merge", {}).get("source_order", []) or []
        rank = {name: i for i, name in enumerate(order)}

        def sort_key(rec):
            return (rank.get(rec.get("_source", ""), len(order)), -_filled(rec))

        return sorted(group, key=sort_key)[0]

    if policy == "latest":
        def sort_key(rec):
            return (str(rec.get("updated_at", "") or ""), _filled(rec))

        return sorted(group, key=sort_key, reverse=True)[0]

    # most_complete：字段最全的那条
    return sorted(group, key=_filled, reverse=True)[0]


def _filled(record: dict) -> int:
    """一条记录里有多少个非空业务字段。"""
    return sum(
        1
        for key, value in record.items()
        if not key.startswith("_") and str(value or "").strip()
    )


def merge_group(group: list[dict], rules: dict) -> tuple[dict, dict, list[dict]]:
    """把一组记录合成一条，返回 (主记录原文, 合并结果, 变更明细)。"""
    master = pick_master(group, rules)
    merged = {k: v for k, v in master.items() if not k.startswith("_")}

    change_log: list[dict] = []
    fill_from_others = rules.get("merge", {}).get("fill_empty_from_others", True)

    business_fields = [k for k in master.keys() if not k.startswith("_")]

    for field in business_fields:
        original = str(merged.get(field, "") or "").strip()

        if original or not fill_from_others:
            continue

        # 主记录这个字段是空的 —— 看看同组别的记录有没有值
        for other in group:
            if other is master:
                continue
            candidate = str(other.get(field, "") or "").strip()
            if candidate:
                merged[field] = candidate
                change_log.append(
                    {
                        "组内记录数": len(group),
                        "字段": field,
                        "动作": "补空",
                        "原值": "",
                        "新值": candidate,
                        "取值来源": f"{other.get('_source')}#{other.get('_row')}",
                        "主记录来源": f"{master.get('_source')}#{master.get('_row')}",
                    }
                )
                break

    return master, merged, change_log


def merge_all(groups: dict[int, list[int]], records: list[dict], rules: dict):
    """对所有组跑一遍合并，返回 (主数据列表, 重复组, 变更日志)。"""
    masters: list[dict] = []
    duplicate_groups: list[dict] = []
    changes: list[dict] = []

    group_id = 0
    for _root, indexes in sorted(groups.items(), key=lambda kv: min(kv[1])):
        group_id += 1
        group = [records[i] for i in indexes]

        if len(group) == 1:
            # 不重复，直接进主数据
            single = {k: v for k, v in group[0].items() if not k.startswith("_")}
            single["_重复组"] = ""
            single["_来源"] = f"{group[0].get('_source')}#{group[0].get('_row')}"
            masters.append(single)
            continue

        master, merged, group_changes = merge_group(group, rules)
        merged["_重复组"] = f"G{group_id:04d}"
        merged["_来源"] = f"{group[0].get('_source')}#{group[0].get('_row')}"
        masters.append(merged)
        changes.extend(group_changes)

        duplicate_groups.append(
            {
                "group_id": f"G{group_id:04d}",
                "size": len(group),
                "master": master,
                "members": group,
                "merged": merged,
                "changes": group_changes,
            }
        )

    return masters, duplicate_groups, changes
