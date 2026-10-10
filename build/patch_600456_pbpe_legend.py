# -*- coding: utf-8 -*-
"""定点修补 chart_pbpe：去掉 ECharts 内置图例（与 .vh-head 里的自定义图例重复）。

起因：截图目视发现图上方有两套图例 ——
  · .vh-head 里的「PB（左轴）/ PE(TTM)（右轴）」（HTML，颜色块 + 说明，未上传壳也可见）
  · ECharts 自带的「PB / PE(TTM)」（画在图内部右上角）
两套内容重复，看着像没做完。留 HTML 那套（信息更多：标了左右轴），
把 ECharts 图例关掉，并把 grid.top 从 58 收到 34 把空间还给曲线。

用法：python build/patch_600456_pbpe_legend.py [--go]
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

GO = '--go' in sys.argv
B = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
CFG = json.load(io.open(os.path.join(B, 'build', 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
CK = '600456_chart_pbpe'


def req(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header('Authorization', 'Bearer ' + CFG['key'])
    r.add_header('Content-Type', 'application/json')
    if method in ('POST', 'PATCH'):
        r.add_header('Prefer', 'return=representation')
    try:
        with urllib.request.urlopen(r, timeout=90) as f:
            raw = f.read()
            return f.status, (json.loads(raw.decode('utf-8')) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:400]


s, cur = req('GET', 'wb_report_charts?id=eq.%s&select=id,opt' % CK)
assert s == 200 and cur, 'GET 失败 %s %s' % (s, cur)
opt = cur[0]['opt']
if isinstance(opt, str):
    opt = json.loads(opt)

# 漂移闸：必须是本轮改过的版本（PB 红 / PE 蓝），否则不动
assert opt['series'][0]['itemStyle']['color'] == '#c8102e', '漂移：PB 不是红色'
assert opt['series'][1]['itemStyle']['color'] == '#2f6fb5', '漂移：PE 不是蓝色'
print('✅ 漂移闸通过（PB 红 / PE 蓝）')
print('   当前 legend =', json.dumps(opt.get('legend'), ensure_ascii=False))
print('   当前 grid   =', json.dumps(opt.get('grid'), ensure_ascii=False))

new = json.loads(json.dumps(opt))
new['legend'] = {'show': False}
new['grid'] = {'top': 34, 'left': 62, 'right': 66, 'bottom': 34}
print()
print('   新 legend   =', json.dumps(new['legend'], ensure_ascii=False))
print('   新 grid     =', json.dumps(new['grid'], ensure_ascii=False))

if not GO:
    print()
    print('★ DRY-RUN —— 未写库。加 --go 执行。')
    sys.exit(0)

s, r = req('PATCH', 'wb_report_charts?id=eq.%s' % CK,
           {'opt': new, 'up': int(time.time() * 1000)})
print()
print('%s PATCH chart_pbpe opt  %s %s' % ('✅' if s in (200, 204) else '❌', s,
                                         '' if s in (200, 204) else r))
