# -*- coding: utf-8 -*-
"""生成工作台种子数据：任务课表 / 里程碑 / 标的库 / 人脉库 / 申请清单
输出 build/seed/*.json，并打印统计信息。
"""
import json, os, sys, datetime, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curriculum import WEEKS, START_DATE
from permits import PERMITS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed")
os.makedirs(OUT, exist_ok=True)

PHASE_NAME = {
    "P0": "奠基期 · 建立认知与纪律",
    "P1": "阶段一 · 资本驱动与周期套利",
    "P2": "阶段二 · 资源卡位与资产证券化",
    "P3": "阶段三 · 纵向一体化与价值链重塑",
}
PHASE_RANGE = {
    "P0": "第 1-4 周",
    "P1": "第 5-30 周",
    "P2": "第 31-46 周",
    "P3": "第 47-52 周",
}

def uid(prefix, *parts):
    h = hashlib.md5(("|".join(str(p) for p in parts)).encode("utf-8")).hexdigest()[:12]
    return "%s_%s" % (prefix, h)

def daterange(start, n):
    d0 = datetime.date(*[int(x) for x in start.split("-")])
    return [(d0 + datetime.timedelta(days=i)) for i in range(n)]

# ---------- 1. 每日任务 ----------
tasks = []
day_no = 0
for w in WEEKS:
    assert len(w["days"]) == 7, "week %s has %s days" % (w["n"], len(w["days"]))
    for di, d in enumerate(w["days"]):
        day_no += 1
        cat, title, detail, deliv, mins, pri = d
        date = daterange(START_DATE, 400)[day_no - 1]
        tasks.append(dict(
            id=uid("t", day_no, title),
            seq=day_no,
            task_date=date.isoformat(),
            weekday="一二三四五六日"[date.weekday()],
            week_no=w["n"],
            week_theme=w["theme"],
            week_goal=w["goal"],
            phase=w["phase"],
            phase_name=PHASE_NAME[w["phase"]],
            category=cat,
            title=title,
            detail=detail,
            deliverable=deliv,
            minutes=int(mins),
            priority=pri,
            status="todo", note="",
        ))
assert day_no == 364, day_no

# ---------- 2. 里程碑 ----------
MILESTONES = [
 (1,"2026-10-10","奠基包交付：战略宪法 + 三表 + 工作台跑通","战略宪法v1已签署；资金/时间三表完成；工作台录入并云端同步","P0"),
 (2,"2026-11-10","周期判断框架成型","周期位置仪表盘含价格/库存/Capex/估值四分位，可持续更新","P0"),
 (3,"2026-12-10","研究框架手册 v1 定稿","宏观→行业→公司→估值→组合五层框架成文，完成一家公司完整估值","P0"),
 (4,"2027-01-10","首份公司深度报告 + 3 份矿山档案卡","3000 字以上深度报告1份；卡莫阿/格林布什/Oyu Tolgoi 档案卡完成","P1"),
 (5,"2027-02-10","交易规则手册 v1 定稿","含四象限操作卡、买卖规则、仓位与风控参数、禁忌清单","P1"),
 (6,"2027-03-10","模拟盘收官并启动实盘","3个月模拟盘总结完成，规则遵守率≥80%，实盘首单执行","P1"),
 (7,"2027-04-10","估值能力达标","NAV/DCF 模板可复用；完成 3 家公司估值并写敏感性分析","P1"),
 (8,"2027-05-10","衍生品对冲体系上线","开通期货并完成首笔套保；套保比例与保证金风控规则成文","P1"),
 (9,"2027-06-10","情景-仓位映射表就绪","四个宏观剧本各有明确触发信号与对应配置","P1"),
 (10,"2027-07-10","业绩归因体系建立","收益拆解为Beta/矿种/个股/择时/杠杆；体系升级至 v2","P1"),
 (11,"2027-08-10","机构化路径决策完成","明确是否走私募管理人路径，落地第一阶段材料或明确放弃理由","P1"),
 (12,"2027-09-10","阶段一 GATE 评估（一周年）","资金规模/收益/回撤/规则遵守率/研究产出/人脉质量六项打分达标","P1"),
 (13,"2027-10-10","矿权法律知识体系完备","矿权取得-转让-审批-融资全流程图谱；接触矿业律师并建立合作","P2"),
 (14,"2027-11-10","尽调流水线运行","DD清单六模块 + 数据室 + 红旗清单；完成一次桌面尽调演练","P2"),
 (15,"2027-12-10","矿权估值模板完成","含三情景敏感性分析，可用公开项目出具估值报告","P2"),
 (16,"2028-01-10","交易架构与 Term Sheet 就绪","SPV架构图、分期付款/对赌条款库、Term Sheet 模板、谈判手册 v1","P2"),
 (17,"2028-02-10","跨境合规全流程打通","发改委+商务部+外汇 三段流程时间轴与材料包齐备","P2"),
 (18,"2028-03-10","首个目标项目完成桌面尽调","出具尽调简报含红旗清单与初步估值","P2"),
 (19,"2028-04-10","融资方案与弹药确认","明确自有资金上限、可撬动融资规模、资金成本结构","P2"),
 (20,"2028-05-10","核心团队至少 3 人到岗","金融线、技术线、商务线各至少 1 人；AB 角安排明确","P2"),
 (21,"2028-06-10","阶段二 GATE 评估","资源控制力/团队/合规架构/融资能力四项达标方可进入阶段三","P2"),
 (22,"2028-07-10","阶段三技术路线选定","明确优先进入的加工环节与技术来源路径（自研/引进/合作）","P3"),
 (23,"2028-08-10","阶段三商业计划书定稿","八段式 BP 完成，含客户地图与认证路线图","P3"),
 (24,"2028-09-10","两周年总复盘","三阶段进度评估、认知清单、战略宪法 v4、第三年课表","P3"),
]
milestones = [dict(id=uid("m", n), seq=n, due_date=due, title=t, criteria=c, phase=p,
                   status="未启动", progress=0) for (n, due, t, c, p) in MILESTONES]

# ---------- 3. 标的库（种子，用户可增删改） ----------
WATCH_SEED = [
 ("紫金矿业","601899.SH","铜/金/锂","综合龙头","A股","全球铜金龙头，成本曲线前25%，海外项目储备丰富；关注其铜产量爬坡与锂项目进度。","阶段一核心池"),
 ("洛阳钼业","603993.SH","铜/钴/钼钨","综合龙头","A股","刚果金TFM/KFM铜钴资源全球稀缺，钴供给定价权强；关注政策与物流风险。","阶段一核心池"),
 ("江西铜业","600362.SH","铜","冶炼一体化","A股","国内最大铜冶炼企业，TC/RC 敏感度最高，可作为矿端/冶炼端相对价值标的。","阶段一观察池"),
 ("云铝股份","000807.SZ","铝","水电铝一体化","A股","绿电铝成本优势，受益于电解铝产能天花板与碳成本上升。","阶段一观察池"),
 ("天齐锂业","002466.SZ","锂","锂盐加工","A股","锂资源+加工一体，SQM 权益与格林布什参股；锂价弹性最大的标的之一。","阶段一核心池"),
 ("赣锋锂业","002460.SZ","锂","全产业链","A股","资源+冶炼+电池回收全链条布局，海外资源布局较广。","阶段一核心池"),
 ("北方稀土","600111.SH","稀土","磁材上游","A股","稀土配额龙头，受益于磁材需求与出口管制带来的议价能力变化。","阶段一观察池"),
 ("华友钴业","603799.SH","钴/镍/锂","前驱体+资源","A股","印尼镍项目成本优势明显，前驱体一体化，关注海外政策风险。","阶段一观察池"),
 ("山东黄金","600547.SH","黄金","国内龙头","A股","国内黄金产量龙头，实际利率下行周期的主要受益者。","阶段一观察池"),
 ("宝钛股份","600456.SH","钛","钛材加工","A股","航空级钛材核心供应商，受益于军工与民航需求；阶段三高附加值加工环节样本。","阶段一观察池"),
 ("贵研铂业","600459.SH","贵金属","贵金属加工","A股","贵金属材料深加工，催化剂与功能材料；阶段三「资源→高附加值产品」的观察样本。","阶段一观察池"),
 ("BHP Group","BHP.N","铜/铁矿","全球巨头","美股","全球最低成本铁矿与铜矿资产组合，观察其资本配置与分红策略的周期信号。","阶段一研究池"),
 ("Rio Tinto","RIO.N","铝/铜/铁矿","全球巨头","美股","资本配置纪律最强的巨头之一，可作为行业资本开支周期的观察窗口。","阶段一研究池"),
 ("Freeport-McMoRan","FCX.N","铜","全球铜矿","美股","Grasberg 与美洲铜资产，全球铜供给弹性最直接的观察标的。","阶段一研究池"),
 ("Albemarle","ALB.N","锂","全球锂业","美股","全球锂盐龙头，锂价周期弹性的海外对照标的。","阶段一研究池"),
 ("紫金黄金国际","02259.HK","黄金","境外平台","港股","紫金海外黄金资产平台，观察其境外融资与资产证券化路径。","阶段二研究池"),
]
watchlist = [dict(id=uid("w", n), name=n, code=c, variety=v, style=s, market=m,
                  thesis=t, note=tag, status="跟踪中", tags=tag, progress=0,
                  sort=i + 1) for i, (n, c, v, s, m, t, tag) in enumerate(WATCH_SEED)]

# ---------- 4. 人脉库（种子） ----------
CONTACT_SEED = [
 ("券商矿业分析师","卖方研究","行业信息与公司跟踪","券商研究所","阶段一（W23）","提供行业数据、公司调研机会；需用有质量的问题建立长期关系"),
 ("地质勘查院/地矿局专家","技术专家","判断矿山资源量与地质风险","地矿系统","阶段一末期（W35）","鉴定储量报告真伪、评估找矿潜力"),
 ("矿业专业律师","法律专家","矿权交易、跨境架构、合规","律所（矿业团队）","阶段二（W32）","矿权转让条件、交易陷阱、架构设计"),
 ("跨境税务师","财税专家","跨境架构、税务合规、CFC","四大/专业机构","阶段二（W28）","持股路径设计与税务成本测算"),
 ("银行并购部/授信经理","资金方","并购贷款与融资结构","商业银行","阶段二（W42）","并购贷款条件、额度与还款安排"),
 ("中信保项目险经理","风险保障","海外投资政治风险保险","中信保","阶段二（W40）","承保范围与费率，降低出海风险"),
 ("已出海矿企中层","产业专家","海外运营真实痛点","矿企","阶段二（W33）","社区、工会、政府关系、供应链的真实经验"),
 ("矿山运营负责人","运营专家","成本与效率管理","矿企/矿山","阶段二（W44）","单位成本控制、设备与人员管理"),
 ("下游采购/技术负责人","客户方","产品认证与需求痛点","电池/航空/半导体企业","阶段三（W48）","认证周期、质量一致性要求、长协定价"),
]
contacts = [dict(id=uid("c", r), sort=i + 1, role_name=r, kind=k, value=v, org=o, phase_plan=p, note=n, status="待接触")
            for i, (r, k, v, o, p, n) in enumerate(CONTACT_SEED)]

# ---------- 5. 申请清单 ----------
permits = []
for i, (code, name, cat, auth, ph, pre, mat, dur, cost, risk, pri) in enumerate(PERMITS):
    permits.append(dict(id=uid("p", code), code=code, seq=i + 1, name=name, category=cat,
                        authority=auth, phase=ph, prereq=pre, materials=mat, duration=dur,
                        cost=cost, risk=risk, priority=pri, status="未启动", progress=0,
                        owner="", due_date="", notes=""))

# ---------- 6. 元信息 ----------
meta = dict(
    start_date=START_DATE, total_days=day_no, total_weeks=len(WEEKS),
    phases=[dict(key=k, name=v, range=PHASE_RANGE[k]) for k, v in PHASE_NAME.items()],
)

def dump(name, obj):
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print("%-16s %6d 条  %8.1f KB" % (name, len(obj), os.path.getsize(p) / 1024.0))

dump("tasks.json", tasks)
dump("permits.json", permits)
dump("milestones.json", milestones)
dump("watchlist.json", watchlist)
dump("contacts.json", contacts)
dump("meta.json", meta)
print("\n日期范围：%s ~ %s" % (tasks[0]["task_date"], tasks[-1]["task_date"]))
print("分类分布：", {c: sum(1 for t in tasks if t["category"] == c) for c in sorted(set(t["category"] for t in tasks))})
print("阶段分布：", {c: sum(1 for t in tasks if t["phase"] == c) for c in ["P0", "P1", "P2", "P3"]})
print("优先级分布：", {c: sum(1 for t in tasks if t["priority"] == c) for c in ["P0", "P1", "P2"]})
print("总投入小时：%.1f" % (sum(t["minutes"] for t in tasks) / 60.0))
