# -*- coding: utf-8 -*-
"""双碳领域知识库 · 静态站点渲染脚本（纯标准库，从 kb/kb.json 渲染）。
核心视图：
 - index.html       ：每日推送首页（最新一期 + 历史推送导航 + 可回看任意一天）
 - push-YYYY-MM-DD.html ：单日推送（该日新增/入库的知识，支持前后日导航、筛选）
 - archive.html     ：全部知识库（按发布日期时间轴 + 时段/分类/部门/地区/质量筛选）
增量机制：kb/kb.json 只增不删（merge.py 去重），render 每次由最新 added_at 生成推送。
用法：python render.py
"""
import json, os, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(BASE, "kb", "kb.json")
CONFIG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
FEEDBACK = CONFIG.get("feedback_url", "")
OWNER = CONFIG.get("owner_email", "")
PNAME = CONFIG.get("project_name", "双碳领域知识库")

# 八大分类：知识门类（顶层），逻辑由基础制度→市场→协同→行业→技术→文献→动态
CATS = [
    ("policy", "政策规划与顶层设计", "#1a7f5a"),
    ("standard", "法规与标准", "#0f766e"),
    ("carbon_market", "碳市场与气候投融资", "#2563eb"),
    ("synergy", "减污降碳协同", "#7c3aed"),
    ("industry", "行业低碳与节能降碳", "#b45309"),
    ("tech", "技术、产品与创新", "#0891b2"),
    ("literature", "研究文献（开源）", "#db2777"),
    ("intl_region", "国际与区域动态", "#475569"),
]
CATNAME = {c[0]: c[1] for c in CATS}
CATCOLOR = {c[0]: c[2] for c in CATS}
CAT_ORDER = {c[0]: i for i, c in enumerate(CATS)}
QUAL_NAME = {"A": "高", "B": "中", "C": "一般"}

# 部门优先级维度：生态环境条线优先，发改/经信(工信)/市场监管/商务为重点，其余一般
PRIORITY = [
    ("生态环境部门", "#1a7f5a", ("生态", "环境")),
    ("发展改革委", "#0f766e", ("发改",)),
    ("经信(工信)", "#2563eb", ("经信", "工信")),
    ("市场监管局", "#b45309", ("市场监管",)),
    ("其他相关部门", "#64748b", ()),
]


def scope_of(dept):
    d = dept or ""
    for name, color, keys in PRIORITY:
        if any(k in d for k in keys):
            return name, color
    return PRIORITY[-1][0], PRIORITY[-1][1]


def priority_rank(dept):
    """部门优先级排序：生态环境部门(0) > 发展改革委(1) > 经信(工信)(2) > 市场监管局(3) > 其他(4)。"""
    d = dept or ""
    for idx, (name, color, keys) in enumerate(PRIORITY):
        if any(k in d for k in keys):
            return idx
    return len(PRIORITY) - 1


def load_kb():
    if os.path.exists(KB):
        try:
            return json.load(open(KB, encoding="utf-8"))
        except Exception:
            return []
    return []


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def card(item):
    q = item.get("quality", "C")
    cat = item.get("category", "")
    title = esc(item.get("title", ""))
    url = esc(item.get("url", "#"))
    source = esc(item.get("source", ""))
    date = esc(item.get("date", ""))
    dept = esc(item.get("department", ""))
    region = esc(item.get("region", ""))
    summary = esc(item.get("summary", ""))
    tags = "".join('<span class="tag">%s</span>' % esc(t) for t in item.get("tags", []))
    scope_name, scope_color = scope_of(item.get("department", ""))
    full = item.get("content_fetched")
    fullbadge = '<span class="full yes">全文入库</span>' if full else '<span class="full no">摘要</span>'
    text = (item.get("title", "") + " " + item.get("summary", "") + " " + source + " " +
            " ".join(item.get("tags", []))).lower()
    return ('''<article class="card" data-cat="%s" data-dept="%s" data-region="%s" '''
            'data-qual="%s" data-date="%s" data-text="%s">'
            '<div class="card-top"><span class="badge" style="background:%s">%s</span>'
            '<span class="q q-%s">质量 %s</span><span class="scope" style="background:%s;color:#fff">%s</span></div>'
            '<h3 class="card-title"><a href="%s" target="_blank" rel="noopener">%s</a></h3>'
            '<div class="meta">%s · %s · <span class="dept">%s</span> · <span class="region">%s</span> · %s</div>'
            '<p class="summary">%s</p><div class="tags">%s</div></article>') % (
        cat, dept, region, q, date, esc(text), CATCOLOR.get(cat, "#475569"),
        CATNAME.get(cat, cat), q, QUAL_NAME.get(q, q), scope_color, scope_name,
        url, title, source, date, dept, region, fullbadge, summary, tags)


CSS = """
:root{--green:#1a7f5a;--green-d:#136046;--bg:#f6f8f7;--panel:#fff;--line:#e3e8e6;--text:#16201c;--muted:#6b7b75}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);line-height:1.65}
a{color:#0f766e;text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px 70px}
header.top{background:linear-gradient(135deg,#1a7f5a,#0f766e);color:#fff;padding:26px 20px 22px}
header.top .inner{max-width:1180px;margin:0 auto}
header.top h1{margin:0;font-size:23px;font-weight:700;letter-spacing:.5px}
header.top p{margin:6px 0 0;opacity:.92;font-size:13.5px}
header.top .up{margin-top:10px;font-size:12.5px;opacity:.85}
.statbar{max-width:1180px;margin:14px auto;padding:0 20px;display:flex;gap:10px;flex-wrap:wrap}
.chip{background:#fff;border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-size:13px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
.chip b{color:var(--green-d)}
.bar{position:sticky;top:0;z-index:20;background:rgba(246,248,247,.96);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);padding:12px 0;margin-bottom:14px}
.bar .inner{max-width:1180px;margin:0 auto;padding:0 20px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input#search{flex:1;min-width:200px;padding:9px 12px;border:1px solid var(--line);border-radius:9px;font-size:14px}
select{padding:9px 10px;border:1px solid var(--line);border-radius:9px;font-size:13.5px;background:#fff}
.pills{display:flex;gap:6px;flex-wrap:wrap}
.pill{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 12px;font-size:12.5px;cursor:pointer;color:#334}
.pill.active{background:var(--green);color:#fff;border-color:var(--green)}
.winbtns{display:flex;gap:6px;flex-wrap:wrap}
.winbtn{border:1px solid var(--line);background:#fff;border-radius:8px;padding:6px 10px;font-size:12.5px;cursor:pointer;color:#334}
.winbtn.active{background:#0f766e;color:#fff;border-color:#0f766e}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
section.block{margin:22px 0 8px}
section.block h2{color:var(--green-d);font-size:17px;margin:0 0 10px;padding-bottom:6px;border-bottom:2px solid #d7e7df}
section.block h2 .cnt{color:var(--muted);font-size:13px;font-weight:400;margin-left:8px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:14px 15px;box-shadow:0 1px 3px rgba(0,0,0,.04);transition:transform .12s,box-shadow .12s;display:flex;flex-direction:column}
.card:hover{transform:translateY(-2px);box-shadow:0 6px 18px rgba(20,80,60,.12)}
.card-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:7px;gap:6px;flex-wrap:wrap}
.badge{color:#fff;border-radius:7px;padding:3px 9px;font-size:12px;font-weight:600}
.q{font-size:11.5px;padding:2px 8px;border-radius:6px;font-weight:600}
.q-A{background:#dcfce7;color:#166534}.q-B{background:#fef9c3;color:#854d0e}.q-C{background:#e5e7eb;color:#4b5563}
.scope{font-size:11px;padding:2px 8px;border-radius:6px;font-weight:600}
.full{font-size:10.5px;padding:1px 7px;border-radius:5px;font-weight:600}
.full.yes{background:#e7f6ee;color:#136046}.full.no{background:#f1f5f4;color:#8a978f}
.card-title{margin:0 0 6px;font-size:15.5px;line-height:1.45}
.card-title a{color:#0f2e25}
.meta{font-size:12px;color:var(--muted);margin-bottom:7px}
.dept{background:#eef6f1;color:#136046;border-radius:5px;padding:1px 7px}
.region{background:#eff4fb;color:#1d4ed8;border-radius:5px;padding:1px 7px}
.summary{font-size:13.5px;color:#37403c;margin:0 0 9px;flex:1}
.tags{display:flex;gap:5px;flex-wrap:wrap}
.tag{background:#f1f5f4;color:#52635c;border-radius:5px;padding:1px 7px;font-size:11.5px}
.fab{position:fixed;right:22px;bottom:22px;z-index:50;background:var(--green);color:#fff;border:none;border-radius:999px;padding:13px 18px;font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 6px 18px rgba(20,80,60,.35)}
.fab:hover{background:var(--green-d)}
.empty{text-align:center;color:var(--muted);padding:40px;font-size:14px}
footer{margin-top:40px;border-top:1px solid var(--line);padding-top:16px;color:var(--muted);font-size:12.5px;text-align:center}
footer a{color:#0f766e}
.count{font-size:13px;color:var(--muted);margin:0 20px 8px;max-width:1180px}
.pushnav{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 4px}
.pday{border:1px solid var(--line);background:#fff;border-radius:8px;padding:7px 12px;font-size:13px;cursor:pointer;color:#334;text-decoration:none}
.pday:hover{background:#eef6f1;border-color:var(--green)}
.pday.cur{background:var(--green);color:#fff;border-color:var(--green)}
.pday b{color:var(--green-d)}
.pday.cur b{color:#fff}
.phead{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:18px 0 2px}
.phead h2{margin:0;color:var(--green-d);font-size:18px}
.phead .sub{color:var(--muted);font-size:13px}
.pager{display:flex;gap:10px;margin:10px 0 4px}
.pager a{border:1px solid var(--line);background:#fff;border-radius:8px;padding:7px 13px;font-size:13px;color:#136046;text-decoration:none}
.pager a:hover{background:#eef6f1}
.pager .dis{color:#b9c2be;border:1px dashed var(--line);background:#fafbfa}
.note{background:#eef6f1;border:1px solid #d7e7df;color:#136046;border-radius:9px;padding:9px 13px;font-size:13px;margin:10px 0}
"""

JS = """
<script>
function applyFilter(){
  var q=(document.getElementById('search').value||'').toLowerCase().trim();
  var dept=document.getElementById('fdept').value;
  var region=document.getElementById('fregion').value;
  var qual=document.getElementById('fqual').value;
  var cat=document.getElementById('fcat').value;
  var win=document.getElementById('fwin')?document.getElementById('fwin').value:'all';
  var now=new Date(); var y=now.getFullYear();
  var cards=document.querySelectorAll('.card');
  var count=0;
  cards.forEach(function(c){
    var ok=true;
    if(q && c.dataset.text.indexOf(q)===-1) ok=false;
    if(cat && c.dataset.cat!==cat) ok=false;
    if(dept && c.dataset.dept!==dept) ok=false;
    if(region && c.dataset.region!==region) ok=false;
    if(qual && c.dataset.qual!==qual) ok=false;
    if(win && win!=='all'){
      var d=new Date(c.dataset.date); if(isNaN(d)) ok=false;
      var days=(now-d)/86400000;
      if(win==='7'&&days>7)ok=false;
      else if(win==='30'&&days>30)ok=false;
      else if(win==='90'&&days>90)ok=false;
      else if(win==='180'&&days>180)ok=false;
      else if(win==='2026'&&d.getFullYear()!==2026)ok=false;
      else if(win==='2025'&&d.getFullYear()!==2025)ok=false;
      else if(win==='2024'&&d.getFullYear()!==2024)ok=false;
      else if(win==='2023'&&d.getFullYear()!==2023)ok=false;
      else if(win==='3y'&&days>365*3)ok=false;
      else if(win==='older'&&d.getFullYear()>=2023)ok=false;
    }
    c.style.display=ok?'':'none';
    if(ok)count++;
  });
  document.querySelectorAll('section.block').forEach(function(s){
    var any=Array.prototype.some.call(s.querySelectorAll('.card'),function(c){return c.style.display!=='none';});
    s.style.display=any?'':'none';
  });
  var ce=document.getElementById('count'); if(ce) ce.textContent='当前显示 '+count+' 条';
}
function bind(){
  document.getElementById('search').addEventListener('input',applyFilter);
  ['fdept','fregion','fqual','fcat'].forEach(function(id){var e=document.getElementById(id);if(e)e.addEventListener('change',applyFilter);});
  var w=document.getElementById('fwin'); if(w) w.addEventListener('change',applyFilter);
  document.querySelectorAll('.pill').forEach(function(p){
    p.addEventListener('click',function(){
      document.querySelectorAll('.pill').forEach(function(x){x.classList.remove('active');});
      p.classList.add('active');
      document.getElementById('fcat').value=p.dataset.cat;
      applyFilter();
    });
  });
  document.querySelectorAll('.winbtn').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('.winbtn').forEach(function(x){x.classList.remove('active');});
      b.classList.add('active');
      document.getElementById('fwin').value=b.dataset.win;
      applyFilter();
    });
  });
  applyFilter();
}
document.addEventListener('DOMContentLoaded',bind);
</script>
"""

WINDOWS = [
    ("all", "全部"), ("7", "近7天"), ("30", "近1月"), ("90", "近3月"),
    ("180", "近半年"), ("2026", "2026年"), ("2025", "2025年"),
    ("2024", "2024年"), ("2023", "2023年"), ("3y", "近三年"), ("older", "2023年前"),
]


def dept_region_options(items):
    depts = sorted(set(i.get("department", "") for i in items if i.get("department")))
    regions = sorted(set(i.get("region", "") for i in items if i.get("region")))
    return depts, regions


def year_stats(items):
    ys = {}
    for i in items:
        y = (i.get("date") or "")[:4]
        if y.isdigit():
            ys[y] = ys.get(y, 0) + 1
    return ys


def build_filters(with_window=True, with_cat=True):
    dept_opts = "".join('<option value="%s">%s</option>' % (esc(d), esc(d)) for d in DEPTS)
    region_opts = "".join('<option value="%s">%s</option>' % (esc(r), esc(r)) for r in REGIONS)
    qual_opts = "".join('<option value="%s">质量 %s</option>' % (k, v) for k, v in QUAL_NAME.items())
    cat_pills = '<button class="pill active" data-cat="">全部门类</button>' + "".join(
        '<button class="pill" data-cat="%s">%s</button>' % (c[0], c[1]) for c in CATS)
    win_btns = "".join('<button class="winbtn" data-win="%s">%s</button>' % (w[0], w[1]) for w in WINDOWS)
    inner = '<input id="search" placeholder="搜索标题 / 摘要 / 标签 / 来源 / 部门…">'
    if with_cat:
        inner += '<div class="pills">%s</div>' % cat_pills
    if with_window:
        inner += '<div class="winbtns">%s</div>' % win_btns
    inner += ('<select id="fdept"><option value="">全部部门</option>%s</select>'
              '<select id="fregion"><option value="">全部地区</option>%s</select>'
              '<select id="fqual"><option value="">全部质量</option>%s</select>'
              '<input type="hidden" id="fcat" value="">') % (dept_opts, region_opts, qual_opts)
    return inner


def push_nav(days, current):
    parts = []
    for d in days:
        n = len(PUSHES[d])
        cls = "pday cur" if d == current else "pday"
        parts.append('<a class="%s" href="push-%s.html">%s <b>%d</b></a>'
                     % (cls, esc(d), esc(d), n))
    return '<div class="pushnav">%s</div>' % "".join(parts)


def pager(days, day):
    idx = days.index(day)
    newer = days[idx - 1] if idx - 1 >= 0 else None   # 更晚的日期
    older = days[idx + 1] if idx + 1 < len(days) else None  # 更早的日期
    left = ('<a href="push-%s.html">← 更早：%s</a>' % (esc(older), esc(older))) if older else '<span class="dis">← 最早</span>'
    right = ('<a href="push-%s.html">更新：%s →</a>' % (esc(newer), esc(newer))) if newer else '<span class="dis">最新 →</span>'
    return '<div class="pager">%s %s</div>' % (left, right)


def build_index(kb, days):
    latest_day = days[0]
    latest = PUSHES[latest_day]
    ys = year_stats(kb)
    full_n = sum(1 for i in kb if i.get("content_fetched"))
    ychips = " ".join('<span class="chip">%s年 <b>%d</b></span>' % (y, n) for y, n in sorted(ys.items()))
    body = (
        '<div class="statbar">'
        '<span class="chip">知识总量 <b>%d</b> 条</span>'
        '<span class="chip">全文入库 <b>%d</b> 条</span>'
        '<span class="chip">推送期数 <b>%d</b> 期</span>'
        '<span class="chip">覆盖年份 <b>%s</b></span></div>' % (
            len(kb), full_n, len(days), "、".join(sorted(ys.keys())))
        + (('<div class="statbar">%s</div>' % ychips) if ychips else '')
        + '<div class="bar"><div class="inner">%s'
          '<a href="archive.html" style="font-size:13px">全部知识库 / 时间轴 →</a>'
          '<a href="rag.html" style="margin-left:auto;font-size:13px;font-weight:700;color:#1a7f5a">🧠 RAG 智能检索（向量+关键词+元数据）→</a>'
          '</div></div>' % build_filters(with_window=False, with_cat=True)
        + '<div class="count" id="count"></div>'
        + '<div class="phead"><h2>最新推送</h2><span class="sub">%s · 当日新增 %d 条</span></div>'
          % (esc(latest_day), len(latest))
        + '<div class="grid">%s</div>' % "".join(card(i) for i in latest)
        + '<div class="note">📅 回看历史推送：点击下方任意日期，即可查看当日新增/入库的知识（今天也能看昨天的推送）。</div>'
        + '<div class="phead"><h2>历史推送</h2><span class="sub">共 %d 期</span></div>' % len(days)
        + push_nav(days, latest_day)
        + ''
    )
    return shell("每日推送", body)


def build_push_day(day, items, days):
    depts, regions = dept_region_options(items)
    sections = ""
    for cid, cname, _ in CATS:
        sub = sorted([i for i in items if i.get("category") == cid],
                     key=lambda x: x.get("date", ""), reverse=True)
        sub.sort(key=lambda x: priority_rank(x.get("department", "")), reverse=False)
        if not sub:
            continue
        sections += ('<section class="block"><h2>%s<span class="cnt">%d 条</span></h2>'
                     '<div class="grid">%s</div></section>') % (cname, len(sub), "".join(card(i) for i in sub))
    body = (
        '<div class="statbar"><span class="chip">本日推送 <b>%d</b> 条</span>'
        '<span class="chip">分类 <b>%d</b> 类</span></div>' % (len(items), len(CATS))
        + '<div class="bar"><div class="inner">%s'
          '<a href="index.html" style="margin-left:auto;font-size:13px">← 返回每日推送</a>'
          '</div></div>' % build_filters(with_window=False, with_cat=True)
        + '<div class="count" id="count"></div>'
        + '<div class="phead"><h2>每日推送 · %s</h2><span class="sub">该日新增 / 入库的知识</span></div>'
          % esc(day)
        + pager(days, day)
        + (sections or '<div class="empty">当日无内容</div>')
        + '<div class="note">本页为 <b>%s</b> 的推送内容。回看其它日期请使用上方翻页或'
          '<a href="index.html">首页历史推送</a>。</div>'
          % esc(day)
    )
    return shell("每日推送 · " + day, body)


def build_archive(kb):
    items = sorted(kb, key=lambda x: x.get("date", ""), reverse=True)
    depts, regions = dept_region_options(items)
    by_date = {}
    for i in items:
        by_date.setdefault(i.get("date", "未知日期"), []).append(i)
    dates = sorted(by_date.keys(), reverse=True)
    sections = ""
    for dt in dates:
        sub = sorted(by_date[dt], key=lambda x: (CAT_ORDER.get(x.get("category"), 99), priority_rank(x.get("department", ""))))
        sections += ('<section class="block"><h2>%s<span class="cnt">%d 条</span></h2>'
                     '<div class="grid">%s</div></section>') % (dt, len(sub), "".join(card(i) for i in sub))
    body = (
        '<div class="statbar"><span class="chip">历史累计 <b>%d</b> 条</span>'
        '<span class="chip">覆盖 <b>%d</b> 个发布日期</span></div>' % (len(items), len(dates))
        + '<div class="bar"><div class="inner">%s'
          '<a href="index.html" style="margin-left:auto;font-size:13px">← 返回每日推送</a>'
          '</div></div>' % build_filters(with_window=True, with_cat=True)
        + '<div class="bar"><div class="inner" style="top:64px"></div></div>'
        + '<div class="count" id="count"></div>'
        + sections
    )
    return shell("全部知识库 · 时间轴", body)


def shell(subtitle, body):
    up = ("双碳知识中台 ｜ 生成于 %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    html = (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>%s</title><style>%s</style></head><body>' % (PNAME, CSS)
        + '<header class="top"><div class="inner"><h1>%s</h1><p>%s · %s</p>'
          '<div class="up">%s</div></div></header>' % (PNAME, CONFIG.get("description", ""), subtitle, up)
        + '<div class="wrap">' + body + '</div>'
        + '<button class="fab" onclick="location.href=\'%s\'">💬 留言反馈</button>' % FEEDBACK
        + '<footer>双碳领域知识库 · 自动采集更新（内容入库，支持 <a href="rag.html" style="color:#fff;text-decoration:underline">RAG 智能检索</a> / 报告生成）｜ 团队反馈：'
          '<a href="%s" target="_blank" rel="noopener">填写问卷</a> ｜ 负责人邮箱 '
          '<a href="mailto:%s">%s</a><br>%s</footer>' % (
            FEEDBACK, OWNER, OWNER, CONFIG.get("update_note", ""))
        + JS + '</body></html>'
    )
    return html


# 模块级缓存（在 main 中初始化），供 build_filters 使用
DEPTS, REGIONS = [], []
PUSHES = {}


def main():
    global DEPTS, REGIONS, PUSHES
    kb = load_kb()
    if not kb:
        print("no kb")
        return
    DEPTS, REGIONS = dept_region_options(kb)
    # 按收录日(added_at)分组，形成"每日推送"
    PUSHES = {}
    for i in kb:
        key = i.get("added_at") or i.get("date") or "未知日期"
        PUSHES.setdefault(key, []).append(i)
    days = sorted(PUSHES.keys(), reverse=True)
    open(os.path.join(BASE, "index.html"), "w", encoding="utf-8").write(build_index(kb, days))
    for day in days:
        open(os.path.join(BASE, "push-%s.html" % day), "w", encoding="utf-8").write(
            build_push_day(day, PUSHES[day], days))
    open(os.path.join(BASE, "archive.html"), "w", encoding="utf-8").write(build_archive(kb))
    print("rendered: index.html, %d push pages, archive.html (kb total=%d)" % (len(days), len(kb)))


if __name__ == "__main__":
    main()
