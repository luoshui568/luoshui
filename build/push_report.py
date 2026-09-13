# -*- coding: utf-8 -*-
"""把 build/seed/report_*.json 推进数据库（PostgREST upsert）。

用法： python push_report.py [seed文件名，默认 report_600456.json]
可反复执行（on_conflict=id → merge-duplicates）。
"""
import io, json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(HERE, "cloud.json"), encoding="utf-8"))
REST = "https://%s.api.tcloudbasegateway.com/v1/rdb/rest/" % CFG["envId"]
HDR = {
    "Authorization": "Bearer " + CFG["key"],
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}


def req(path, method="GET", body=None, headers=None, timeout=90):
    h = dict(HDR)
    if headers:
        h.update(headers)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    r = urllib.request.Request(REST + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:900]


def chunk(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "report_600456.json"
    seed = json.load(io.open(os.path.join(HERE, "seed", name), encoding="utf-8"))
    rep = seed["report"]
    rid = rep["code"]
    now = int(time.time() * 1000)

    # ---------- 1. 研报元信息 ----------
    row = {
        "id": rid, "code": rep["code"], "name": rep["name"],
        "kicker": rep["kicker"], "title": rep["title"], "subtitle": rep["subtitle"],
        "badges": rep["badges"], "verdict_title": rep["verdict_title"],
        "verdict_html": rep["verdict_html"], "kpis": rep["kpis"], "kpi_note": rep["kpi_note"],
        "toc": rep["toc"], "essence_html": rep["essence_html"], "footer_html": rep["footer_html"],
        "theme": rep.get("theme", "red"), "sort": 1, "up": now,
    }
    st, r = req("wb_reports?on_conflict=id", "POST", [row])
    print("wb_reports        %s %s" % (st, "" if st < 400 else r))

    # ---------- 2. 模块 ----------
    mods = []
    for m in seed["mods"]:
        mods.append({
            "id": "%s_m%s" % (rid, m["no"]), "report_id": rid, "code": rid,
            "seq": m["seq"], "no": m["no"], "title": m["title"], "html": m["html"], "up": now,
        })
    ok = 0
    for part in chunk(mods, 6):
        st, r = req("wb_report_mods?on_conflict=id", "POST", part)
        if st < 400:
            ok += len(part)
        else:
            print("   !! 模块批次失败 %s %s" % (st, r))
    print("wb_report_mods    %d/%d 条" % (ok, len(mods)))

    # ---------- 3. 图表 ----------
    charts = []
    for c in seed["charts"]:
        charts.append({
            "id": "%s_%s" % (rid, c["id"]), "report_id": rid, "code": rid,
            "seq": c["seq"], "name": c["name"], "opt": c["opt"], "up": now,
        })
    ok = 0
    for part in chunk(charts, 4):
        st, r = req("wb_report_charts?on_conflict=id", "POST", part)
        if st < 400:
            ok += len(part)
        else:
            print("   !! 图表批次失败 %s %s" % (st, r))
    print("wb_report_charts  %d/%d 张" % (ok, len(charts)))

    # ---------- 4. 回读核对 ----------
    print("\n---- 回读核对 ----")
    st, r = req("wb_reports?id=eq.%s&select=id,name,title" % rid)
    print("研报      ", st, r)
    st, r = req("wb_report_mods?report_id=eq.%s&select=no,title&order=seq.asc" % rid)
    print("模块      %s，%d 条" % (st, len(r) if isinstance(r, list) else r))
    if isinstance(r, list):
        print("          编号：", " ".join(x["no"] for x in r))
    st, r = req("wb_report_charts?report_id=eq.%s&select=id,name&order=seq.asc" % rid)
    print("图表      %s，%d 张" % (st, len(r) if isinstance(r, list) else r))
    if isinstance(r, list):
        for x in r:
            print("          %-26s %s" % (x["id"], x["name"]))


if __name__ == "__main__":
    main()
