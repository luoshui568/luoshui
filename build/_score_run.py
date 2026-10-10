# -*- coding: utf-8 -*-
"""槽 29 自动评分 —— **原料抽取 + 引擎调用**（干跑/落盘两用）

用法：
    python _score_run.py                 # 干跑，只打决策表
    python _score_run.py 002408          # 只看某几家
    python _score_run.py --json          # 额外输出 _score_out.json

数据源：
    _score_src/<code>.json          线上报告模块（真身，本地 seed 存量家已陈旧）
    _score_src/<code>_charts.json   线上图表 option（产品价格序列）
    _score_market/<code>.json       行情底数（月线派生，见 _score_market.py）
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_engine as SE   # noqa: E402

SRC = os.path.join(HERE, '_score_src')
MKT = os.path.join(HERE, '_score_market')

ALL = ['600456', '600459', '002237', '000731', '000830',
       '603977', '601118', '601958', '603599', '002408']


# ───────────────────────────────────────────────────────────── 基础工具
def clean(x):
    x = re.sub(r'<[^>]+>', ' ', str(x or ''))
    x = x.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    x = x.replace('&nbsp;', ' ').replace('&#39;', "'")
    # ★ 源数据（尤其搬家来的正文）带 markdown 粗体标记，直接抄进 sc-note
    #   会在页面上露出字面 `**`（如 002408 的第一大股东比例）。
    x = x.replace('**', '').replace('__', '')
    return re.sub(r'\s+', ' ', x).strip()


def load(code):
    mods = json.loads(io.open(os.path.join(SRC, '%s.json' % code),
                              encoding='utf-8').read())['mods']
    cp = os.path.join(SRC, '%s_charts.json' % code)
    charts = {}
    if os.path.exists(cp):
        for c in json.loads(io.open(cp, encoding='utf-8').read()):
            charts[c['id']] = c.get('opt')
    return mods, charts


def find_mod(mods, *keys):
    for m in mods:
        t = clean(m.get('title'))
        if any(k in t for k in keys):
            return m
    return None


def tables(html):
    out = []
    for tb in re.findall(r'<table.*?</table>', html or '', re.S):
        out.append([[clean(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S)]
                    for r in re.findall(r'<tr.*?</tr>', tb, re.S)])
    return out


def num(x):
    m = re.search(r'[-+]?\d+(?:\.\d+)?', str(x or '').replace(',', '').replace('−', '-'))
    return float(m.group(0)) if m else None


# ─────────────────────────────────────────────────────────── 七项抽取器
def ex_owner(mods):
    """实控人抽取。

    ★ 只认「项目|内容」型信息表，**跳过缺口表**——否则会抽到
      「待取路径」列里的文本（601958 曾抽成「陕西省国资委出资企业名录 / …」）。
    ★ 600456（母本）槽 4 无表格、只有段落 ⇒ 段落兜底。
    """
    m = find_mod(mods, '实控人')
    if not m:
        return {}
    val = kind = desc = ''
    for t in tables(m.get('html')):
        head = ' '.join(t[0]) if t else ''
        if '项目' not in head or '内容' not in head:
            continue
        for row in t[1:]:
            for i, c in enumerate(row):
                if '实际控制人' in c and i + 1 < len(row) and not val:
                    val = row[i + 1]
                    for j in range(i + 2, len(row) - 1):
                        if '性质' in row[j] and not kind:
                            kind = row[j + 1]
                if '控股股东' in c and i + 1 < len(row) and not desc:
                    desc = row[i + 1]
    if not val:                                   # 无表格 ⇒ 段落兜底
        txt = clean(m.get('html'))
        mm = re.search(r'([\u4e00-\u9fa5]{2,24}(?:国务院|省|市)[\u4e00-\u9fa5]{0,24}'
                       r'(?:人民政府|国有资产监督管理委员会|国资委))'
                       r'[^。；]{0,12}为最终实际控制人', txt)
        if mm:
            val = mm.group(1)
        else:
            mm = re.search(r'最终控制人为([\u4e00-\u9fa5]{4,30})', txt)
            if mm:
                val = mm.group(1)
    # 国资类型判定 —— ★ 先判「非国有/自然人」，否则性质栏里那句
    #   「控股股东为境内**非国有**法人」会把自然人实控人误判成国资（603599 踩过）。
    blob = val + ' ' + kind
    if '非国有' in blob or '自然人' in blob:
        k = '自然人/民营'
    elif '国务院' in blob:
        k = '国务院国资委'
    elif '省人民政府' in blob or '省属' in blob or ('省' in blob and '国资' in blob):
        k = '省属国资'
    elif ('市' in blob or '县' in blob) and ('国资' in blob or '人民政府' in blob):
        k = '市属国资'
    elif '国资' in blob or '国有' in blob:
        k = '国有（未注明层级）'
    else:
        k = val or '未知'
    return {'kind': k, 'desc': desc or '', 'raw': val, 'nature': kind}


def ex_moat(mods):
    m = find_mod(mods, '护城河')
    if not m:
        return {}
    ns = nw = nm_ = 0
    names = []
    ev = ''
    for t in tables(m.get('html')):
        head = ' '.join(t[0]) if t else ''
        if '强度' not in head:
            continue
        ci = next((i for i, c in enumerate(t[0]) if '强度' in c), 1)
        ni = 0
        for row in t[1:]:
            if len(row) <= ci:
                continue
            v = row[ci]
            if v.startswith('强'):
                ns += 1
                names.append(row[ni] if row else '')
            elif v.startswith('弱'):
                nw += 1
            elif v.startswith('中'):
                nm_ += 1
    blob = clean(m.get('html'))
    uniq = [w for w in ('唯一', '全球第一', '国内第一', '龙头', '垄断', '独家', '最大')
            if w in blob]
    if names:
        # ★ 只列前 3 项时要标「等」—— 否则「强 4 项（A、B、C）」会数不上。
        ev = '壁垒强度：强 %d 项（%s%s）' % (ns, '、'.join(names[:3]),
                                          '等' if len(names) > 3 else '')
    return {'n_strong': ns, 'n_weak': nw, 'n_mid': nm_,
            'unique_words': uniq, 'evidence': ev}


def _ym(s):
    m = re.match(r'^(\d{4})-(\d{2})', str(s or ''))
    return (int(m.group(1)), int(m.group(2))) if m else None


def ex_price(charts):
    o = None
    for cid, opt in charts.items():
        if 'ResPrice' in cid or 'TiPrice' in cid:
            o = opt
            break
    if not isinstance(o, dict):
        return {}
    xa = o.get('xAxis')
    xd = (xa.get('data') if isinstance(xa, dict) else xa) or []
    ser = (o.get('series') or [{}])[0]
    vals = ser.get('data') or []
    name = (ser.get('name') or '核心产品').split('（')[0]
    pairs = [(x, v) for x, v in zip(xd, vals) if v is not None]
    if len(pairs) < 2:
        return {'name': name}
    (lx, lv), (fx, fv) = pairs[-1], pairs[0]
    yoy = prev_label = None
    note_caliber = ''
    ly, lm = _ym(lx) or (None, None)
    if ly:
        # 精确同比：找 12 个月前的同月
        for x, v in pairs[:-1]:
            y2 = _ym(x)
            if y2 and y2 == (ly - 1, lm):
                yoy = (lv / v - 1) * 100
                prev_label = '%s %s' % (x, SE._fmt(v))
                break
        if yoy is None:
            sx = _ym(fx)
            span = ((_ym(lx)[0] - sx[0]) * 12 + (_ym(lx)[1] - sx[1])) if sx else None
            note_caliber = ('序列仅覆盖约 %d 个月、按首末值比较' % span) if span \
                else '按首末值比较'
    else:
        # 文字轴（如「2025 年（全年均价）」「2026-08（最新报价）」）
        note_caliber = '口径：最新值与首期值比较'
    if yoy is None:
        yoy = (lv / fv - 1) * 100 if fv else None
        prev_label = prev_label or '%s %s' % (fx, SE._fmt(fv))
    # ★ `%.4g` 会把 14,420 打成 `1.442e+04`（四位数报价必踩），统一走 SE._fmt。
    return {'name': name, 'yoy': yoy, 'last': SE._fmt(lv), 'prev': prev_label,
            'caliber': note_caliber, 'last_label': str(lx)}


def ex_profit(mods, report_year=None):
    """归母净利年度序列。

    ★ 两个坑：① 000731 的表**没有归母同比列**（只有营收同比）⇒ 自算同比；
              ② 000830 的表把 2026H1 也塞进「年度」列 ⇒ 按报告年份剔除当年行。
    """
    m = find_mod(mods, '营业收入与利润')
    if not m:
        return {}
    for t in tables(m.get('html')):
        if not t:
            continue
        head = t[0]
        ci = next((i for i, c in enumerate(head)
                   if '归母净利' in c or ('净利润' in c and '扣非' not in c)), None)
        if ci is None:
            continue
        yi = next((i for i in range(ci + 1, len(head)) if '同比' in head[i]), None)
        ser, prev = [], None
        for row in t[1:]:
            if len(row) <= ci:
                continue
            y = num(row[0])
            if y is None or y < 1990:
                continue
            if report_year and y >= report_year:       # 当年行（H1 口径）不进年度序列
                prev = None
                continue
            v = num(row[ci])
            yoy = num(row[yi]) if (yi is not None and yi < len(row)) else None
            if yoy is None and v is not None and prev is not None and prev > 0:
                yoy = (v / prev - 1) * 100             # 自算同比
            ser.append({'y': str(int(y)), 'val': v, 'yoy': yoy})
            prev = v
        if ser:
            return {'basis': '归母', 'series': ser}
    return {}


def ex_focus(mods):
    """主营集中度 + 板块数。

    ★ 板块数只数「占比 ≥ 3%」的，避免把「其他/其他业务」这种零头算成一个板块
      （601958 曾因此被算成 5 个板块、白白降档）。
    """
    m = find_mod(mods, '产品收入与毛利结构')
    if not m:
        return {}
    for t in tables(m.get('html')):
        if not t:
            continue
        head = t[0]
        pi = next((i for i, c in enumerate(head)
                   if ('占比' in c or '收入占比' in c) and '毛利' not in c), None)
        if pi is None:
            continue
        rows = [r for r in t[1:]
                if len(r) > pi and '合计' not in r[0] and num(r[pi]) is not None]
        if not rows:
            continue
        top = rows[0]
        big = [r for r in rows if (num(r[pi]) or 0) >= 3]
        return {'top_name': top[0], 'top_pct': num(top[pi]),
                'n_seg': len(big) or len(rows),
                'extra': ('第二板块 %s 占 %s' % (rows[1][0], rows[1][pi])) if len(rows) > 1 else ''}
    return {}


def ex_mktcap(mods):
    m = find_mod(mods, '企业评分')
    if not m:
        return {}
    h = m.get('html') or ''
    kv = re.findall(r'<div class="k">(.*?)</div>\s*<div class="v"[^>]*>(.*?)</div>', h, re.S)
    d = {clean(a): clean(b) for a, b in kv}
    mv = num(list(d.values())[0]) if d else None
    date = ''
    for k, v in d.items():
        if '日期' in k:
            date = v
    return {'mktcap': mv, 'date': date, 'kpi': d}


# ───────────────────────────────────────────────────────────── 主流程
def extract(code):
    mods, charts = load(code)
    mk = ex_mktcap(mods)
    ry = None
    if mk.get('date'):
        m = re.match(r'(\d{4})', str(mk['date']))
        ry = int(m.group(1)) if m else None
    ctx = {
        'owner': ex_owner(mods),
        'moat': ex_moat(mods),
        'price': ex_price(charts),
        'profit': ex_profit(mods, report_year=ry),
        'focus': ex_focus(mods),
        'mktcap': mk,
    }
    mp = os.path.join(MKT, '%s.json' % code)
    ctx['market'] = json.loads(io.open(mp, encoding='utf-8').read()) \
        if os.path.exists(mp) else {}
    ctx['_meta'] = {'code': code, 'has_market': bool(ctx['market']),
                    'report_year': ry}
    return ctx


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    want_json = '--json' in sys.argv
    codes = args or ALL
    out = {}
    for code in codes:
        ctx = extract(code)
        r = SE.score(ctx)
        out[code] = {'ctx': ctx, 'result': r, 'name': ''}
        print('=' * 78)
        print('### %s' % code)
        # 原料
        o = ctx['owner']
        print('  原料①股东  : kind=%s | %s' % (o.get('kind'), o.get('raw')))
        print('            desc=%s' % (o.get('desc') or '')[:80])
        mo = ctx['moat']
        print('  原料②护城河: 强%d 中%d 弱%d | 关键词 %s'
              % (mo.get('n_strong', 0), mo.get('n_mid', 0), mo.get('n_weak', 0),
                 mo.get('unique_words')))
        pr = ctx['price']
        print('  原料③价格  : %s yoy=%s (%s → %s) %s'
              % (pr.get('name'), ('%+.1f%%' % pr['yoy']) if pr.get('yoy') is not None else None,
                 pr.get('prev'), pr.get('last'), pr.get('caliber') or ''))
        pf = ctx['profit']
        print('  原料④净利  : basis=%s 序列 %s'
              % (pf.get('basis'), [(x['y'], x['val'], x['yoy'])
                                   for x in (pf.get('series') or [])]))
        fo = ctx['focus']
        print('  原料⑤⑥主营: top=%s %.2f%% seg=%d'
              % (fo.get('top_name'), fo.get('top_pct') or 0, fo.get('n_seg') or 0))
        mk = ctx['mktcap']
        print('  原料⑦市值  : %s (%s)' % (mk.get('mktcap'), mk.get('date')))
        print('  原料⑧⑨⑩行情: %s' % ('已取' if ctx['market'] else '**缺**'))
        # 结果
        print('  --- 打分 ---')
        for i, (s, n) in enumerate(zip(r['scores'], r['notes'])):
            print('   %2d %-20s %2d  %s' % (i + 1, SE.ITEMS[i][0], s, n))
        print('  >>> 加权总分 %.1f  评级 %s' % (r['total'], r['rating']))
    print()
    print('完成 %d 家' % len(codes))
    if want_json:
        io.open(os.path.join(HERE, '_score_out.json'), 'w', encoding='utf-8') \
            .write(json.dumps(out, ensure_ascii=False, indent=1))
        print('已写 _score_out.json')


if __name__ == '__main__':
    main()
