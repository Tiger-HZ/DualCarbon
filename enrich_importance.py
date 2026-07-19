# -*- coding: utf-8 -*-
"""给 kb.json 每条记录计算 importance，写回 kb.json，供静态站点按重要性排序。

排序意图：部门权重 + 质量 + 时效 + **碳相关度**。
新增「碳相关度(carbon_rel)」维度：即便来源权威（政府网站），若正文/标题与"碳/双碳"
关系不大（如《群众身边水体保护治理行动方案》），也应降低展示优先级。
实现方式（符合用户"把质量分调低"的思路）：
  1) 计算 carbon_rel ∈ [0,1]（标题命中核心碳词=强信号；否则按正文碳词密度打分）；
  2) 低相关度记录：有效质量分逐档下调（A→B→C），并对最终 importance 乘惩罚系数；
  3) 幂等：首次运行把原始质量存入 quality_src，之后每次都基于 quality_src + carbon_rel 重算。
update.py 会在 merge 之后自动调用本脚本。
"""
import os, json, datetime, sys

BASE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(BASE, "kb", "kb.json")

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

# 除"碳"字之外的核心气候词（不含"碳"字，避免与"碳"计数重复）
CLIMATE = ["温室气体", "甲烷", "气候变化", "气候投融资", "应对气候", "CCUS", "CBAM",
           "碳边境", "净零", "零碳", "近零碳"]
# 支撑词（弱信号）：与低碳转型相关但非专指碳
SUPPORT = ["减排", "节能", "能耗", "能效", "新能源", "可再生能源", "清洁能源", "光伏",
           "风电", "储能", "氢能", "绿色转型", "绿色低碳", "电动汽车", "换电",
           "绿色发展", "ESG", "循环经济", "资源综合利用", "绿证", "绿电", "含绿量"]


def _count(text, terms):
    return sum(text.count(t) for t in terms)


def carbon_rel(rec):
    """碳相关度 ∈ [0,1]。主信号=正文"碳"字频次；辅以气候词、支撑词。
    标题只要出现"碳"或核心气候词即判为高相关。"""
    title = rec.get("title") or ""
    summary = rec.get("summary") or ""
    content = rec.get("content") or ""
    if title.count("碳") >= 1 or _count(title, CLIMATE) >= 1:
        return 1.0
    body = title + " " + summary + " " + content
    core = body.count("碳") + _count(body, CLIMATE)
    support = _count(body, SUPPORT)
    raw = core * 1.0 + support * 0.4
    if raw >= 5:
        return 1.0
    if raw <= 0:
        return 0.3
    return round(0.3 + 0.7 * (raw / 5.0), 2)


def _downgrade(q, steps):
    order = ["A", "B", "C"]
    try:
        i = order.index(q)
    except ValueError:
        i = 1
    return order[min(2, i + steps)]


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
    dept = norm_dept(rec.get("department"))
    rec["department"] = dept
    region = norm_region(rec.get("region"))
    rec["region"] = region

    # 原始质量（幂等保存）
    src_q = rec.get("quality_src") or rec.get("quality") or "B"
    if src_q not in QUAL:
        src_q = "B"
    rec["quality_src"] = src_q

    rel = carbon_rel(rec)
    rec["carbon_rel"] = rel

    # 低相关度：有效质量下调
    if rel < 0.35:
        q = _downgrade(src_q, 2)
    elif rel < 0.6:
        q = _downgrade(src_q, 1)
    else:
        q = src_q
    rec["quality"] = q

    base = DEPT.get(dept, 1) + QUAL.get(q, 1) * 0.7 + timeliness(rec.get("date") or rec.get("added_at") or "")
    # 相关度惩罚系数：rel=1→1.0，rel=0.3→0.58
    factor = 0.4 + 0.6 * rel
    return round(base * factor, 2)


def main():
    data = json.load(open(KB, encoding="utf-8"))
    lowrel = 0
    for r in data:
        r["importance"] = importance(r)
        if r.get("carbon_rel", 1) < 0.6:
            lowrel += 1
    json.dump(data, open(KB, "w", encoding="utf-8"), ensure_ascii=False)
    print("enriched importance for", len(data), "records; low-carbon-relevance demoted:", lowrel)


if __name__ == "__main__":
    main()
