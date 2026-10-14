# crm-cleaner

**Customer master data cleaning and de-duplication** — a small CLI tool for CRM implementation and data migration projects.

It merges several customer lists that **do not share the same columns**, cleans them, finds duplicates, and produces **master data + a duplicate-group report + a change log**.

> **Zero runtime dependencies.** Standard library only — `git clone` and run. No `pip install` needed.

---

## The problem it solves

When a CRM goes live or data is migrated, the first wall is always messy customer data:

- The same customer written three ways across three tables: `郑州云启科技有限公司` / `郑州云启科技` / `郑州云启科技（郑州）`
- Email case inconsistency (`ZhangWei@YunQi.com` vs `zhangwei@yunqi.com`)
- Phone numbers with dashes, spaces, brackets, country codes
- **Different column names meaning the same field** — one export calls it `公司名称`, another calls it `客户名称`
- After merging, **nobody can say what was merged or what changed**

Today this is done by scrolling through Excel. This tool automates it and keeps an auditable change log.

---

## Quick start

Python 3.11+ and nothing else.

```bash
git clone <repo-url>
cd crm-cleaner

python -m crm_cleaner \
  -i examples/customers_a.csv examples/customers_b.csv \
  -r examples/rules.toml \
  -o out
```

Output:

```
Read 10 records from 2 files
  customers_a.csv: 5 fields recognised (missing: 更新时间)
  customers_b.csv: 5 fields recognised (missing: 更新时间)
Found 4 duplicate groups
Master data: 6 records, change log: 1 entry

Wrote:
  out/master.csv
  out/duplicates.html
  out/changes.csv
```

Open `out/duplicates.html` in a browser to see each duplicate group, where every record came from, and which one was chosen as the master.

### CLI options

| Option | Description |
|---|---|
| `-i, --input` | One or more customer CSV files (column names may differ) |
| `-r, --rules` | Rules file (TOML). Built-in defaults are used if omitted |
| `-o, --outdir` | Output directory, defaults to `out/` |
| `-q, --quiet` | Print results only |
| `--version` | Show version |

### Exit codes

Designed to be CI-friendly:

| Code | Meaning |
|---|---|
| `0` | Ran fine, no duplicates found |
| `1` | Ran fine, **duplicates found** (something needs human review) |
| `2` | Runtime error (unreadable file, bad rules, …) |

---

## How matching works

Comparing a single field always breaks something, so matching runs in three layers — from "certain" to "probably":

| Layer | Rule | Notes |
|---|---|---|
| **1 · Exact keys** | Identical normalised email or phone | Most reliable |
| **2 · Normalised** | Same company name after stripping legal-form suffixes | `郑州云启科技有限公司` matches `郑州云启科技` |
| **3 · Similarity** | `difflib` ratio ≥ threshold (default 0.88) | Fallback. `洛阳新材` vs `洛阳新材料` scores 0.889 |

**Grouping uses union-find.** Duplicates are transitive: if A shares an email with B and B shares a company name with C, then A, B and C are one customer. Union-find handles that far more cleanly than recursion.

### Tuning

The similarity threshold is the only knob you normally need to touch:

- **Too high → misses.** `洛阳新材` vs `洛阳新材料` scores 0.889, so a 0.9 threshold drops it.
- **Too low → false merges.** `河南云启信息技术` and `郑州云启科技` are unrelated companies that share a prefix.

The default is 0.88, and **layer-3 matches should still be reviewed by a human** — the report shows which layer produced each group.

---

## Configuration

Written in TOML — `tomllib` has been in the standard library since Python 3.11, so no PyYAML dependency either.

```toml
# Column mapping: different systems name the same thing differently
[columns]
company = ["公司名称", "客户名称", "公司", "company", "company_name"]
email   = ["邮箱", "电子邮箱", "email", "e-mail"]
phone   = ["电话", "手机", "联系电话", "phone", "tel", "mobile"]

[normalize]
# "XX(Shanghai)" and "XX(Beijing)" are different companies — brackets kept by default
strip_parentheses = false

[match]
exact_keys = ["email", "phone"]
company_key = true
similarity_threshold = 0.88
similarity_prefilter = true

[merge]
# most_complete / source_priority / latest
master_policy = "most_complete"
fill_empty_from_others = true
```

A fully commented example is in [`examples/rules.toml`](examples/rules.toml).

---

## Output

### `master.csv` — cleaned master data

One row per customer. Chinese headers, plus two provenance columns at the end:

| Column | Meaning |
|---|---|
| `公司名称` … `更新时间` | Canonical fields. **Original values are preserved** — only formatting is cleaned, content is never rewritten |
| `_重复组` | Group ID if this row came from a duplicate group (`G0001`), otherwise blank |
| `_来源` | Which file and line the master came from (`customers_a.csv#2`) |

### `duplicates.html` — duplicate-group report

Written for business users. Each group lists all members, marks the master (★) and shows the field-level changes.
**Design rule: original values are never prettified** — people need to recognise their own data.

### `changes.csv` — change log

After a migration you must be able to answer "what exactly did this change?". Each row records the group size, the field, the action, old value, new value, and where the value was taken from.

---

## Design decisions (and why)

**Why zero dependencies?**
Data migrations usually run inside a customer's intranet where installing packages needs approval. A tool that needs no `pip install` actually gets used. TOML config, `difflib` similarity, `sqlite3` and HTML reports are all in the standard library.

**Why are brackets kept in company names by default?**
`云启科技(上海)` and `云启科技(北京)` are different legal entities. Stripping brackets would merge them. Turn on `strip_parentheses` only when brackets clearly hold remarks rather than regions or branches.

**Why keep original values instead of "cleaning" them up?**
The tool's job is to **merge duplicates**, not to **rewrite content**. Silently altering a customer's data is worse than leaving duplicates in place. So the master holds the original text, and every change is written to the change log.

**Why the first-character prefilter on layer 3?**
Pairwise comparison is O(N²). Company names starting with different characters are extremely unlikely to pass the threshold, so skipping them saves a great deal of work. It trades a little recall for a lot of speed; disable it with `similarity_prefilter = false`.

---

## Tests

```bash
python -m unittest discover -s tests -v
```

35 test cases covering normalisation rules, union-find transitivity, all three matching layers, end-to-end CLI runs, GBK-encoded input and cross-file column-name differences.
**No pytest required** — written with the standard library `unittest`.

---

## Known limitations

Listed honestly, to prevent misuse:

- **No judgement beyond fuzzy matching.** The similarity threshold always needs a human pass; the tool only narrows the work from "read every row" to "read the report".
- **CSV input only.** Excel files must be saved as CSV first.
- **Similarity uses `difflib.SequenceMatcher`**, a character-level comparison. It does not understand pinyin or abbreviations, so `郑煤机` vs `郑州煤矿机械集团` will not be caught.
- **No performance work.** Layer 3 is O(N²). Tens of thousands of rows are fine; hundreds of thousands would need an indexing strategy.
- **A personal project, never run in production.** The example data is fictional.

---

## Possible next steps

- [ ] Native `.xlsx` input (needs `openpyxl`; would break zero-dependency, so make it optional)
- [ ] Pinyin / abbreviation matching (`郑煤机` ↔ `郑州煤矿机械集团`)
- [ ] Write-back: emit a merge action list a CRM could execute
- [ ] CLI overrides: `--threshold 0.9` on top of the rules file

---

## License

MIT
