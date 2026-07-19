# -*- coding: utf-8 -*-
"""统一更新入口：合并 inbox -> kb，再渲染站点。供每日任务/回填任务一键调用。
用法：python update.py
"""
import os, runpy

BASE = os.path.dirname(os.path.abspath(__file__))
for step in ("merge.py", "enrich_importance.py", "enrich_kg.py", "render.py"):
    runpy.run_path(os.path.join(BASE, step), run_name="__main__")
print("update done")
