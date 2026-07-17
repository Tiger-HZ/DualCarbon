# -*- coding: utf-8 -*-
"""全文抓取模块：从政策/文献原文 URL 下载 HTML 并抽取正文。
纯标准库实现（urllib + re），不依赖第三方包，供每日自动化增量补全文库使用。
用法：
  python fetch_fulltext.py            # 对 kb.json 中尚未抓取且 URL 可抓取者批量补全文
  python fetch_fulltext.py --only "标题关键词"   # 仅抓取标题命中的若干条
  python fetch_fulltext.py --test URL  # 测试单条 URL 抽取效果
"""
import json, os, re, sys, time, html, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(BASE, "kb", "kb.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# 内容容器候选（按优先级匹配 class/id 关键字）
CONTENT_KEYS = ["TRS_Editor", "article", "article-con", "art_content", "artContent",
                "content", "detail", "newscon", "newsCon", "news_text", "newsText",
                "main", "body", "pages_content", "pagesContent", "zoom", "view",
                "fontbox", "TRS_UEDITOR", "u-editor", "edit", "cont"]

BOILER = re.compile(r"(版权所有|ICP备|网站标识|京公网安|首页|登录|注册|无障碍|繁體|English|"
                    r"纠错|责任编辑|来源：|发布时间|点击：|打印|关闭|分享到|扫一扫|关注我们|"
                    r"上一篇|下一篇|相关阅读|推荐阅读|主办单位|技术支持|政府网站)")


def download(url, timeout=25, retries=2):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                        "Accept": "text/html,application/xhtml+xml"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            enc = "utf-8"
            m = re.search(r"charset=([\w-]+)", r.headers.get("Content-Type", ""), re.I)
            if m:
                enc = m.group(1).lower()
            try:
                return data.decode(enc, "ignore")
            except LookupError:
                return data.decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(1.5)
    return None


def _clean(txt):
    txt = html.unescape(txt)
    txt = re.sub(r"&emsp;|&ensp;|&thinsp;|&nbsp;", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def extract_main_text(html):
    """从 HTML 抽取正文纯文本（尽力而为）。"""
    if not html:
        return ""
    # 去 head/script/style/comment
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<head[\s\S]*?</head>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<noscript[\s\S]*?</noscript>", " ", html, flags=re.I | re.S)

    # 1) 尝试定位内容容器
    best = ""
    for key in CONTENT_KEYS:
        # class*=key 或 id*=key
        for pat in (r"class=[\"'][^\"']*%s[^\"']*[\"']" % re.escape(key),
                    r"id=[\"']%s[\"']" % re.escape(key)):
            m = re.search(pat, html, re.I)
            if m:
                # 找该标签闭合块
                start = m.start()
                # 回溯到标签起点
                ot = html.rfind("<", 0, start)
                eb = html.find(">", ot) + 1
                block = _grab_block(html, ot)
                if block:
                    text = _block_text(block)
                    if len(text) > len(best):
                        best = text
    if len(best) > 300:
        return best

    # 2) 退而求其次：取 body 内最长连续有效文本段
    body = re.sub(r"<body[\s\S]*?</body>", lambda m: m.group(0), html, flags=re.I | re.S)
    if not body or "body" not in body.lower():
        body = html
    # 取所有标签外文本片段
    texts = re.findall(r">([^<>]+)<", body)
    texts = [_clean(t) for t in texts if _clean(t)]
    # 过滤样板行，拼接最长连续有效段
    kept = [t for t in texts if not BOILER.search(t) and len(t) >= 4]
    # 用空行/短分隔合并：直接拼成一大段也可，这里返回过滤后的非空行
    longs = [t for t in kept if len(t) >= 15]
    if longs:
        return "\n".join(longs)
    return "\n".join(kept)


def _grab_block(html, open_idx):
    """从 open_idx（'<') 开始，匹配到对应闭合标签，返回内部 HTML。"""
    m = re.match(r"<\s*([a-zA-Z0-9]+)", html[open_idx:])
    if not m:
        return None
    tag = m.group(1).lower()
    i = open_idx
    depth = 0
    n = len(html)
    while i < n:
        lt = html.find("<", i)
        if lt < 0:
            break
        if html[lt + 1:lt + 2] == "/":
            # 闭合
            et = html.find(">", lt)
            ctag = re.match(r"</\s*([a-zA-Z0-9]+)", html[lt:et + 1])
            if ctag and ctag.group(1).lower() == tag:
                depth -= 1
                if depth == 0:
                    return html[open_idx:et + 1]
            i = et + 1
        else:
            # 开放
            et = html.find(">", lt)
            otag = re.match(r"<\s*([a-zA-Z0-9]+)", html[lt:et + 1])
            if otag and otag.group(1).lower() == tag:
                depth += 1
            i = et + 1
    return html[open_idx:]


def _block_text(block):
    # 去所有标签，保留换行
    text = re.sub(r"<br\s*/?>", "\n", block, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [_clean(t) for t in text.split("\n")]
    lines = [t for t in lines if t and not BOILER.search(t) and len(t) >= 4]
    return "\n".join(lines)


def fetch_one(url):
    html = download(url)
    if not html:
        return None
    text = extract_main_text(html)
    # 去除与正文无关的超短噪声
    text = "\n".join(l for l in text.split("\n") if len(l) >= 4)
    return text if len(text) >= 120 else None


def run_batch(only=None):
    kb = json.load(open(KB, encoding="utf-8"))
    todo = [r for r in kb if not r.get("content_fetched")]
    if only:
        rx = re.compile(only)
        todo = [r for r in todo if rx.search(r.get("title", ""))]
    done = 0
    fail = 0
    for r in todo:
        url = r.get("url", "")
        if not url or url.startswith("http") is False:
            continue
        if any(b in url for b in ("people.com.cn", "163.com", "qq.com", "nfnews.com",
                                  ".pdf", "wulanchabu")):
            # 这些镜像/聚合/PDF 站点正文抽取不稳定，跳过（留待人工或后续补）
            continue
        try:
            txt = fetch_one(url)
        except Exception:
            txt = None
        if txt:
            r["content"] = txt
            r["content_fetched"] = True
            done += 1
            print("OK  [%d字] %s" % (len(txt), r.get("title", "")[:40]))
        else:
            fail += 1
            print("SKIP %s" % r.get("title", "")[:40])
        time.sleep(0.4)
    json.dump(kb, open(KB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("----\nbatch done: fetched=%d skipped=%d total=%d" % (done, fail, len(kb)))
    return done


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        u = sys.argv[2]
        t = fetch_one(u)
        print("LEN", len(t) if t else 0)
        print(t[:1500] if t else "(none)")
    elif len(sys.argv) > 1 and sys.argv[1] == "--only":
        run_batch(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        run_batch()
