# -*- coding: utf-8 -*-
"""把新构建的 EPS×收盘价 双轴图 opt 写进 wb_report_charts.id = 600456_chart_eps

★ 该表既无 is_del、也不在删除 RPC 白名单里 ⇒ **图表行删不掉，只能原地更新**。
  所以第一步必须留快照，写坏了只能靠快照回退。

用法：
  python build/set_600456_chart_eps.py          # 干跑（只比对，不写）
  python build/set_600456_chart_eps.py --go     # 写库 + 回读复核
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.loads(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8').read())
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
H = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json'}

ROW_ID = '600456_chart_eps'
NEW_OPT = os.path.join(HERE, 'seed', '_eps_opt_600456.json')
BAKDIR = os.path.join(HERE, 'backup')


def req(q, method='GET', body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(REST + q, data=data, method=method, headers=H)
    with urllib.request.urlopen(r, timeout=90) as resp:
        t = resp.read().decode('utf-8')
        return json.loads(t) if t.strip() else None


def canon(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True)


def main():
    go = '--go' in sys.argv
    new = json.loads(io.open(NEW_OPT, encoding='utf-8').read())
    cur = req('wb_report_charts?id=eq.%s&select=id,report_id,code,seq,name,opt,up' % ROW_ID)
    if not cur:
        print('★ 目标行不存在：%s' % ROW_ID)
        return 1
    cur = cur[0]
    old = cur['opt']
    if isinstance(old, str):
        old = json.loads(old)

    print('目标行 %s  seq=%s  name=%s  up=%s' % (cur['id'], cur['seq'], cur['name'], cur['up']))
    print('旧 opt  %8.1f KB  系列 %s'
          % (len(canon(old).encode('utf-8')) / 1024.0,
             [(s.get('name'), s.get('type'), len(s.get('data') or [])) for s in (old.get('series') or [])]))
    print('新 opt  %8.1f KB  系列 %s'
          % (len(canon(new).encode('utf-8')) / 1024.0,
             [(s.get('name'), s.get('type'), len(s.get('data') or [])) for s in new['series']]))
    print('旧 xAxis: %s' % canon(old.get('xAxis'))[:150])

    if not go:
        print('\n[干跑] 未写库。加 --go 执行。')
        return 0

    # ---------- 备份（唯一回退凭据）----------
    os.makedirs(BAKDIR, exist_ok=True)
    ts = time.strftime('%Y%m%d-%H%M%S')
    bak = os.path.join(BAKDIR, '600456_chart_eps_pre_%s.json' % ts)
    io.open(bak, 'w', encoding='utf-8').write(
        json.dumps({'at': int(time.time() * 1000), 'row': cur}, ensure_ascii=False))
    print('\n快照 → %s（%d B）' % (os.path.basename(bak), os.path.getsize(bak)))

    # ---------- 写 ----------
    now = int(time.time() * 1000)
    try:
        req('wb_report_charts?id=eq.%s' % ROW_ID, 'PATCH', {'opt': new, 'up': now})
        print('  ✔ PATCH %s  up=%d' % (ROW_ID, now))
    except urllib.error.HTTPError as e:
        print('  ✖ PATCH 失败：HTTP %s %s' % (e.code, e.read()[:400]))
        return 1

    # ---------- 回读复核（比解析后的 dict，不比 md5 —— jsonb 往返会重排键序）----------
    time.sleep(1.5)
    got = req('wb_report_charts?id=eq.%s&select=opt,up' % ROW_ID)[0]
    g = got['opt']
    if isinstance(g, str):
        g = json.loads(g)
    same = canon(new) == canon(g)
    print('\n回读复核：%s   up=%s' % ('逐字段一致 ✅' if same else '★ 不一致 ❌', got['up']))
    if not same:
        a, b = canon(new), canon(g)
        for i in range(min(len(a), len(b))):
            if a[i] != b[i]:
                print('  首个差异 @%d：期望 …%s… 实际 …%s…' % (i, a[max(0, i - 50):i + 50], b[max(0, i - 50):i + 50]))
                break
        else:
            print('  长度不同：期望 %d / 实际 %d' % (len(a), len(b)))
        return 1

    # 关键字段抽查
    s1 = g['series'][1]
    print('  系列1 名=%s  点数=%d  首=%s  末=%s'
          % (s1['name'], len(s1['data']), s1['data'][0], s1['data'][-1]))
    s0 = g['series'][0]
    print('  系列0 名=%s  点数=%d  首=%s  末=%s'
          % (s0['name'], len(s0['data']), s0['data'][0], s0['data'][-1]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
