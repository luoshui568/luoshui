# -*- coding: utf-8 -*-
"""探测公开行情接口能否被服务端直连调用（云函数方案的前提）

目标：一次请求拿到尽量多的字段，用于 wb_stocks 的每日自动更新。
"""
import json
import urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}


def get(url, decode='gbk'):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode(decode, 'ignore')


def probe_snapshot():
    print('=' * 70)
    print('[1] 腾讯实时行情快照  qt.gtimg.cn')
    print('=' * 70)
    codes = 'sh600459,sz000833,sz002317,sh601600,sh600547'
    txt = get('https://qt.gtimg.cn/q=' + codes)
    for line in txt.strip().split('\n'):
        if not line.strip():
            continue
        head, _, payload = line.partition('=')
        vals = payload.strip().strip(';').strip('"').split('~')
        print('\n---', head.strip().replace('v_', ''), '共', len(vals), '个字段 ---')
        # 关键索引
        marks = {
            1: '名称', 2: '代码', 3: '现价', 4: '昨收', 5: '今开',
            6: '成交量(手)', 31: '涨跌', 32: '涨跌%', 33: '最高', 34: '最低',
            36: '成交量', 37: '成交额(万)', 38: '换手率', 39: 'PE(TTM)',
            43: '振幅', 44: '流通市值(亿)', 45: '总市值(亿)', 46: 'PB',
            47: '涨停', 48: '跌停', 49: '量比', 51: '均价',
            52: 'PE(动)', 53: 'PE(静)',
        }
        for i in sorted(marks):
            if i < len(vals):
                print('   [%2d] %-12s = %s' % (i, marks[i], vals[i]))
        # 打印全部，供寻找股息率等其他字段
        print('   RAW:', '~'.join('%d:%s' % (i, v) for i, v in enumerate(vals) if v))


def probe_kline():
    print()
    print('=' * 70)
    print('[2] 日K线（用于算 10/20/60 日涨幅与年初至今）')
    print('=' * 70)
    url = ('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
           '?param=sh600459,day,,,70,qfq')
    txt = get(url, 'utf-8')
    try:
        j = json.loads(txt)
        d = j.get('data', {}).get('sh600459', {})
        k = d.get('qfqday') or d.get('day') or []
        print('拿到 %d 根日K' % len(k))
        if k:
            print('  最早:', k[0])
            print('  最新:', k[-1])
            print('  字段顺序猜测: [日期, 开, 收, 高, 低, 成交量, ...]')
    except Exception as e:
        print('解析失败:', e)
        print(txt[:400])


def probe_yearstart():
    print()
    print('=' * 70)
    print('[3] 年初价格（算 年初至今%）')
    print('=' * 70)
    url = ('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
           '?param=sh600459,day,2026-01-01,2026-01-10,10,qfq')
    txt = get(url, 'utf-8')
    try:
        j = json.loads(txt)
        d = j.get('data', {}).get('sh600459', {})
        k = d.get('qfqday') or d.get('day') or []
        print('年初区间拿到 %d 根' % len(k))
        for r in k[:3]:
            print('  ', r[:6])
    except Exception as e:
        print('解析失败:', e, txt[:300])


def probe_batch_limit():
    print()
    print('=' * 70)
    print('[4] 单次请求能带多少只（批量上限）')
    print('=' * 70)
    # 用一批真实代码测试 80 只是否一次拿全
    codes = [
        'sh600459', 'sz000833', 'sz002317', 'sh601600', 'sh600547',
        'sz000630', 'sh601168', 'sh603993', 'sz000807', 'sz000831',
    ]
    txt = get('https://qt.gtimg.cn/q=' + ','.join(codes))
    got = [l for l in txt.strip().split('\n') if '="' in l and len(l.split('~')) > 10]
    print('请求 %d 只，返回有效 %d 只' % (len(codes), len(got)))
    # 再造 100 只代码试试
    big = []
    for i in range(100):
        big.append('sh600%03d' % (100 + i))
    txt2 = get('https://qt.gtimg.cn/q=' + ','.join(big))
    got2 = [l for l in txt2.strip().split('\n') if len(l.split('~')) > 10]
    print('请求 100 只，返回有效 %d 只' % len(got2))


if __name__ == '__main__':
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        probe_snapshot()
        probe_kline()
        probe_yearstart()
        probe_batch_limit()
    out = buf.getvalue()
    with open('_probe_out.txt', 'w', encoding='utf-8') as f:
        f.write(out)
    print('written', len(out))
