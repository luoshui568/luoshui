# -*- coding: utf-8 -*-
"""交付前数据核查：数据库里的研报是否与 build/seed/report_*.json 逐字一致。

为什么要单独核对：
  * push_report.py 是「upsert + return=minimal」，成功了也不回传内容；
  * E2E 探针会临时改标题/KPI/图表数据再还原，还原是否真的成功必须由第三方核对；
  * jsonb 落库后键序与空白会规范化，只有**读回来做深比较**才能确认没丢东西。

用法：python build/verify_report_db.py [seed文件名]
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(HERE, "cloud.json"), encoding="utf-8"))
REST = "https://%s.api.tcloudbasegateway.com/v1/rdb/rest/" % CFG["envId"]
HDR = {"Authorization": "Bearer " + CFG["key"], "Content-Type": "application/json"}

import urllib.request
import urllib.error


def get(path):
    r = urllib.request.Request(REST + path, headers=HDR)
    with urllib.request.urlopen(r, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "report_600456.json"
    seed = json.load(io.open(os.path.join(HERE, "seed", name), encoding="utf-8"))
    rep = seed["report"]
    rid = rep["code"]

    bad = []
    cnt = [0]

    def eq(label, a, b):
        if a == b:
            cnt[0] += 1
        else:
            bad.append((label, a, b))

    # ---------- 1. 研报头 ----------
    rows = get("wb_reports?id=eq.%s" % rid)
    if not rows:
        print("❌ 数据库里没有研报 %s" % rid)
        return 1
    r0 = rows[0]
    for k in ["code", "name", "kicker", "title", "subtitle", "badges", "verdict_title",
              "verdict_html", "kpis", "kpi_note", "toc", "essence_html", "footer_html", "theme"]:
        eq("report.%s" % k, r0.get(k), rep.get(k))
    print("研报头    %s %s · 标题 %r" % (r0.get("code"), r0.get("name"), r0.get("title")))
    print("          KPI %d 项 · 徽标 %d 个 · 目录 %d 条 · 结论 %d 字 · 页脚 %d 字"
          % (len(r0.get("kpis") or []), len(r0.get("badges") or []), len(r0.get("toc") or []),
             len(r0.get("verdict_html") or ""), len(r0.get("footer_html") or "")))
    for k in ["title", "verdict_html", "footer_html", "essence_html", "subtitle"]:
        s = str(r0.get(k) or "")
        if "探针" in s or "PROBE" in s.upper():
            bad.append(("report.%s 残留探针字样" % k, s[:60], ""))

    # ---------- 2. 模块 ----------
    mods = get("wb_report_mods?report_id=eq.%s&order=seq.asc" % rid)
    eq("mods 条数", len(mods), len(seed["mods"]))
    sm = dict(("%s_m%s" % (rid, m["no"]), m) for m in seed["mods"])
    for m in mods:
        s = sm.get(m["id"])
        if not s:
            bad.append(("多余模块", m["id"], ""))
            continue
        for k in ["seq", "no", "title", "html"]:
            eq("mod %s.%s" % (m["no"], k), m.get(k), s.get(k))
    print("模块      %d 条（seed %d 条）· 编号 %s"
          % (len(mods), len(seed["mods"]), " ".join(m["no"] for m in mods)))

    # ---------- 3. 图表 ----------
    charts = get("wb_report_charts?report_id=eq.%s&order=seq.asc" % rid)
    eq("charts 张数", len(charts), len(seed["charts"]))
    sc = dict(("%s_%s" % (rid, c["id"]), c) for c in seed["charts"])
    for c in charts:
        s = sc.get(c["id"])
        if not s:
            bad.append(("多余图表", c["id"], ""))
            continue
        eq("chart %s.name" % c["id"], c.get("name"), s.get("name"))
        eq("chart %s.seq" % c["id"], c.get("seq"), s.get("seq"))
        eq("chart %s.opt" % c["id"], c.get("opt"), s.get("opt"))
    print("图表      %d 张（seed %d 张）" % (len(charts), len(seed["charts"])))

    # ---------- 4. 标记形态 ----------
    opt_txt = json.dumps([c["opt"] for c in charts], ensure_ascii=False)
    n_mark = opt_txt.count("{{fn:")
    n_well = opt_txt.count("{{fn:")          # 规范标记数（下面用正则复核）
    import re
    n_well = len(re.findall(r"\{\{fn:[^{}]+\}\}", opt_txt))
    n_extra = len(re.findall(r"\{\{fn:[^{}]+\}\}\}", opt_txt))
    eq("库里的 {{fn:}} 标记数", n_mark, 15)
    eq("标记形态全部规范", n_mark - n_well, 0)
    eq("标记后无多余花括号", n_extra, 0)
    print("具名标记  %d 处（规范 %d · 多花括号 %d）" % (n_mark, n_well, n_extra))

    print("\n" + "=" * 62)
    if bad:
        print("❌ 发现 %d 处不一致（通过 %d 项）：" % (len(bad), cnt[0]))
        for lab, a, b in bad[:12]:
            print("  · %s" % lab)
            print("      库 : %s" % json.dumps(a, ensure_ascii=False)[:200])
            print("      seed: %s" % json.dumps(b, ensure_ascii=False)[:200])
        print("=" * 62)
        return 2
    print("✅ 数据库与 seed 完全一致（通过 %d 项比对）" % cnt[0])
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
