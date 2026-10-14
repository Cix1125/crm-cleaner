"""归一化规则的单元测试。

用标准库 unittest 写 —— 这个项目从运行到测试都不需要安装任何第三方包。

跑：python -m unittest discover -s tests -v
"""
import unittest

from crm_cleaner.normalize import (
    build_norm,
    normalize_company,
    normalize_email,
    normalize_phone,
    normalize_text,
)


class TestTextNormalize(unittest.TestCase):
    def test_fullwidth_letters_become_halfwidth(self):
        # 从 Excel 复制出来的数据经常是全角
        self.assertEqual(normalize_text("ＡＢＣ１２３"), "ABC123")

    def test_chinese_punctuation_becomes_halfwidth(self):
        self.assertEqual(normalize_text("（郑州）"), "(郑州)")

    def test_extra_whitespace_collapsed(self):
        self.assertEqual(normalize_text("  郑州   云启  "), "郑州 云启")

    def test_none_is_empty_string(self):
        self.assertEqual(normalize_text(None), "")


class TestEmailNormalize(unittest.TestCase):
    def test_lowercased(self):
        self.assertEqual(normalize_email("ZhangWei@YunQi.com"), "zhangwei@yunqi.com")

    def test_strips_spaces(self):
        self.assertEqual(normalize_email("  a@b.com  "), "a@b.com")


class TestPhoneNormalize(unittest.TestCase):
    def test_keeps_digits_only(self):
        self.assertEqual(normalize_phone("138-0013-8000"), "13800138000")

    def test_strips_spaces_and_brackets(self):
        self.assertEqual(normalize_phone("(0371) 6666 8888"), "037166668888")

    def test_strips_country_code(self):
        self.assertEqual(normalize_phone("+86 138 0013 8000"), "13800138000")

    def test_keeps_landline_area_code(self):
        # 座机不能把 0371 当成国家码去掉
        self.assertEqual(normalize_phone("0371-88886666"), "037188886666")

    def test_empty(self):
        self.assertEqual(normalize_phone(""), "")


class TestCompanyNormalize(unittest.TestCase):
    def test_strips_chinese_legal_suffix(self):
        self.assertEqual(normalize_company("郑州云启科技有限公司"), "郑州云启科技")

    def test_strips_limited_liability_suffix(self):
        self.assertEqual(normalize_company("河南大河物流有限责任公司"), "河南大河物流")

    def test_strips_english_suffix(self):
        self.assertEqual(normalize_company("YunQi Technology Co., Ltd."), "yunqitechnology")

    def test_removes_inner_spaces(self):
        self.assertEqual(normalize_company("郑州 云启 科技"), "郑州云启科技")

    def test_keeps_parentheses_by_default(self):
        # 「XX(上海)」和「XX(北京)」是两家公司，默认不能合并
        self.assertNotEqual(
            normalize_company("云启科技(上海)有限公司"),
            normalize_company("云启科技(北京)有限公司"),
        )

    def test_strips_parentheses_when_asked(self):
        self.assertEqual(
            normalize_company("云启科技(上海)有限公司", strip_parentheses=True),
            normalize_company("云启科技(北京)有限公司", strip_parentheses=True),
        )

    def test_empty(self):
        self.assertEqual(normalize_company(""), "")


class TestBuildNorm(unittest.TestCase):
    def test_reads_canonical_fields(self):
        record = {
            "company": "郑州云启科技有限公司",
            "contact": " 张伟 ",
            "email": "ZhangWei@YunQi.com",
            "phone": "+86 138-0013-8000",
            "city": "郑州",
        }
        norm = build_norm(record, {"normalize": {}})
        self.assertEqual(norm["company"], "郑州云启科技")
        self.assertEqual(norm["contact"], "张伟")
        self.assertEqual(norm["email"], "zhangwei@yunqi.com")
        self.assertEqual(norm["phone"], "13800138000")

    def test_does_not_modify_original(self):
        record = {"company": "郑州云启科技有限公司", "email": "A@B.com"}
        build_norm(record, {"normalize": {}})
        # 原始值必须原样保留 —— 报告里要显示客户原来的写法
        self.assertEqual(record["company"], "郑州云启科技有限公司")
        self.assertEqual(record["email"], "A@B.com")


if __name__ == "__main__":
    unittest.main()
