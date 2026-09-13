# -*- coding: utf-8 -*-
"""把本地种子数据批量推到 CloudBase PG REST（幂等 upsert）"""
import io, json, os, urllib.request, urllib.error, time

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(HERE, "cloud.json"), encoding="utf-8"))
BASE = "https://%s.api.tcloudbasegateway.com/v1/rdb/rest/" % CFG["envId"]
SEED = os.path.join(HERE, "seed")

JOBS = [("wb_tasks", "tasks.json"), ("wb_permits", "permits.json"),
        ("wb_milestones", "milestones.json"), ("wb_watchlist", "watchlist.json"),
        ("wb_contacts", "contacts.json")]

ALLOWED = None

def post(table, rows):
    body = json.dumps(rows, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + table, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + CFG["key"])
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "resolution=merge-duplicates,return=minimal")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return "%s %s" % (e.code, e.read().decode("utf-8", "ignore")[:300])

total = 0
for table, fn in JOBS:
    rows = json.load(io.open(os.path.join(SEED, fn), encoding="utf-8"))
    ok = 0
    for i in range(0, len(rows), 60):
        chunk = rows[i:i + 60]
        st = post(table, chunk)
        if st in (200, 201, 204):
            ok += len(chunk)
        else:
            print("  !! %s 第 %d 批失败: %s" % (table, i // 60 + 1, st))
            break
        time.sleep(0.25)
    print("%-16s %3d / %3d 已入库" % (table, ok, len(rows)))
    total += ok
print("合计推送 %d 条" % total)

# 校验
chk = urllib.request.Request(BASE + "wb_tasks?select=id&limit=1")
chk.add_header("Authorization", "Bearer " + CFG["key"])
req2 = urllib.request.Request(BASE + "wb_tasks?limit=1&order=seq.asc", method="GET")
req2.add_header("Authorization", "Bearer " + CFG["key"])
with urllib.request.urlopen(req2, timeout=30) as r:
    print("回读 wb_tasks 首行:", r.read().decode("utf-8")[:160])
