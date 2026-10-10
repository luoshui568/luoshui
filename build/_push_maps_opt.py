# -*- coding: utf-8 -*-
"""把改版后的两张地图 opt PATCH 进 wb_report_charts（id = 600456_chartTiWorldMap / _chartTiCNMap）。

为什么不走 add_ti_mod_600456.py --go：
  那个脚本的改版分支只 PATCH **模块正文**；图表 opt 的更新在本轮是独立的一件事
  （上一轮建立的 fix_worldmap_opt.py 就是干这个）。本轮把两张图一起推，避免
  「正文是新的、图是旧的」这种半吊子状态。

用法：python build/_push_maps_opt.py            # 干跑
      python build/_push_maps_opt.py --go       # 写库
"""
import hashlib, importlib.util, io, json, os, sys, time, urllib.error, urllib.request

HERE = r"C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build"
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("ati", os.path.join(HERE, "add_ti_mod_600456.py"))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)

GO = "--go" in sys.argv
now = int(time.time() * 1000)
out = []

# 要推的两张图（图表 id 后缀 → 生成函数）
TARGETS = [("chartTiWorldMap", M.opt_worldmap), ("chartTiCNMap", M.opt_cnmap)]

# ---- 拉当前值 ----
cur = {}
for sid, _ in TARGETS:
    r = M.req("wb_report_charts?id=eq.%s_%s&select=id,opt,up" % (M.CODE, sid))
    cur[sid] = r[0] if r else None
    out.append("当前 %-18s %s" % (sid, "存在 (up=%s)" % r[0]["up"] if r else "★ 不存在"))
out.append("")

if not GO:
    for sid, fn in TARGETS:
        new = fn()
        old = cur[sid]["opt"] if cur[sid] else None
        js_new = json.dumps(new, ensure_ascii=False, sort_keys=True)
        out.append("[干跑] %-18s 新 opt %d B / 旧 %s B  %s"
                   % (sid, len(js_new.encode("utf-8")),
                      len(json.dumps(old, ensure_ascii=False, sort_keys=True).encode("utf-8")) if old else "-",
                      "内容有变化" if js_new != json.dumps(old, ensure_ascii=False, sort_keys=True) else "内容相同（无需推）"))
        out.append("        tooltip.formatter = %r" % new.get("tooltip", {}).get("formatter"))
    out.append("")
    out.append("（干跑结束。加 --go 写库）")
    io.open(os.path.join(HERE, "_o_push_maps.txt"), "w", encoding="utf-8").write("\n".join(out))
    print("\n".join(out))
    sys.exit(0)

# ---- 备份 ----
bk = os.path.join(HERE, "backup", "600456_maps_opt_pre_%s.json" % time.strftime("%Y%m%d-%H%M%S"))
os.makedirs(os.path.dirname(bk), exist_ok=True)
io.open(bk, "w", encoding="utf-8").write(json.dumps({"at": now, "charts": cur}, ensure_ascii=False))
out.append("快照 → %s（%d B）" % (os.path.basename(bk), os.path.getsize(bk)))
out.append("")

# ---- 写 ----
for sid, fn in TARGETS:
    new = fn()
    try:
        M.req("wb_report_charts?id=eq.%s_%s" % (M.CODE, sid), "PATCH", {"opt": new, "up": now})
        out.append("  ✔ PATCH %-18s" % sid)
    except urllib.error.HTTPError as e:
        out.append("  ✖ PATCH %s 失败：HTTP %s %s" % (sid, e.code, e.read()[:300]))
        io.open(os.path.join(HERE, "_o_push_maps.txt"), "w", encoding="utf-8").write("\n".join(out))
        print("\n".join(out)); sys.exit(1)

# ---- 回读复核（★ 比解析后的 dict，不比 md5 —— jsonb 往返会重排键序，md5 必假红）----
time.sleep(1.2)
out.append("")
out.append("=== 回读复核（比较解析后的 dict，不比 md5）===")
ok_all = True
for sid, fn in TARGETS:
    want = fn()
    got = M.req("wb_report_charts?id=eq.%s_%s&select=opt,up" % (M.CODE, sid))[0]
    g = got["opt"]
    if isinstance(g, str): g = json.loads(g)
    same = json.dumps(want, ensure_ascii=False, sort_keys=True) == json.dumps(g, ensure_ascii=False, sort_keys=True)
    ok_all = ok_all and same
    out.append("  %-18s %s  up=%s" % (sid, "逐字段一致 ✅" if same else "★ 不一致 ❌", got["up"]))
    if not same:
        # 首个差异定位
        a = json.dumps(want, ensure_ascii=False, sort_keys=True)
        b = json.dumps(g, ensure_ascii=False, sort_keys=True)
        for i in range(min(len(a), len(b))):
            if a[i] != b[i]:
                out.append("     首个差异 @%d：期望 …%s… 实际 …%s…" % (i, a[max(0,i-40):i+40], b[max(0,i-40):i+40]))
                break
        else:
            out.append("     长度不同：期望 %d / 实际 %d" % (len(a), len(b)))
out.append("")
out.append("总判定：%s" % ("✅ 两张图 opt 已一致落地" if ok_all else "❌ 有图未落地，见上"))

io.open(os.path.join(HERE, "_o_push_maps.txt"), "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))
