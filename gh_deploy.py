# -*- coding: utf-8 -*-
"""通过 GitHub Contents API（api.github.com，沙箱可达）同步变更文件到仓库。
用于沙箱 git push 被网络拦截时的兜底部署。
【安全】Token 绝不写在本文件。从环境变量 GH_TOKEN 或本地未跟踪文件 .deploy_token 读取。
用法：python gh_deploy.py
"""
import os, json, base64, time, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = "Tiger-HZ/DualCarbon"
BRANCH = "main"

# Token：优先环境变量，其次本地未跟踪文件（已被 .gitignore 忽略，不会进仓库）
TOKEN = os.environ.get("GH_TOKEN", "")
if not TOKEN:
    tokfile = os.path.join(BASE, ".deploy_token")
    if os.path.exists(tokfile):
        TOKEN = open(tokfile, encoding="utf-8").read().strip()
if not TOKEN:
    raise SystemExit("未找到 GitHub Token：请设置环境变量 GH_TOKEN 或在 .deploy_token 中写入。")

FILES = [
    "kb/kb.json",
    "rag.html", "rag.py", "rag_cli.py", "fetch_fulltext.py", "README_RAG.md",
    ".gitignore", "update.py", "render.py", "config.json", "gh_deploy.py",
    "index.html", "archive.html", "2026-07-17.html",
]
for f in sorted(os.listdir(BASE)):
    if f.startswith("push-") and f.endswith(".html"):
        FILES.append(f)

API = "https://api.github.com/repos/%s/contents/%%s" % REPO


def req(method, url, data=None):
    r = urllib.request.Request(url, headers={
        "Authorization": "Bearer %s" % TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "dual-carbon-deploy",
        "Content-Type": "application/json",
    })
    r.get_method = lambda: method
    if data is not None:
        r.data = data.encode("utf-8")
    return urllib.request.urlopen(r, timeout=30)


def get_remote(path):
    try:
        with req("GET", API % path) as r:
            d = json.load(r)
            return d.get("sha"), base64.b64decode(d.get("content", "")).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise


def upload(path):
    local = os.path.join(BASE, path)
    with open(local, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    sha, remote_text = get_remote(path)
    if sha and remote_text == text:
        print("SKIP (unchanged) " + path)
        return True
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    body = {"message": "deploy: %s" % path, "content": b64, "branch": BRANCH}
    if sha:
        body["sha"] = sha
    for attempt in range(3):
        try:
            with req("PUT", API % path, json.dumps(body)) as r:
                print(("OK %d " % r.status) + path)
                return True
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "ignore")
            print("HTTP %d %s  %s" % (e.code, path, msg[:120]))
            time.sleep(2)
        except Exception as e:
            print("ERR %s %s" % (path, e))
            time.sleep(2)
    return False


if __name__ == "__main__":
    ok = 0
    for p in FILES:
        lp = os.path.join(BASE, p)
        if os.path.exists(lp):
            if upload(p):
                ok += 1
            time.sleep(0.4)
        else:
            print("MISSING", p)
    print("\n=== deployed %d / %d files via api.github.com ===" % (ok, len(FILES)))
