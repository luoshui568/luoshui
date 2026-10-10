# -*- coding: utf-8 -*-
"""修 chartTiWorldMap 的 opt（旧版满涂色块 → 新版 geo + 浅红打底 + 气泡标签），
并重排 wb_report_charts 的 seq（插中国地图后出现 seq=25 撞号、尾部错位）。

★ 为什么单独做：上一轮 add_ti_mod_600456.py 的「改版」模式只 PATCH 了 m25 正文
  与插入 chartTiCNMap 行，**没动 chartTiWorldMap 的 opt** —— 那是首插时写进去的旧配置。
  实测线上该图仍为「12 国满涂四种红 + roam:false + 无 geo」，用户要的
  「好看 + 可自由缩放」对它完全没生效（中国地图因为是新插的，反而正常）。
★ seq 撞号：chartTiShare 与 chartTiCNMap 都是 25。渲染按 id 不按 seq，不影响出图，
  但 seq 是编辑列表的显示序 ⇒ 一并重排为连续 1..28。
★ 幂等：opt 与 seq 都写成「目标值」，重跑无副作用。
"""
import io, json, os, sys, time, urllib.request, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import add_ti_mod_600456 as M   # 复用 opt_worldmap()

CFG = json.load(io.open(os.path.join(HERE, "cloud.json"), encoding="utf-8"))
BASE = "https://%s.api.tcloudbasegateway.com/v1/rdb/rest/" % CFG["envId"]
KEY = CFG["key"]
HDR = {"apikey": KEY, "Authorization": "Bearer " + KEY,
       "Content-Type": "application/json", "Accept": "application/json"}

CODE = "600456"
TARGET_SEQ = {
    "chartTiWorldMap": 24,
    "chartTiCNMap": 25,
    "chartTiShare": 26,
    "chartTiCNProv": 27,
    "chartTiPrice": 28,
}


def req(path, method="GET", body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers=HDR, method=method)
    raw = urllib.request.urlopen(r, timeout=90).read().decode("utf-8")
    return json.loads(raw) if raw.strip() else None


def main(go=False):
    # 两张地图的 opt 都从 build/add_ti_mod_600456.py 现场推导（单一数据源），
    # 保证「库里的 opt」与「改版脚本里的定义」永远一致。
    OPTS = {
        "chartTiWorldMap": M.opt_worldmap(),
        "chartTiCNMap": M.opt_cnmap(),
    }
    for key, o in OPTS.items():
        txt = json.dumps(o, ensure_ascii=False, separators=(",", ":"))
        print("=== %s ：%d 字符 ===" % (key, len(txt)))
        print("  顶层键 =", sorted(o.keys()))
        print("  series  =", [s.get("type") for s in o["series"]])
        g = o.get("geo", {})
        print("  geo.map=%s roam=%s scaleLimit=%s layoutSize=%s" %
              (g.get("map"), g.get("roam"), g.get("scaleLimit"), g.get("layoutSize")))
        for s in o["series"]:
            print("   - %-8s roam=%-5s scaleLimit=%-22s items=%s" %
                  (s.get("type"), s.get("roam"), s.get("scaleLimit"),
                   len(s.get("data") or [])))
        # 抽一个 data 项看颜色分档有没有落上
        for s in o["series"]:
            if s.get("type") == "scatter" and s.get("data"):
                d = s["data"][0]
                print("   首个气泡: %s color=%s symbolSize=%.1f" %
                      (d.get("name"), (d.get("itemStyle") or {}).get("color"),
                       d.get("symbolSize") or 0))
            if s.get("type") == "map" and s.get("data"):
                for d in s["data"][:3]:
                    print("   底纹: %-12s areaColor=%s" %
                          (d.get("name"), (d.get("itemStyle") or {}).get("areaColor")))
        print()

    print("seq 目标：")
    for k, v in TARGET_SEQ.items():
        print("  %-18s -> %d" % (k, v))

    if not go:
        print("\n（干跑结束，加 --go 写库）")
        return

    now = int(time.time() * 1000)

    # ① PATCH 两张地图的 opt
    for key, o in OPTS.items():
        req("wb_report_charts?id=eq.%s_%s" % (CODE, key), "PATCH", {"opt": o, "up": now})
        print("\n[1] PATCH %-18s opt  ok" % key)

    # ② PATCH seq
    for k, v in TARGET_SEQ.items():
        req("wb_report_charts?id=eq.%s_%s" % (CODE, k), "PATCH", {"seq": v, "up": now})
        print("[2] PATCH %-18s seq=%d  ok" % (k, v))

    # ③ 回读复核（逐张地图比**解析后的 dict**，不比 md5 —— PG 的 jsonb 往返会重排键序）
    rows = req("wb_report_charts?report_id=eq.%s&select=seq,id,name,opt&order=seq.asc" % CODE)
    print("\n=== 回读 %d 行 ===" % len(rows))
    ok_opt = ok_seq = False
    for r in rows:
        short = r["id"].split("_", 1)[1] if r["id"].startswith(CODE + "_") else r["id"]
        if short in OPTS:
            o = r["opt"]
            if isinstance(o, str):
                o = json.loads(o)
            same = (o == OPTS[short])
            ok_opt = same
            g = o.get("geo", {})
            print("  %-18s 与本地定义一致=%s  geo.map=%s roam=%s series=%s" %
                  (short, "✅" if same else "❌", g.get("map"), g.get("roam"),
                   [s.get("type") for s in o.get("series", [])]))
            if not same:
                for kk in sorted(set(list(o.keys()) + list(OPTS[short].keys()))):
                    if o.get(kk) != OPTS[short].get(kk):
                        print("     ✗ 差异字段 .%s" % kk)
        if short in TARGET_SEQ:
            print("  %-18s seq=%s %s" % (short, r["seq"],
                                         "✅" if r["seq"] == TARGET_SEQ[short] else "❌"))
    seqs = sorted(x["seq"] for x in rows)
    ok_seq = seqs == list(range(1, len(rows) + 1))
    print("\n两张地图 opt 与本地定义一致 %s" % ("✅" if ok_opt else "❌"))
    print("seq 1..%d 连续 %s" % (len(rows), "✅" if ok_seq else "❌ " + str(seqs)))


if __name__ == "__main__":
    main("--go" in sys.argv)
