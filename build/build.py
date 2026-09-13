# -*- coding: utf-8 -*-
"""把种子数据、红色主题 CSS、ECharts 库与云环境配置注入模板，产出两个独立页面：

  deploy/index.html    工作台（单文件，含全部业务模块）
  deploy/report.html   深度研究报告页（?code=600456，数据来自数据库，可编辑）

「不要所有东西全都放在 index 一个页面」——研报独立成页，工作台里点标的名称跳转过去。
用法： python build.py
"""
import io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEPLOY = os.path.join(ROOT, "deploy")
SEED = os.path.join(HERE, "seed")

CFG = json.load(io.open(os.path.join(HERE, "cloud.json"), encoding="utf-8"))
CLOUD = {"envId": CFG["envId"], "key": CFG["key"]}


def rd(p):
    return json.load(io.open(p, encoding="utf-8"))


def wr(dst, txt):
    io.open(dst, "w", encoding="utf-8").write(txt)
    print("  已生成 %-34s %8.1f KB" % (os.path.basename(dst), os.path.getsize(dst) / 1024.0))


def build_index():
    print("[1/2] 工作台 index.html")
    seed = {
        "meta": rd(os.path.join(SEED, "meta.json")),
        "tasks": rd(os.path.join(SEED, "tasks.json")),
        "permits": rd(os.path.join(SEED, "permits.json")),
        "milestones": rd(os.path.join(SEED, "milestones.json")),
        "watchlist": rd(os.path.join(SEED, "watchlist.json")),
        "contacts": rd(os.path.join(SEED, "contacts.json")),
        # 工作计划：按用户要求「数据留空白，自己添加」——不预置种子
        "works": [],
    }
    tpl = io.open(os.path.join(DEPLOY, "app.template.html"), encoding="utf-8").read()
    assert "/*__SEED__*/" in tpl, "app.template.html 缺少 __SEED__ 占位符"
    payload = ("window.WB_CFG = " + json.dumps(CLOUD, ensure_ascii=False) + ";\n"
               + "window.WB_SEED = " + json.dumps(seed, ensure_ascii=False, separators=(",", ":")) + ";")
    wr(os.path.join(DEPLOY, "index.html"), tpl.replace("/*__SEED__*/", payload))


def build_report():
    print("[2/2] 研报页 report.html")
    tplp = os.path.join(DEPLOY, "report.template.html")
    tpl = io.open(tplp, encoding="utf-8").read()

    libp = os.path.join(HERE, "lib", "echarts.min.js")
    if not os.path.exists(libp):
        sys.exit("缺少 %s —— 先跑 python extract_report.py 从原研报里抽取" % libp)
    lib = io.open(libp, encoding="utf-8").read()

    cssp = os.path.join(HERE, "report_theme.css")
    if not os.path.exists(cssp):
        sys.exit("缺少 %s —— 先跑 python extract_report.py" % cssp)
    css = io.open(cssp, encoding="utf-8").read()

    seedp = os.path.join(SEED, "report_600456.json")
    seed = rd(seedp) if os.path.exists(seedp) else None

    for ph in ("/*__ECHARTS__*/", "/*__REPORTCSS__*/", "/*__RPTCFG__*/"):
        assert ph in tpl, "report.template.html 缺少占位符 " + ph

    cfg_js = ("window.RPT_CFG = " + json.dumps(CLOUD, ensure_ascii=False) + ";\n"
              + "window.RPT_SEED = "
              + (json.dumps(seed, ensure_ascii=False, separators=(",", ":")) if seed else "null") + ";")

    out = (tpl.replace("/*__ECHARTS__*/", lib)
              .replace("/*__REPORTCSS__*/", css)
              .replace("/*__RPTCFG__*/", cfg_js))
    wr(os.path.join(DEPLOY, "report.html"), out)
    if seed:
        print("  内置兜底副本：%s（%d 个模块 / %d 张图表）"
              % (seed["report"]["code"], len(seed["mods"]), len(seed["charts"])))


if __name__ == "__main__":
    print("envId = %s" % CFG["envId"])
    build_index()
    build_report()
    print("完成。")
