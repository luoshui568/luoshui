# -*- coding: utf-8 -*-
"""交付前数据核查：数据库里的研报是否与 build/seed/report_*.json 逐字一致。

为什么要单独核对：
  * push_report.py 是「upsert + return=minimal」，成功了也不回传内容；
  * E2E 探针会临时改标题/KPI/图表数据再还原，还原是否真的成功必须由第三方核对；
  * jsonb 落库后键序与空白会规范化，只有**读回来做深比较**才能确认没丢东西。

用法：python build/verify_report_db.py [seed文件名 ...]
     不带参数 → 自动核查 build/seed/report_*.json 全部研报
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


def verify(name):
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
            # ⚠️ 库里 no 是 text（返回 "7"），seed 里可能是 int（7）→ 统一成字符串比
            a, b = m.get(k), s.get(k)
            if k in ("seq", "no"):
                a, b = (str(a) if a is not None else None), (str(b) if b is not None else None)
            eq("mod %s.%s" % (m["no"], k), a, b)
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
    seed_txt = json.dumps([c["opt"] for c in seed["charts"]], ensure_ascii=False)
    n_mark = opt_txt.count("{{fn:")
    import re
    n_well = len(re.findall(r"\{\{fn:[^{}]+\}\}", opt_txt))
    n_extra = len(re.findall(r"\{\{fn:[^{}]+\}\}\}", opt_txt))
    # 期望值从 seed 自身推导（各研报图表数不同，不能写死）
    eq("库里的 {{fn:}} 标记数与 seed 一致", n_mark, seed_txt.count("{{fn:"))
    eq("标记形态全部规范", n_mark - n_well, 0)
    eq("标记后无多余花括号", n_extra, 0)
    print("具名标记  %d 处（规范 %d · 多花括号 %d）" % (n_mark, n_well, n_extra))

    # ---------- 5. 模块 HTML 里绝不能出现标记或占位残留 ----------
    mod_bad = []
    for m in seed["mods"]:
        h = str(m.get("html") or "")
        if not h.strip():
            mod_bad.append(m["no"])
        if "{{fn:" in h or "{{" in h:
            mod_bad.append("%s(标记)" % m["no"])
    eq("模块 HTML 无空模块 / 无标记残留", mod_bad, [])
    # 模块里引用的图位必须都在 seed 图表里
    # ⚠️ 必须扫**原始 html 字段**：对 json.dumps 的结果做正则会因 " → \" 而全部漏匹配
    used = set()
    for m in seed["mods"]:
        used |= set(re.findall(r'data-chart="([^"]+)"', str(m.get("html") or "")))
    have = set(c["id"] for c in seed["charts"])
    eq("模块引用的图位 ⊆ 已有图表", sorted(used - have), [])
    print("图位引用  %d 处 · 库内图表 %d 张 · 孤儿图 %s" % (len(used), len(have), sorted(have - used)))

    print("\n" + "=" * 62)
    if bad:
        print("❌ %s 发现 %d 处不一致（通过 %d 项）：" % (name, len(bad), cnt[0]))
        for lab, a, b in bad[:12]:
            print("  · %s" % lab)
            print("      库 : %s" % json.dumps(a, ensure_ascii=False)[:200])
            print("      seed: %s" % json.dumps(b, ensure_ascii=False)[:200])
        print("=" * 62)
        return 2
    print("✅ %s 数据库与 seed 完全一致（通过 %d 项比对）" % (name, cnt[0]))
    print("=" * 62)
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        d = os.path.join(HERE, "seed")
        args = sorted(f for f in os.listdir(d)
                      if f.startswith("report_") and f.endswith(".json"))
        print("自动核查 %d 份研报：%s\n" % (len(args), " ".join(args)))
    rc = 0
    for a in args:
        rc |= verify(a)
        print()
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
