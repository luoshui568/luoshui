# -*- coding: utf-8 -*-
"""生成工作计划模块的功能探针页面（headless 自动化测试用）"""
import io, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PROBE = r'''
<script>
window.__E=[];
window.onerror=function(m,u,l,c){window.__E.push(m+" @"+l+":"+c);};
setTimeout(function(){
  var out={};
  try{
    /* 1. 进入工作计划页（默认看板视图） */
    App.go("work");
    out.tabDashDisplay = document.getElementById("workDashBox").style.display;
    out.hzcCards = document.querySelectorAll("#workDashBox .hzc").length;

    /* 2. 新增 4 条计划，覆盖不同档位与父子关系 */
    function mk(hz,title,extra){ var row={horizon:hz,title:title}; for(var k in (extra||{})) row[k]=extra[k]; return insertRow("works", row); }
    mk("今天","今日：完成铜供需平衡表 v1",{priority:"P0",progress:50,status:"doing",category:"研究",due_date:today(),key_actions:"拉数据 / 建表",metric:"平衡表版本",target:"v1"});
    mk("五年计划","五年内控股 1 座在产中型铜矿",{priority:"P0",category:"战略",metric:"年产铜金属量(万吨)",baseline:"0",target:"5",kpi:"并表满12个月、IRR>15%",review_date:"2027-03-01"});
    var pid = mk("十年计划","十年建成矿业产业集团",{category:"战略"}).id;
    mk("十年计划","子计划：搭建境外并购平台",{parent_id:pid,category:"资本",progress:20});
    out.worksLen = S.works.length;

    /* 3. 子计划关系识别 */
    out.kids = workSubTree(pid).length;

    /* 4. 排序应为：今天 → 五年计划 → 十年计划 */
    sortState();
    out.order = S.works.map(function(w){return w.horizon;}).join(" > ");

    /* 5. 看板三块区块渲染 */
    App.workTab("dashboard"); renderWork();
    out.hzc2 = document.querySelectorAll("#workDashBox .hzc").length;
    out.dueBox = (document.getElementById("workDueBox").textContent||"").trim().length > 0;
    out.revBox = (document.getElementById("workReviewBox").textContent||"").trim().length > 0;

    /* 6. 按周期浏览 + 筛选 */
    App.workTab("horizon"); renderWork();
    out.workCards = document.querySelectorAll("#workBox .wcrd").length;
    App.workHzFilter("十年计划"); renderWork();
    out.hzFilterCards = document.querySelectorAll("#workBox .wcrd").length;
    out.hzChipOn = document.querySelectorAll("#workHzChips .chip.on").length;
    App.workHzFilter("十年计划");

    /* 7. 时间轴 */
    App.workTab("timeline"); renderWork();
    out.tlNodes = document.querySelectorAll("#workTimeBox .tlnd").length;

    /* 8. 状态循环 + 子计划渲染在父卡内 */
    App.workTab("horizon"); renderWork();
    var first = S.works[0].id;
    App.workCycle(first);
    out.cycled = findRow("works",first).status;
    out.kidsBox = document.querySelectorAll("#workBox .wcrd .kids").length;

    /* 9. cleanRow 白名单命中 */
    var ck = Object.keys(cleanRow("works", S.works[1])).sort();
    out.cleanN = ck.length;
    out.hasHz = ck.indexOf("horizon") >= 0;
    out.hasActions = ck.indexOf("key_actions") >= 0;
    out.hasParent = ck.indexOf("parent_id") >= 0;

    /* 10. 待同步队列（file:// 下云端不通，走本机队列） */
    out.pending = PENDING.length;

    document.title = "T|" + JSON.stringify(out);
  }catch(e){ document.title = "TERR|" + e.message + "@@" + JSON.stringify(out); }
},1600);
</script>
'''

src = io.open(os.path.join(ROOT, "deploy", "index.html"), encoding="utf-8").read()
io.open(os.path.join(HERE, "__probe.html"), "w", encoding="utf-8").write(src.replace("</body>", PROBE + "</body>"))
print("probe written")
