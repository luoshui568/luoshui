#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一条复盘日志写进「矿产战略执行工作台 → 复盘日志」页（表 public.wb_logs）。

用途：每日自动化（22:30）把当天干的活归纳成一条简明日志写库。
页面：https://liuchaowang.cn/app.html → 侧栏「📝 复盘日志」

字段（见 cloudbase/migrations/20260910070221_create_strategy_workbench.sql）：
  id        text  PK     形如 l_xxxxxxxxx（与前端 uid('l') 同款）
  log_date  text         YYYY-MM-DD
  kind      text         前端下拉：日复盘/周复盘/月度复盘/季度复盘/年度复盘/决策记录/情绪日志
  title     text         h5 标题
  body      text         正文（\n 换行，页面用 esc() 直出，故纯文本即可）
  tags      text         右侧蓝色胶囊标签
  t / up    bigint       毫秒时间戳

★ 幂等：同一 (log_date, tags) 已存在 ⇒ PATCH 覆盖，不产生重复条目。
★ anon key 有 SELECT/INSERT/UPDATE，DELETE 已被数据库端收回（只能走 wb_admin_delete_row RPC）。
   所以本脚本**只写不删**；要删请去页面上点「🗑 删除」（需管理员密码）。

用法：
  python3 build/log_daily.py --date 2026-10-14 --title '研报体系迭代' \\
      --tags 'AI 工作日志' --body-file /tmp/daily_log_body_2026-10-14.txt
  python3 build/log_daily.py --date 2026-10-14 --title '...' --body '第一行\\n第二行'
  python3 build/log_daily.py --show --date 2026-10-14 --tags 'AI 工作日志'   # 只看
  python3 build/log_daily.py --dry  --date ... --title ...                  # 只印不发请求

★ 幂等键 = (log_date, tags)。每日自动化**固定用 tags='AI 工作日志'**，这样同一天重复运行只会覆盖、
  不会写重；用户手动写的那几条 tags 是别的词，不会被碰。
⚠️ body 中转文件**别用固定路径**（本仓库同时会有并发会话，`/tmp/daily_log_body.txt` 会被互相覆写）
  ⇒ 一律带日期：`/tmp/daily_log_body_<YYYY-MM-DD>.txt`。
"""
import argparse
import json
import os
import random
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "cloud.json")


def load_cfg():
    with open(CFG, "r", encoding="utf-8") as f:
        c = json.load(f)
    env = c["envId"]
    base = "https://%s.api.tcloudbasegateway.com/v1/rdb/rest/" % env
    return base, c["key"]


def req(method, url, key, body=None):
    data = None
    headers = {"Authorization": "Bearer " + key}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Prefer"] = "return=representation"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400]


def new_id():
    rnd = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(5))
    ts = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(7))
    return "l_%s%s" % (ts, rnd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="日志日期 YYYY-MM-DD")
    ap.add_argument("--title", default="")
    ap.add_argument("--kind", default="日复盘")
    ap.add_argument("--tags", default="AI 工作日志")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--body", default=None)
    g.add_argument("--body-file", default=None)
    ap.add_argument("--show", action="store_true", help="只查看当天该 tags 是否已写入")
    ap.add_argument("--dry", action="store_true", help="只打印，不写库")
    a = ap.parse_args()

    base, key = load_cfg()
    tbl = base + "wb_logs"

    q = "%s?select=*&log_date=eq.%s&tags=eq.%s" % (tbl, a.date, urllib.parse.quote(a.tags))
    st, cur = req("GET", q, key)
    if st != 200:
        print("READ FAIL", st, cur)
        return 2
    old = cur[0] if cur else None

    if a.show:
        print(json.dumps(cur, ensure_ascii=False, indent=2))
        return 0

    if a.body_file:
        with open(a.body_file, "r", encoding="utf-8") as f:
            body = f.read().strip()
    else:
        body = (a.body or "").strip()
    title = a.title.strip()

    if not title or not body:
        print("REFUSE: title/body 不能为空（宁可写「今日无产出」也不要空条目）")
        return 3

    row = {
        "log_date": a.date,
        "kind": a.kind,
        "title": title,
        "body": body,
        "tags": a.tags,
        "up": int(time.time() * 1000),
    }
    if old:
        target = "%s?id=eq.%s" % (tbl, old["id"])
        action = "UPDATE"
        row["id"] = old["id"]
        row["t"] = old.get("t") or row["up"]
    else:
        target = tbl
        action = "INSERT"
        row["id"] = new_id()
        row["t"] = row["up"]

    if a.dry:
        print("DRY", action, json.dumps(row, ensure_ascii=False, indent=2))
        return 0

    st, res = req("POST" if not old else "PATCH", target, key, row)
    if st not in (200, 201, 204):
        print("WRITE FAIL", st, res)
        return 4
    print("OK %s %s  %s  [%s] %s" % (action, row["id"], a.date, a.tags, title))
    print("正文 %d 字 / %d 行" % (len(body), body.count("\n") + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
