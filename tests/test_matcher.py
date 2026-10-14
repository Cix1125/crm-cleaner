"""判重逻辑的单元测试：并查集、相似度、三层匹配。

跑：python -m unittest discover -s tests -v
"""
import unittest

from crm_cleaner.matcher import UnionFind, find_groups, similarity
from crm_cleaner.normalize import build_norm


def make_record(company="", email="", phone="", contact="", city=""):
    """造一条「已经归一化过」的记录，方便测判重。"""
    record = {
        "company": company, "contact": contact,
        "email": email, "phone": phone, "city": city,
    }
    record["_source"] = "test.csv"
    record["_row"] = 1
    record["_norm"] = build_norm(record, {"normalize": {}})
    return record


class TestUnionFind(unittest.TestCase):
    def test_groups(self):
        uf = UnionFind(4)
        uf.union(0, 1)
        uf.union(2, 3)
        sizes = sorted(len(v) for v in uf.groups().values())
        self.assertEqual(sizes, [2, 2])

    def test_is_transitive(self):
        # A-B 相连、B-C 相连 → A、B、C 是一组。这是重复识别里最关键的性质。
        uf = UnionFind(3)
        uf.union(0, 1)
        uf.union(1, 2)
        self.assertEqual(len(uf.groups()), 1)


class TestSimilarity(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(similarity("郑州云启科技", "郑州云启科技"), 1.0)

    def test_empty(self):
        self.assertEqual(similarity("", "abc"), 0.0)

    def test_partial(self):
        score = similarity("洛阳新材", "洛阳新材料")
        self.assertGreater(score, 0.85)
        self.assertLess(score, 1.0)


class TestFindGroups(unittest.TestCase):
    def test_exact_email_matches(self):
        records = [
            make_record(company="甲公司", email="a@x.com"),
            make_record(company="完全不同名字", email="a@x.com"),
        ]
        groups, stats = find_groups(records, {"match": {"exact_keys": ["email"]}})
        self.assertEqual(len(groups), 1)
        self.assertEqual(stats["exact"], 1)

    def test_company_key_matches(self):
        records = [
            make_record(company="郑州云启科技有限公司"),
            make_record(company="郑州云启科技"),
        ]
        groups, stats = find_groups(
            records, {"match": {"exact_keys": [], "company_key": True}}
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(stats["company"], 1)

    def test_similarity_threshold_can_be_disabled(self):
        records = [make_record(company="洛阳新材"), make_record(company="洛阳新材料")]

        groups, _ = find_groups(
            records,
            {"match": {"exact_keys": [], "company_key": True, "similarity_threshold": 0}},
        )
        self.assertEqual(len(groups), 2, "关掉相似层就不该合并")

        groups, _ = find_groups(
            records,
            {"match": {"exact_keys": [], "company_key": True, "similarity_threshold": 0.88}},
        )
        self.assertEqual(len(groups), 1, "打开相似层应该合并")

    def test_different_companies_not_merged(self):
        # 名字前缀相同但是两家不同的公司 —— 一定不能合并
        records = [
            make_record(company="河南云启信息技术有限公司", email="a@yunqi-it.com"),
            make_record(company="郑州云启科技有限公司", email="b@yunqi.com"),
        ]
        groups, _ = find_groups(
            records,
            {
                "match": {
                    "exact_keys": ["email"],
                    "company_key": True,
                    "similarity_threshold": 0.9,
                }
            },
        )
        self.assertEqual(len(groups), 2)

    def test_single_record_stays_alone(self):
        records = [make_record(company="只有一家")]
        groups, _ = find_groups(
            records, {"match": {"exact_keys": [], "company_key": True}}
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(list(groups.values())[0], [0])


if __name__ == "__main__":
    unittest.main()
