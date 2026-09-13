# -*- coding: utf-8 -*-
"""生成三个视图的截图页（延迟切页，避开 boot 的 pullAll 覆盖）"""
import io, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DATA = [
    ("今天", "完成铜供需平衡表 v1", dict(priority="P0", progress=60, status="doing", category="研究",
        due_date="TODAY", key_actions="1. 拉海关与冶炼厂数据 / 2. 建平衡表 / 3. 找券商交叉验证",
        metric="平衡表版本", baseline="无", target="v1", kpi="口径可复用，能支撑一次完整路演")),
    ("本周", "拜访 2 家券商矿业分析师", dict(priority="P1", progress=40, status="doing", category="人脉",
        due_date="2026-09-15", metric="接触人数", baseline="0", target="2", review_date="2026-09-14")),
    ("本月", "完成境外投资（ODI）备案材料初稿", dict(priority="P0", progress=25, status="doing", category="合规",
        due_date="2026-09-30", metric="材料完成度", baseline="0%", target="初稿提交")),
    ("本季度", "锁定首个矿权标的并完成尽调", dict(priority="P0", progress=15, status="doing", category="资源",
        due_date="2026-12-31", metric="尽调完成度", target="出尽调报告")),
    ("本年", "搭建完成矿业并购的合规与资金框架", dict(priority="P1", progress=30, status="doing", category="战略",
        due_date="2026-12-31", metric="框架落地项", baseline="0", target="6 项")),
    ("五年计划", "五年内控股 1 座在产中型铜矿", dict(priority="P0", progress=10, status="doing", category="战略",
        metric="年产铜金属量（万吨）", baseline="0", target="5", kpi="并表满 12 个月、项目 IRR>15%",
        resources="自有资金 + 并购贷 + 产业基金",
        risk="铜价长期低于 6000 美元 / 标的所在国政策收紧",
        review_date="2027-03-01", milestone="M12 完成首矿交割", tags="铜 / 核心仓")),
    ("十年计划", "十年建成自有矿业产业集团", dict(priority="P0", progress=5, status="todo", category="战略",
        metric="集团营收（亿元）", baseline="0", target="50",
        kpi="3 座在产矿 + 自有贸易与冶炼环节", review_date="2027-06-30", tags="集团 / 长周期")),
    ("二十年计划", "二十年形成跨国资源产业集团", dict(priority="P1", progress=0, status="todo", category="战略",
        metric="海外资产占比", baseline="0%", target="60%", review_date="2028-01-01", tags="全球化")),
]


def js_str(v):
    if v == "TODAY":
        return "today()"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


lines = []
for hz, title, ex in DATA:
    props = ",".join("%s:%s" % (k, js_str(v)) for k, v in ex.items())
    lines.append('  mk(%s,%s,{%s});' % (js_str(hz), js_str(title), props))
BODY = "\n".join(lines)

PROBE = '''
<script>
setTimeout(function(){
  function mk(hz,title,extra){ var row={horizon:hz,title:title}; for(var k in (extra||{})) row[k]=extra[k]; return insertRow("works", row); }
__BODY__
  App.go("work");
  UI.workTab="__VIEW__";
  renderWork();
  window.scrollTo(0,0);
},4200);
</script>
'''.replace("__BODY__", BODY)

src = io.open(os.path.join(ROOT, "deploy", "index.html"), encoding="utf-8").read()
for view in ("dashboard", "horizon", "timeline"):
    out = src.replace("</body>", PROBE.replace("__VIEW__", view) + "</body>")
    io.open(os.path.join(HERE, "__s_%s.html" % view), "w", encoding="utf-8").write(out)
print("3 shot pages written")
