# -*- coding: utf-8 -*-
"""云端端到端测试：通过 PostgREST 对 wb_works 做增删改查（验证 GRANT + RLS + 字段白名单）"""
import io, json, os, urllib.request, urllib.error, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(HERE, "cloud.json"), encoding="utf-8"))
BASE = "https://%s.api.tcloudbasegateway.com/v1/rdb/rest/" % CFG["envId"]
HEAD = {"Authorization": "Bearer " + CFG["key"], "Content-Type": "application/json"}


def call(table, method="GET", q="", body=None, extra=None):
    h = dict(HEAD)
    if extra:
        h.update(extra)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + table + q, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            t = r.read().decode("utf-8")
            return r.status, (json.loads(t) if t else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")[:300]
    except Exception as e:
        return -1, str(e)


rid = "wk_e2e_" + uuid.uuid4().hex[:8]
print("=== 1. INSERT ===")
row = {"id": rid, "horizon": "五年计划", "title": "E2E 测试：五年内控股 1 座铜矿", "detail": "端到端验证",
       "category": "战略", "priority": "P0", "status": "doing", "progress": 10, "owner": "测试",
       "start_date": "2026-09-01", "due_date": "2031-09-01", "kpi": "IRR>15%", "metric": "年产铜(万吨)",
       "baseline": "0", "target": "5", "key_actions": "1.找标的 2.尽调", "resources": "资金+人脉",
       "risk": "铜价下行", "parent_id": "", "milestone": "M12 交割", "review_date": "2027-03-01",
       "note": "备注", "tags": "铜/核心", "sort": 1, "t": 1789000000000, "up": 1789000000000}
st, res = call("wb_works", "POST", "", [row], {"Prefer": "return=representation"})
print("status", st, "->", json.dumps(res, ensure_ascii=False)[:260] if not isinstance(res, str) else res)

print("\n=== 2. SELECT (按 sort 排序) ===")
st, res = call("wb_works", "GET", "?order=sort.asc&limit=5")
print("status", st, "rows", len(res) if isinstance(res, list) else res)
if isinstance(res, list) and res:
    r0 = res[0]
    checks = ["horizon", "title", "key_actions", "metric", "baseline", "target", "kpi",
              "resources", "risk", "parent_id", "milestone", "review_date", "progress", "sort"]
    print("字段回读:", {k: r0.get(k) for k in checks})
    missing = [k for k in checks if r0.get(k) in (None, "")]
    print("空值字段:", missing if missing else "无（全部落库成功）")

print("\n=== 3. UPDATE ===")
st, res = call("wb_works", "PATCH", "?id=eq." + rid, {"status": "done", "progress": 100, "up": 1789000099999},
               {"Prefer": "return=representation"})
print("status", st, "->", json.dumps(res, ensure_ascii=False)[:200] if not isinstance(res, str) else res)

print("\n=== 4. 复查 UPDATE 结果 ===")
st, res = call("wb_works", "GET", "?id=eq." + rid)
if isinstance(res, list) and res:
    print("status=%s progress=%s" % (res[0].get("status"), res[0].get("progress")))
else:
    print("status", st, res)

print("\n=== 5. DELETE ===")
st, res = call("wb_works", "DELETE", "?id=eq." + rid)
print("status", st)

print("\n=== 6. 清理校验（应剩 0 行） ===")
st, res = call("wb_works", "GET", "?limit=200")
print("status", st, "剩余行数", len(res) if isinstance(res, list) else res)
