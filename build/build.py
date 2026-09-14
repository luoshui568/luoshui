# -*- coding: utf-8 -*-
"""把种子数据、红色主题 CSS、ECharts 库与云环境配置注入模板，产出三个独立页面：

  deploy/index.html     工作台（单文件，含全部业务模块）
  deploy/report.html    深度研究报告页（?code=600456，数据来自数据库，可编辑）
  deploy/research.html  研究报告库（列表页，超管与团队成员共用入口）

「不要所有东西全都放在 index 一个页面」——研报独立成页，工作台里点标的名称跳转过去；
研报库也是独立成页，工作台侧栏的「研究报告」直接跳过去（不占 index 的体积）。
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


def pinyin_js():
    """生成「拼音首字母」运行时（锚点表由 build/_calib_pinyin.py 标定）。

    为什么不用内置字表：常用字表动辄 10~15KB，两个页面上都要放一份。
    这里换成**区间定位**——浏览器自带的 zh 排序规则本来就按拼音排，
    把字与 23 个声母锚点两两比较，落在哪个区间就取哪个声母，
    体积只有下面两个 23 字字符串（≈90 字节）。

    表怎么来的、踩过哪些坑：见 `_calib_pinyin.py` 顶部注释。
    实测：项目真实数据里的 1706 个汉字 **0 冲突**；全 CJK 区仅 79/20892（0.38%）生僻字不准。
    """
    d = rd(os.path.join(HERE, "py_table.json"))
    letters = d["letters"]
    a = d["anchorChars"]
    assert len(letters) == len(a) == 23, "py_table.json 的锚点表不自洽"
    assert "".join(letters) == "abcdefghjklmnopqrstwxyz", "声母顺序不对：%s" % "".join(letters)
    exc = d.get("exceptions") or {}
    st = d.get("stat") or {}
    assert not st.get("conflictCommon"), "项目数据里还有拼音冲突字，先重跑 _calib_pinyin.py"
    return (
        "/* ---------------- 拼音首字母（锚点在下方两个常量里） ----------------\n"
        "   为什么长这样：常用字表要 10KB+，两个页面各放一份不划算。\n"
        "   换成区间定位 —— 浏览器自带的 zh 排序规则本来就按拼音排，把字与 23 个\n"
        "   声母锚点两两比，落在哪个区间就取哪个声母，体积只有两个 23 字字符串。\n"
        "   锚点表由 build/_calib_pinyin.py 标定：项目真实数据 1706 字 **0 冲突**。\n"
        "   ⚠️ 别手改锚点：它不是「每声母找一个代表字」那么随意 ——\n"
        "      必须按拼音顺序**夹紧**取下界，否则区间会互相串（踩过，见该脚本注释）。 */\n"
        "var PY_L = %s;\n" % json.dumps("".join(letters)) +
        "var PY_A = %s;\n" % json.dumps(a) +
        "var PY_EXC = %s;\n" % json.dumps(exc, ensure_ascii=False) +
        "var PY_OK = false;\n"
        "var PY_CACHE = {};\n"
        "function pyCh(ch){\n"
        "  var e = PY_EXC[ch];\n"
        "  if(e) return e;\n"
        "  var lo = 0, hi = PY_A.length - 1, hit = '';\n"
        "  while(lo <= hi){\n"
        "    var mid = (lo + hi) >> 1;\n"
        "    if(ch.localeCompare(PY_A.charAt(mid), 'zh') >= 0){ hit = PY_L.charAt(mid); lo = mid + 1; }\n"
        "    else hi = mid - 1;\n"
        "  }\n"
        "  return hit;\n"
        "}\n"
        "function pyInit(s){\n"
        "  s = String(s == null ? '' : s);\n"
        "  var out = '';\n"
        "  for(var i = 0; i < s.length; i++){\n"
        "    var c = s.charAt(i), n = c.charCodeAt(0);\n"
        "    if(n < 128){\n"
        "      if((n >= 48 && n <= 57) || (n >= 97 && n <= 122) || (n >= 65 && n <= 90)) out += c.toLowerCase();\n"
        "      continue;\n"
        "    }\n"
        "    out += pyCh(c);\n"
        "  }\n"
        "  return out;\n"
        "}\n"
        "/* 按原串缓存：同一只标的每次按键都重算会很卡（206 只 × 每字一次二分） */\n"
        "function pyInitCached(s){\n"
        "  var k = String(s == null ? '' : s);\n"
        "  var v = PY_CACHE[k];\n"
        "  if(v === undefined){ v = pyInit(k); PY_CACHE[k] = v; }\n"
        "  return v;\n"
        "}\n"
        "/* 查「这段文本的拼音首字母里有没有 q」；q 必须已经是纯小写字母数字 */\n"
        "function pyHit(src, q){\n"
        "  return PY_OK && q && pyInitCached(src).indexOf(q) >= 0;\n"
        "}\n"
        "/* 自检：环境不支持 zh 排序时（会回落到码点序）**整体禁用** ——\n"
        "   宁可不支持拼音搜索，也不能给出错的拼音把用户带偏。 */\n"
        "(function(){\n"
        "  try{\n"
        "    if(PY_A.length !== PY_L.length) return;\n"
        "    var t = '贵g研y铂b业y钛t中z国g恒h邦b鲁l西x新x三s蜀s';\n"
        "    for(var i = 0; i < t.length; i += 2){\n"
        "      if(pyCh(t.charAt(i)) !== t.charAt(i + 1)) return;\n"
        "    }\n"
        "    PY_OK = true;\n"
        "  }catch(e){ PY_OK = false; }\n"
        "})();\n"
    )


def build_index():
    print("[1/3] 工作台 index.html")
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
    assert "/*__PY__*/" in tpl, "app.template.html 缺少 __PY__ 占位符"
    payload = ("window.WB_CFG = " + json.dumps(CLOUD, ensure_ascii=False) + ";\n"
               + "window.WB_SEED = " + json.dumps(seed, ensure_ascii=False, separators=(",", ":")) + ";")
    out = tpl.replace("/*__SEED__*/", payload).replace("/*__PY__*/", pinyin_js())
    wr(os.path.join(DEPLOY, "index.html"), out)


def build_report():
    print("[2/3] 研报页 report.html")
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


def build_research():
    """研究报告库（独立页面）。

    只注入云端配置 —— 列表数据全部由页面自己从 wb_reports 拉，
    所以加一份新研报、改个标题都不用重新构建。
    """
    print("[3/3] 研报库 research.html")
    tplp = os.path.join(DEPLOY, "research.template.html")
    tpl = io.open(tplp, encoding="utf-8").read()
    for ph in ("/*__LIBCFG__*/", "/*__PY__*/"):
        assert ph in tpl, "research.template.html 缺少占位符 " + ph
    cfg_js = "window.WB_CFG = " + json.dumps(CLOUD, ensure_ascii=False) + ";"
    wr(os.path.join(DEPLOY, "research.html"),
       tpl.replace("/*__LIBCFG__*/", cfg_js).replace("/*__PY__*/", pinyin_js()))


if __name__ == "__main__":
    print("envId = %s" % CFG["envId"])
    build_index()
    build_report()
    build_research()
    print("完成。")
