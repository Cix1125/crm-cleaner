"""判重：三层匹配 + 并查集分组。

为什么要三层？
    只比邮箱 → 漏掉没填邮箱的；
    只比公司名 → 「郑州XX科技有限公司」和「郑州XX科技」判不出来；
    只比相似度 → 误合并率高，而且 O(N²) 太慢。
    所以从「绝对可靠」到「可能相似」分三层，越往后越需要人工确认。

为什么要并查集？
    重复是传递的：A 和 B 邮箱相同、B 和 C 公司名相同 → A、B、C 是同一家。
    用并查集合并，不用写成递归。
"""
from __future__ import annotations

from difflib import SequenceMatcher


class UnionFind:
    """并查集：把「是同一家」的记录连成一个个组。"""

    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, x: int) -> int:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        # 路径压缩：下次查更快
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra

    def groups(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = {}
        for i in range(len(self._parent)):
            out.setdefault(self.find(i), []).append(i)
        return out


def find_groups(records: list[dict], rules: dict) -> tuple[dict[int, list[int]], dict]:
    """返回 (组, 统计)。组里每一项是记录下标列表。"""
    match_rules = rules.get("match", {})
    uf = UnionFind(len(records))
    stats = {"exact": 0, "company": 0, "similar": 0}

    # ── 第 1 层：精确键（邮箱 / 电话）──
    for key in match_rules.get("exact_keys", []):
        buckets: dict[str, list[int]] = {}
        for idx, rec in enumerate(records):
            value = rec.get("_norm", {}).get(key, "")
            if value:
                buckets.setdefault(value, []).append(idx)
        for bucket in buckets.values():
            if len(bucket) > 1:
                stats["exact"] += _union_all(uf, bucket)

    # ── 第 2 层：公司名规范化后相同 ──
    if match_rules.get("company_key", True):
        buckets = {}
        for idx, rec in enumerate(records):
            value = rec.get("_norm", {}).get("company", "")
            if value:
                buckets.setdefault(value, []).append(idx)
        for bucket in buckets.values():
            if len(bucket) > 1:
                stats["company"] += _union_all(uf, bucket)

    # ── 第 3 层：相似度 ──
    threshold = float(match_rules.get("similarity_threshold", 0) or 0)
    if threshold > 0:
        stats["similar"] = _match_by_similarity(
            records, uf, threshold, prefilter=bool(match_rules.get("similarity_prefilter", True))
        )

    return uf.groups(), stats


def similarity(a: str, b: str) -> float:
    """两个公司名的相似度（0~1）。用的是标准库 difflib，不需要装任何东西。"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _union_all(uf: UnionFind, bucket: list[int]) -> int:
    """把一个 bucket 里的记录全并成一组，返回少算了多少次连接。"""
    merged = 0
    first = bucket[0]
    for other in bucket[1:]:
        if uf.find(first) != uf.find(other):
            uf.union(first, other)
            merged += 1
    return merged


def _match_by_similarity(
    records: list[dict], uf: UnionFind, threshold: float, *, prefilter: bool
) -> int:
    """两两比公司名相似度。

    ``prefilter`` 打开时，只有「首字相同」的才比 —— 公司名首字不同的，
    相似度几乎不可能过阈值，跳过能省掉大量比较（N² 在几万条数据上会很慢）。
    """
    pairs = 0
    names = [rec.get("_norm", {}).get("company", "") for rec in records]

    for i in range(len(records)):
        if not names[i]:
            continue
        for j in range(i + 1, len(records)):
            if not names[j]:
                continue
            if prefilter and names[i][0] != names[j][0]:
                continue
            if similarity(names[i], names[j]) >= threshold:
                if uf.find(i) != uf.find(j):
                    uf.union(i, j)
                    pairs += 1
    return pairs
