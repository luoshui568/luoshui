# -*- coding: utf-8 -*-
"""seed ← DB 单向同步：把「线上已被人工/浏览器规范化过」的内容回写到 seed。

背景：
  seed 是**恢复源**（push_report.py 用它重建库内研报），所以它必须忠实反映线上现状。
  但线上有两类合法变更会让 seed 显得「过期」：
    1. 实体规范化 —— 经 contenteditable / sanitizeHtml 往返后，正文里的裸 `<` `>`
       会变成 `&lt;` `&gt;`。语义完全相同，但字节不同。
    2. 人工精简 —— 用户在研报页直接删掉了几个字（例：kicker 尾部的「模板」）。

安全边界（**失败优先**）：
  只接受上面两类可证等价/可证精简的差异；其余差异一律不改 seed，打印后以非 0 退出，
  交由人工判断。绝不反向覆盖线上数据。

用法：
  python build/sync_seed_from_db.py            # 预演（只报告，不写盘）
  python build/sync_seed_from_db.py --apply    # 真正回写
"""
import html
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(HERE, "cloud.json"), encoding="utf-8"))
REST = "https://%s.api.tcloudbasegateway.com/v1/rdb/rest/" % CFG["envId"]
HDR = {"Authorization": "Bearer " + CFG["key"]}

SHELL_TXT = ["kicker", "title", "subtitle", "verdict_title", "verdict_html",
             "kpi_note", "essence_html", "footer_html"]


def get(path):
    r = urllib.request.Request(REST + path, headers=HDR)
    with urllib.request.urlopen(r, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def equiv(a, b):
    """两级等价：字节相同 / HTML 反转义后相同。"""
    a, b = str(a or ""), str(b or "")
    if a == b:
        return "same"
    if html.unescape(a) == html.unescape(b):
        return "entity"
    return ""


def trimmed(db, sd):
    """db 是 sd 的**严格子串** → 判定为人工精简（只允许 db 更短）。"""
    d, s = str(db or ""), str(sd or "")
    if d and d != s and d in s:
        return True
    return False


def sync(name, apply=False):
    path = os.path.join(HERE, "seed", name)
    seed = json.load(io.open(path, encoding="utf-8"))
    rid = seed["report"]["code"]
    changes, rejects = [], []

    # ---------- 1. 研报头 ----------
    row = get("wb_reports?id=eq.%s" % rid)
    if not row:
        print("❌ 库里没有 %s" % rid)
        return 1, 1
    r0 = row[0]
    for k in SHELL_TXT:
        st = equiv(r0.get(k), seed["report"].get(k))
        if st:
            continue
        if trimmed(r0.get(k), seed["report"].get(k)):
            changes.append("report.%s 人工精简" % k)
            if apply:
                seed["report"][k] = r0.get(k)
        else:
            rejects.append("report.%s" % k)

    # ---------- 2. 模块 ----------
    mods = {m["id"]: m for m in get("wb_report_mods?report_id=eq.%s" % rid)}
    for m in seed["mods"]:
        key = "%s_m%s" % (rid, m["no"])
        d = mods.get(key)
        if not d:
            rejects.append("缺模块 %s" % key)
            continue
        for f in ("title", "html"):
            st = equiv(d.get(f), m.get(f))
            if st == "same":
                continue
            if st == "entity":
                changes.append("%s.%s 实体规范化" % (key, f))
                if apply:
                    m[f] = d.get(f)
            elif trimmed(d.get(f), m.get(f)):
                changes.append("%s.%s 人工精简" % (key, f))
                if apply:
                    m[f] = d.get(f)
            else:
                rejects.append("%s.%s" % (key, f))
        if str(d.get("seq")) != str(m.get("seq")):
            rejects.append("%s.seq" % key)

    # ---------- 3. 图表 ----------
    charts = {c["id"]: c for c in get("wb_report_charts?report_id=eq.%s" % rid)}
    for c in seed["charts"]:
        key = "%s_%s" % (rid, c["id"])
        d = charts.get(key)
        if not d:
            rejects.append("缺图表 %s" % key)
            continue
        if json.dumps(d.get("opt"), sort_keys=True) != json.dumps(c.get("opt"), sort_keys=True):
            # 图表 option 是 jsonb，键序会被规范化 → 用规范化后比较
            if json.dumps(d.get("opt"), sort_keys=True) != json.dumps(c.get("opt"), sort_keys=True):
                rejects.append("%s.opt" % key)
        if d.get("name") != c.get("name"):
            rejects.append("%s.name" % key)

    print("── %s" % name)
    for c in changes:
        print("   ~ %s" % c)
    for r in rejects:
        print("   ✗ 需人工判断：%s" % r)
    if not changes and not rejects:
        print("   = 无需同步")
    if apply and changes:
        io.open(path, "w", encoding="utf-8").write(
            json.dumps(seed, ensure_ascii=False, separators=(",", ":")))
        print("   ✔ 已回写 seed（%d 处）" % len(changes))
    return (1 if rejects else 0), len(changes)


def main():
    apply = "--apply" in sys.argv
    d = os.path.join(HERE, "seed")
    names = sorted(f for f in os.listdir(d)
                   if f.startswith("report_") and f.endswith(".json"))
    print("seed ← DB %s\n" % ("回写" if apply else "预演（加 --apply 才写盘）"))
    rc, tot = 0, 0
    for n in names:
        a, b = sync(n, apply)
        rc |= a
        tot += b
        print()
    print("=" * 62)
    print("共 %d 处差异可安全同步 · %s" % (tot, "存在需人工判断项 ❌" if rc else "全部等价 ✅"))
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
