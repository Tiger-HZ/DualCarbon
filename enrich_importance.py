# -*- coding: utf-8 -*-
"""给 kb.json 每条记录计算 importance（部门权重 + 质量×0.7 + 内容时效），
写回 kb.json，供静态站点（无后端）按重要性排序。
公式与后端 pipeline/process.py 的 importance() 保持一致，时效改用内容发布日期(date)，
使较早年份(2023-2025)在时效性上自然低于新内容，符合"质量/关联性/时效性"排序意图。
update.py 会在 merge 之后自动调用本脚本，确保每日更新都带 importance。
"""
import os, json, datetime, sys

BASE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(BASE, "kb", "kb.json")

# 复用 stage.py 的受控词表归一化，确保与 SPA 的 DEPTS 完全一致
sys.path.insert(0, BASE)
try:
    import stage as _stage
    norm_dept = _stage.norm_dept
    norm_region = _stage.norm_region
except Exception:
    def norm_dept(s):
        return (s or "其他").strip() or "其他"
    def norm_region(s):
        return (s or "全国").strip() or "全国"

DEPT = {"生态环境": 5, "发改委": 4, "经信": 3, "市监": 2, "住建": 1, "交通": 1,
        "农业": 1, "能源": 1, "科技": 1, "金融": 1, "商务": 1, "其他": 1}
QUAL = {"A": 3, "B": 2, "C": 1}


def timeliness(date_str):
    try:
        d = datetime.date.fromisoformat(date_str)
    except Exception:
        return 0
    days = (datetime.date.today() - d).days
    if days <= 365:
        return 2
    if days <= 730:
        return 1
    return 0


def importance(rec):
    # 先归一化到受控词表，避免原始部门名（如「生态环境部」「国家发改委」）落到默认权重 1
    dept = norm_dept(rec.get("department"))
    rec["department"] = dept
    region = norm_region(rec.get("region"))
    rec["region"] = region
    qual = rec.get("quality") or "B"
    base = DEPT.get(dept, 1) + QUAL.get(qual, 1) * 0.7
    return round(base + timeliness(rec.get("date") or rec.get("added_at") or ""), 2)


def main():
    data = json.load(open(KB, encoding="utf-8"))
    for r in data:
        r["importance"] = importance(r)
    json.dump(data, open(KB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("enriched importance for", len(data), "records (dept/region normalized)")


if __name__ == "__main__":
    main()
