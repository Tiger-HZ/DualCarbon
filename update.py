# -*- coding: utf-8 -*-
"""统一更新入口：合并 inbox -> kb，再渲染站点。供每日任务/回填任务一键调用。
用法：python update.py
"""
import os, runpy

BASE = os.path.dirname(os.path.abspath(__file__))
for step in ("merge.py", "enrich_importance.py", "enrich_kg.py", "render.py"):
    runpy.run_path(os.path.join(BASE, step), run_name="__main__")

# 安全护栏：发布年份不得超过当前年份（未来年份多为学术库「forthcoming」误记），
# 也不得低于 1990；越界一律视为缺失并置空。发布时间以知识原文为准，规划目标年（2030/2050 等）不算作产生时间。
try:
    import json, re, datetime
    kb = json.load(open(os.path.join(BASE, "kb", "kb.json"), encoding="utf-8"))
    cur = datetime.date.today().year; n = 0
    for r in kb:
        d = r.get("date")
        if isinstance(d, str) and re.match(r"^\d{4}", d):
            y = int(d[:4])
            if y > cur or y < 1990:
                r["date"] = ""; n += 1
    if n:
        json.dump(kb, open(os.path.join(BASE, "kb", "kb.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print("cleaned future/invalid publication date:", n)
except Exception as e:
    print("date clean skipped:", e)
print("update done")
