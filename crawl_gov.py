# -*- coding: utf-8 -*-
"""国务院政策文件库(sousuo.www.gov.cn)双碳政策批量采集。

数据源：https://sousuo.www.gov.cn/search-gov/data?t=zhengcelibrary&...
返回 searchVO.catMap.{gongwen,bumenfile,gongbao,otherfile}.listVO[]，
每条含 title/url/pcode(文号)/pubtimeStr/puborg/summary/childtype。

流程：多关键词 × 多类目 × 多页 → 清洗 → 双碳相关性过滤 → 分类(部门/类别/地域/质量)
     → 与 kb.json+inbox.json 去重(norm_url + 文号事件指纹) → 追加写入 kb/inbox.json。
随后由 update.py 合并渲染。

用法：
  python crawl_gov.py                # 默认全部关键词，每类每词抓 PAGES 页
  python crawl_gov.py 碳达峰 碳市场   # 仅指定关键词
"""
import json, os, re, ssl, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge import norm_url, event_key  # 复用去重逻辑

BASE = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(BASE, "kb", "inbox.json")
KB = os.path.join(BASE, "kb", "kb.json")
STATE = os.path.join(BASE, "kb", "gov_crawl_state.json")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://sousuo.www.gov.cn/"}

API = ("https://sousuo.www.gov.cn/search-gov/data?t=zhengcelibrary"
       "&q=%s&p=%d&n=50&type=gwyzcwjk&sort=&sortType=1&searchfield=")

# 双碳关键词（覆盖政策/市场/协同/能源/工业/标准/金融等）
QUERIES = [
    "碳达峰", "碳中和", "碳排放", "减污降碳", "绿色低碳", "节能降碳",
    "可再生能源", "新能源", "碳市场", "碳交易", "碳汇", "温室气体",
    "应对气候变化", "碳足迹", "新型电力系统", "甲烷", "CCUS", "绿色金融",
    "能耗双控", "碳达峰试点", "零碳", "清洁能源", "新型储能", "绿色制造",
    "循环经济", "绿色建筑", "碳排放权", "低碳转型",
]
CATS_KEEP = ["gongwen", "bumenfile", "gongbao"]   # 公文/部门文件/公报；otherfile(解读)另计
CATS_LIT = ["otherfile"]                          # 政策解读 -> literature

# 双碳相关性词表（标题或摘要需命中，过滤宽泛查询带来的噪声）
REL = ["碳达峰", "碳中和", "碳排放", "减污降碳", "低碳", "降碳", "脱碳", "零碳",
       "温室气体", "甲烷", "气候变化", "碳汇", "碳市场", "碳交易", "碳足迹",
       "可再生能源", "新能源", "清洁能源", "新型电力系统", "新型储能", "光伏",
       "风电", "氢能", "ccus", "碳捕集", "节能", "能耗", "能效", "绿色低碳",
       "绿色制造", "绿色建筑", "绿色金融", "循环经济", "生态环境", "美丽中国"]

DEPTS = ["生态环境", "发改委", "经信", "市监", "住建", "交通", "农业",
         "能源", "科技", "金融", "商务", "其他"]

# 发布机构 / 标题关键词 -> 受控部门词表
DEPT_RULES = [
    (("生态环境部", "环境保护", "气候", "减污降碳"), "生态环境"),
    (("发展改革委", "发改委", "国家发展和改革"), "发改委"),
    (("工业和信息化部", "工信部", "工业和信息化", "工业领域"), "经信"),
    (("市场监督管理", "市场监管", "国家标准", "标准委", "认证认可"), "市监"),
    (("住房和城乡建设", "住建", "城乡建设", "建筑"), "住建"),
    (("交通运输", "民航", "铁路", "港口", "航运"), "交通"),
    (("农业农村", "林业和草原", "林草", "农业"), "农业"),
    (("能源局", "能源领域", "电力", "煤炭", "油气", "可再生能源"), "能源"),
    (("科学技术部", "科技部", "科技创新", "技术创新"), "科技"),
    (("人民银行", "银保监", "金融监督", "证监会", "外汇", "绿色金融", "财政部", "税务"), "金融"),
    (("商务部", "对外贸易", "外资"), "商务"),
]

# 类别关键词 -> 受控 category
CAT_RULES = [
    (("碳市场", "碳交易", "碳排放权", "ccer", "配额"), "carbon_market"),
    (("减污降碳", "协同增效", "协同治理"), "synergy"),
    (("标准", "计量", "核算方法", "技术规范", "指南（试行）", "核算指南"), "standard"),
    (("绿色金融", "气候投融资", "碳金融", "转型金融", "绿色债券", "绿色信贷"), "finance"),
    (("工业", "制造业", "钢铁", "石化", "建材", "有色", "重点行业"), "industry"),
    (("技术", "科技创新", "ccus", "碳捕集", "示范工程", "研发"), "tech"),
    (("国际", "全球", "一带一路", "多边", "公约", "cop"), "intl"),
]


def get(u, timeout=25, retries=3):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(u, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            last = e
            time.sleep(1.2 * (i + 1))
    raise last


def clean(s):
    s = s or ""
    s = re.sub(r"<[^>]+>", "", s)              # 去 <em>/<br/> 等标签
    s = s.replace("\u3000", " ").replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip()


def to_date(it):
    ds = it.get("pubtimeStr") or ""
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", ds)
    if m:
        return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    for k in ("pubtime", "ptime"):
        v = it.get(k)
        if isinstance(v, (int, float)) and v > 1_000_000_000_000:
            t = time.localtime(v / 1000.0)
            return time.strftime("%Y-%m-%d", t)
    return ""


def classify_dept(title, puborg):
    hay = (puborg or "") + " " + (title or "")
    for keys, dept in DEPT_RULES:
        if any(k in hay for k in keys):
            return dept
    return "其他"


def classify_cat(title, summary, is_lit):
    if is_lit:
        return "literature"
    hay = (title or "") + " " + (summary or "")
    for keys, cat in CAT_RULES:
        if any(k in hay for k in keys):
            return cat
    return "policy"


def is_relevant(title, summary):
    hay = ((title or "") + " " + (summary or "")).lower()
    return any(k.lower() in hay for k in REL)


def quality_of(cat, dept, is_lit):
    if is_lit:
        return "B"
    # 国家级政策/部门文件/公报默认高质量
    return "A"


def build_record(it, is_lit):
    title = clean(it.get("title"))
    if not title:
        return None
    url = (it.get("url") or "").strip()
    if not url:
        return None
    summary = clean(it.get("summary"))
    puborg = clean(it.get("puborg"))
    pcode = clean(it.get("pcode"))
    if not is_relevant(title, summary):
        return None
    date = to_date(it)
    dept = classify_dept(title, puborg)
    cat = classify_cat(title, summary, is_lit)
    qual = quality_of(cat, dept, is_lit)
    if not summary:
        summary = ("%s发布%s。" % (puborg or "国家有关部门", title)) + (("文号：%s。" % pcode) if pcode else "")
    tags = ["双碳", "国家政策"]
    if pcode:
        tags.append(pcode)
    if puborg:
        tags.append(puborg)
    ev = ("ev:" + pcode.lower()) if pcode else event_key(title)
    rec = {
        "title": title,
        "url": url,
        "source": (puborg or "中国政府网 · 国务院政策文件库"),
        "date": date,
        "category": cat,
        "department": dept,
        "region": "全国",
        "quality": qual,
        "summary": summary,
        "tags": tags,
        "content": summary,
        "content_fetched": False,
        "added_at": date or "",   # 用发布日期归档，历史条目分布到各自时间轴
        "_ev": ev,
    }
    return rec


def load(p):
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return []
    return []


def main():
    queries = sys.argv[1:] or QUERIES
    pages = int(os.environ.get("GOV_PAGES", "3"))

    kb = load(KB)
    inbox = load(INBOX)

    # 去重索引：kb + 现有 inbox
    seen_url, seen_ev = set(), set()
    for r in kb + inbox:
        nu = norm_url(r.get("url", ""))
        if nu:
            seen_url.add(nu)
        ev = r.get("_ev")
        if ev:
            seen_ev.add(ev)

    added = 0
    per_year = {}
    for q in queries:
        qq = urllib.parse.quote(q)
        cat_plan = [(c, False) for c in CATS_KEEP] + [(c, True) for c in CATS_LIT]
        for pg in range(1, pages + 1):
            try:
                raw = get(API % (qq, pg))
                d = json.loads(raw)
            except Exception as e:
                print("  [warn] q=%s p=%d %s" % (q, pg, type(e).__name__))
                break
            cm = (d.get("searchVO") or {}).get("catMap") or {}
            got_any = False
            for cat_key, is_lit in cat_plan:
                lv = (cm.get(cat_key) or {}).get("listVO") or []
                for it in lv:
                    got_any = True
                    rec = build_record(it, is_lit)
                    if not rec:
                        continue
                    nu = norm_url(rec["url"])
                    if nu and nu in seen_url:
                        continue
                    if rec["_ev"] in seen_ev:
                        continue
                    seen_url.add(nu)
                    seen_ev.add(rec["_ev"])
                    inbox.append(rec)
                    added += 1
                    yr = (rec["date"] or "")[:4] or "?"
                    per_year[yr] = per_year.get(yr, 0) + 1
            if not got_any:
                break
            time.sleep(0.25)
        print("q=%s done, cumulative added=%d" % (q, added))

    json.dump(inbox, open(INBOX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("=" * 50)
    print("crawl_gov: added=%d, inbox_total=%d" % (added, len(inbox)))
    print("by year:", dict(sorted(per_year.items(), reverse=True)))


if __name__ == "__main__":
    main()
