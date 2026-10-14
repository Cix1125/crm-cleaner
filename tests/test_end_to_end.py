"""端到端测试：直接跑 CLI，检查输出文件。

单测保证了每一块是对的，这一层保证拼起来也是对的。

跑：python -m unittest discover -s tests -v
"""
import csv
import tempfile
import unittest
from pathlib import Path

from crm_cleaner.cli import EXIT_FOUND_DUPLICATES, EXIT_OK, main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


class TestExampleRun(unittest.TestCase):
    def test_example_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main([
                "-i", str(EXAMPLES / "customers_a.csv"), str(EXAMPLES / "customers_b.csv"),
                "-r", str(EXAMPLES / "rules.toml"),
                "-o", tmp, "-q",
            ])

            # 发现重复 → 返回 1，方便接 CI 时当告警用
            self.assertEqual(code, EXIT_FOUND_DUPLICATES)

            master = read_csv(Path(tmp) / "master.csv")
            changes = read_csv(Path(tmp) / "changes.csv")

            # 10 条原始记录，4 组重复 → 合并成 6 条
            self.assertEqual(len(master), 6)
            # 有一处「补空」：洛阳新材缺城市，从另一份数据里补上了
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0]["字段"], "city")
            self.assertEqual(changes[0]["新值"], "洛阳")

            # 三家不同公司不能被误合并
            names = {row["公司名称"] for row in master}
            self.assertIn("河南云启信息技术有限公司", names)
            self.assertIn("漯河建材集团有限公司", names)

            # 重复组编号落在主数据里
            grouped = [row for row in master if row["_重复组"]]
            self.assertEqual(len(grouped), 4)

    def test_html_report_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            main([
                "-i", str(EXAMPLES / "customers_a.csv"), str(EXAMPLES / "customers_b.csv"),
                "-r", str(EXAMPLES / "rules.toml"),
                "-o", tmp, "-q",
            ])
            html = (Path(tmp) / "duplicates.html").read_text(encoding="utf-8")
            self.assertIn("重复组报告", html)
            self.assertIn("洛阳新材", html)
            self.assertIn('class="master"', html)


class TestEdgeCases(unittest.TestCase):
    def test_no_duplicates_returns_ok(self):
        """只有一份、且内部没有重复时，应该返回 0。"""
        with tempfile.TemporaryDirectory() as tmp:
            single = Path(tmp) / "single.csv"
            single.write_text(
                "公司名称,联系人,邮箱,电话,城市\n"
                "甲公司,张三,a@a.com,13800000001,郑州\n"
                "乙公司,李四,b@b.com,13800000002,洛阳\n",
                encoding="utf-8",
            )
            code = main(["-i", str(single), "-o", str(Path(tmp) / "out"), "-q"])
            self.assertEqual(code, EXIT_OK)

            master = read_csv(Path(tmp) / "out" / "master.csv")
            self.assertEqual(len(master), 2)

    def test_column_names_can_differ_between_files(self):
        """两份文件列名完全不同，也要能认出同一个字段 —— 这是最核心的能力。"""
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.csv"
            b = Path(tmp) / "b.csv"
            a.write_text("公司名称,联系人,邮箱\n甲公司,张三,a@a.com\n", encoding="utf-8")
            b.write_text("客户名称,联系人,电子邮箱\n甲公司,张三,a@a.com\n", encoding="utf-8")

            code = main(["-i", str(a), str(b), "-o", str(Path(tmp) / "out"), "-q"])
            self.assertEqual(code, EXIT_FOUND_DUPLICATES)

            master = read_csv(Path(tmp) / "out" / "master.csv")
            self.assertEqual(len(master), 1)

    def test_gbk_encoded_file_is_readable(self):
        """中文 Excel 另存的 CSV 多半是 GBK，必须能读。"""
        with tempfile.TemporaryDirectory() as tmp:
            gbk_file = Path(tmp) / "gbk.csv"
            gbk_file.write_bytes(
                "公司名称,联系人,邮箱\n甲公司,张三,a@a.com\n".encode("gbk")
            )
            code = main(["-i", str(gbk_file), "-o", str(Path(tmp) / "out"), "-q"])
            self.assertEqual(code, EXIT_OK)
            master = read_csv(Path(tmp) / "out" / "master.csv")
            self.assertEqual(master[0]["公司名称"], "甲公司")


if __name__ == "__main__":
    unittest.main()
