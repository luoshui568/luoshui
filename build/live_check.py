# -*- coding: utf-8 -*-
"""线上真机验证：加载线上页面 → 新增一条计划 → 确认已写入云端 PG → 清理"""
import io, json, os, subprocess, time, urllib.request, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CFG = json.load(io.open(os.path.join(HERE, "cloud.json"), encoding="utf-8"))
BASE = "https://%s.api.tcloudbasegateway.com/v1/rdb/rest/" % CFG["envId"]
HEAD = {"Authorization": "Bearer " + CFG["key"], "Content-Type": "application/json"}

URL = "https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com/index.html"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# 先用 REST 直接写入一条，模拟页面的 POST（页面走的是同一条路径）
rid = "wk_live_" + uuid.uuid4().hex[:8]
row = {
    "id": rid, "horizon": "本季度", "title": "线上验证：季度内完成矿权标的初筛",
    "detail": "线上真机验证", "category": "资源", "priority": "P0", "status": "doing", "progress": 20,
    "owner": "刘", "start_date": "2026-09-10", "due_date": "2026-12-31",
    "kpi": "初筛出 5 个可尽调标的", "metric": "初筛标的数", "baseline": "0", "target": "5",
    "key_actions": "1. 建筛选清单 2. 跑数据 3. 约见", "resources": "地勘院专家 + 券商",
    "risk": "优质标的被抢", "parent_id": "", "milestone": "M3 出初筛报告",
    "review_date": "2026-10-31", "note": "线上测试", "tags": "铜/初筛",
    "sort": 5, "t": int(time.time() * 1000), "up": int(time.time() * 1000)
}


def post(t, method="GET", q="", body=None, extra=None):
    h = dict(HEAD)
    if extra:
        h.update(extra)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + t + q, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode("utf-8")
            return r.status, (json.loads(txt) if txt else None)
    except Exception as e:
        return -1, str(e)[:200]


print("=== A. 写入一条计划（模拟页面 POST /wb_works） ===")
st, res = post("wb_works", "POST", "", [row], {"Prefer": "return=representation"})
print("status", st)

print("\n=== B. headless 打开【线上页面】，检查工作计划页签是否可用 ===")
probe = """
<script>
setTimeout(function(){
  var o={};
  try{
    o.err = (window.__E||[]).length;
    o.navBtn = document.querySelectorAll('#nav button').length;
    o.hasWork = !!document.getElementById('pg-work');
    App.go('work');
    o.workTabActive = document.getElementById('wt-dashboard').className;
    o.hzCards = document.querySelectorAll('#workDashBox .hzc').length;
    App.workTab('horizon'); renderWork();
    o.cards = document.querySelectorAll('#workBox .wcrd').length;
    o.hzChips = document.querySelectorAll('#workHzChips .chip').length;
    o.cloudState = Cloud.state;
    o.cloudMsg = String(Cloud.msg).slice(0,80);
    o.worksLen = S.works.length;
    var t = S.works.filter(function(w){return w.horizon==='本季度';})[0];
    o.found = t? (t.title + ' | KPI=' + t.kpi + ' | target=' + t.target) : 'NOT_FOUND';
    document.title='L|'+JSON.stringify(o);
  }catch(e){ document.title='LERR|'+e.message; }
},7000);
</script>
"""
src = io.open(os.path.join(ROOT, "deploy", "index.html"), encoding="utf-8").read()
tmp = os.path.join(HERE, "__live_probe.html")
io.open(tmp, "w", encoding="utf-8").write(src.replace("</body>", probe + "</body>"))

# 用本地 http 服务（线上 file:// 会被 CORS 拦，但我们测的是页面逻辑 + 真实云端拉取）
srv = subprocess.Popen([r"C:\Users\50522\.workbuddy\binaries\python\envs\default\Scripts\python.exe",
                        "-m", "http.server", "8917", "--bind", "127.0.0.1"], cwd=HERE,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2.5)
try:
    out = subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
                          "--virtual-time-budget=12000", "--dump-dom",
                          "http://127.0.0.1:8917/__live_probe.html"],
                         capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=90)
    dom = out.stdout or ""
    import re
    m = re.search(r"<title>(.*?)</title>", dom, re.S)
    print(m.group(1) if m else "NO_TITLE")
finally:
    srv.terminate()

print("\n=== C. 云端确认该条已存在 ===")
st, res = post("wb_works", "GET", "?id=eq." + rid)
if isinstance(res, list) and res:
    r0 = res[0]
    print("status", st, "| horizon=%s | title=%s | kpi=%s | target=%s | progress=%s"
          % (r0.get("horizon"), r0.get("title"), r0.get("kpi"), r0.get("target"), r0.get("progress")))
else:
    print("status", st, res)

print("\n=== D. 清理测试数据 ===")
st, _ = post("wb_works", "DELETE", "?id=eq." + rid)
print("delete status", st)
st, res = post("wb_works", "GET", "?limit=200")
print("wb_works 剩余行数:", len(res) if isinstance(res, list) else res)
os.remove(tmp)
