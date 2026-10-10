# -*- coding: utf-8 -*-
"""600456 宝钛股份：补 m12 管理层名单（源：2025 年年度报告第 36–40 页 + 签章页）。

⚠️ 年报的董监高名单是**表格**，发现报告的段落接口取不到 → 只录入有明确出处的人名与日期，
   完整名单（含独立董事）在 source 里注明「见年报原表」，不臆造。
"""
import io, json, os, shutil, sys, time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
B = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(B, 'seed', 'data_v31_600456.json')
BK = os.path.join(B, 'backup')
GO = '--go' in sys.argv

d = json.load(io.open(P, encoding='utf-8'))

MGMT = {
    'overview': (
        '公司控股股东为宝钛集团有限公司（原宝鸡有色金属加工厂，代号 902），'
        '实际控制人为陕西省国资委。管理层具有深厚的有色金属加工行业背景。'
        '2025 年公司完成总经理交接：陈战乾于 4 月 30 日辞去总经理、总工程师职务，'
        '张海龙于 7 月 14 日经第八届董事会第十六次临时会议聘任接任。'
    ),
    'rows': [
        ['王俭', '董事长（法定代表人）', '在任（至 2026-04-27 年报报出日）',
         '2026 年半年报载明为公司法定代表人；2025 年年报签章人'],
        ['张海龙', '总经理；第八届董事会董事', '总经理 2025-07-14 起；董事 2025-07-30 起',
         '经第八届董事会第十六次临时会议聘任、临时股东大会选举'],
        ['陈战乾', '原总经理、总工程师（已离任）', '2025-04-30 辞总经理；2025-07-13 辞董事',
         '因工作变动离任；年报载近三年无证券监管机构处罚'],
    ],
    'governance': (
        '**央企/省属国企体制**：优点是战略稳定性强、军工客户关系稳固、融资成本低；'
        '缺点是市场化激励不足，对钛价波动与需求变化的响应速度可能慢于民营同行。'
        '2025 年 ROE 降至 5.67%，即体现「规模优先、回报次之」的经营取向。'
        '治理架构上，2025 年 10 月 15 日临时股东大会通过《关于公司取消监事会、'
        '修订〈公司章程〉的议案》，公司不再设监事会及监事，其职权由董事会审计委员会行使，'
        '监督职能进一步向董事会集中；年报另明确总经理、副总经理、董事会秘书、'
        '财务负责人均在公司领取薪酬，未在控股股东单位担任职务。'
    ),
    'source': (
        '高管名单与变动取自宝钛股份《2025 年年度报告》（2026-04-28 披露，共 215 页）'
        '第 36–40 页「董事和高级管理人员的情况」及第 215 页签章页'
        '（董事长：王俭，董事会批准报送日期 2026-04-27）；法定代表人信息见'
        '《2026 年半年度报告》（2026-08-26）。'
        '说明：年报中董监高完整名单以表格形式披露，段落接口无法取回，'
        '本次仅录入有明确文本出处的人名与日期，未逐人录入（含独立董事）；'
        '如需完整名单请调阅年报原表。'
    ),
}

print('=' * 74)
print('600456 宝钛股份 · mgmt（m12 管理层与治理）变更预览')
print('=' * 74)
old = d.get('mgmt') or {}
for f in ('overview', 'rows', 'governance', 'source'):
    o, n = old.get(f), MGMT.get(f)
    if o == n:
        print('  · %-10s 无变化' % f)
    else:
        print('  · %-10s 旧 %s → 新 %s' % (f, len(o) if o is not None else 0, len(n)))
print()
print('--- 新增名单表 ---')
for r in MGMT['rows']:
    print('  %-6s | %-22s | %-40s' % (r[0], r[1], r[2]))

if not GO:
    print()
    print('（预演模式，未写盘。加 --go 生效）')
    raise SystemExit(0)

os.makedirs(BK, exist_ok=True)
stamp = time.strftime('%Y%m%d_%H%M%S')
bakp = os.path.join(BK, 'data_v31_600456_pre_mgmt_%s.json' % stamp)
shutil.copy2(P, bakp)
print()
print('已备份 → %s' % os.path.relpath(bakp, B))

before = {k: json.dumps(v, ensure_ascii=False) for k, v in d.items()}
d['mgmt'] = MGMT
io.open(P, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=1) + '\n')

back = json.load(io.open(P, encoding='utf-8'))
assert back['mgmt']['rows'] == MGMT['rows'], 'mgmt.rows 写盘不一致'
assert len(back['mgmt']) == 4, 'mgmt 键数异常：%s' % list(back['mgmt'])
changed = [k for k in before if json.dumps(back[k], ensure_ascii=False) != before[k]]
print('回读校验通过。本轮变更的顶层键：%s' % changed)
assert changed == ['mgmt'], '意外改动了别的字段：%s' % changed
print('新文件 %d 字节' % os.path.getsize(P))
