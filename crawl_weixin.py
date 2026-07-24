# -*- coding: utf-8 -*-
"""采集微信公众号双碳相关文章（经由搜狗微信搜索），归一化后追加到 inbox.json。
搜狗微信无需登录即可返回文章列表；文章链接经 /link?url= 重定向到 mp.weixin.qq.com 原文。
用法：python crawl_weixin.py [额外关键词 ...]   环境变量 PAGES 控制每词翻页数(默认3)
"""
import os, sys, json, time, ssl, urllib.request, urllib.parse, re, datetime
BASE = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(BASE, "kb", "inbox.json")
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
sys.path.insert(0, BASE)
import weixin  # 微信采集辅助：会话/反爬识别/真实 URL 解析/正文抽取
QUERIES = ["碳中和", "碳达峰", "碳排放权交易", "绿色低碳", "节能降碳", "碳足迹",
           "新型电力系统", "零碳园区", "绿色金融 碳", "碳市场"]
PAGES = int(os.environ.get("PAGES", "3"))
DEPT_RE = {"生态环境": "生态环境", "环境": "生态环境", "发改委": "发改委", "发展改革": "发改委",
           "能源": "能源", "工信": "经信", "工业": "经信", "市场监管": "市监", "住建": "住建",
           "交通": "交通", "农业农村": "农业", "科技": "科技", "金融": "金融", "商务": "商务"}

def get(u, to=20):
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=to, context=CTX) as r:
        return r.read().decode("utf-8", "ignore")

def norm_url(u):
    u = (u or "").strip()
    u = re.split(r"[?#]", u)[0]
    return u.rstrip("/").lower()

def resolve(url, session):
    """用搜狗 cookie 会话尽量解析真实 mp.weixin.qq.com 文章地址。
    解析不到（被反爬）返回 None——调用方应保留 sogou 链接且不声称已拿到全文。"""
    return session.resolve(url)

def main():
    existing = set()
    kb = json.load(open(os.path.join(BASE, "kb", "kb.json"), encoding="utf-8")) if os.path.exists(os.path.join(BASE, "kb", "kb.json")) else []
    for r in kb:
        if r.get("url"): existing.add(norm_url(r["url"]))
        if r.get("title"): existing.add(r["title"].strip().lower())
    inbox = json.load(open(INBOX, encoding="utf-8")) if os.path.exists(INBOX) else []
    for r in inbox:
        if r.get("url"): existing.add(norm_url(r["url"]))
        if r.get("title"): existing.add(r["title"].strip().lower())

    extra = sys.argv[1:]
    queries = QUERIES + extra
    # 复用同一会话：先 seed 一次搜索拿 cookie，再反复解析链接（降低被反爬概率）
    session = weixin.WeixinSession()
    session.seed()
    ITEM_RE = re.compile(
        r'<h3>\s*<a[^>]*href="(/link\?url=[^"]+)"[^>]*>(.*?)</a>\s*</h3>'
        r'.*?class="txt-info"[^>]*>(.*?)</p>'
        r'.*?class="all-time-y2"[^>]*>([^<]+)'
        r'.*?timeConvert\(\'(\d+)\'\)', re.S)
    added = 0
    for q in queries:
        for pg in range(1, PAGES + 1):
            su = "https://weixin.sogou.com/weixin?type=2&page=%d&query=%s" % (pg, urllib.parse.quote(q))
            try:
                html = get(su)
            except Exception as e:
                print("FAIL %s %s" % (q, str(e)[:50])); break
            for link, rawtitle, rawsum, acct, ts in ITEM_RE.findall(html):
                link = link.replace("&amp;", "&")
                title = re.sub(r"<[^>]+>", "", rawtitle).strip()
                if not title or len(title) < 6:
                    continue
                if title.strip().lower() in existing:
                    continue
                full = "https://weixin.sogou.com" + link
                real = resolve(full, session)
                # 尽量解析真实 mp 文章地址；解析不到（被反爬）则保留 sogou 链接，
                # 但 content_fetched 保持 False，绝不把验证码页当正文写入。
                if real and "mp.weixin.qq.com" in real:
                    dedup_key = norm_url(real)
                    url = real
                    resolved = True
                else:
                    dedup_key = full
                    url = full
                    resolved = False
                if dedup_key in existing:
                    continue
                summary = re.sub(r"<[^>]+>", "", rawsum).strip()
                account = acct.strip() or "微信公众号"
                try:
                    date = datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%d")
                except Exception:
                    date = "2026-07-19"
                dept = "其他"
                for k, v in DEPT_RE.items():
                    if k in (account + title):
                        dept = v; break
                rec = {
                    "title": title,
                    "url": url,
                    "source": "微信:" + account,
                    "date": date,
                    "category": "other",
                    "department": dept,
                    "region": "全国",
                    "quality": "B",
                    "summary": summary[:240],
                    "tags": [q],
                    "content": summary,
                    "content_fetched": False,
                    "weixin_resolved": resolved,
                    "added_at": date or "2026-07-19",
                }
                inbox.append(rec); existing.add(title.strip().lower()); existing.add(dedup_key); added += 1
            time.sleep(1.2)
        print("q=%s done, cumulative added=%d" % (q, added))
    json.dump(inbox, open(INBOX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("crawl_weixin: added=%d, inbox_total=%d" % (added, len(inbox)))

if __name__ == "__main__":
    main()
