# -*- coding: utf-8 -*-
"""批量取数 —— 解析侧。

架构说明（重要）：
    iFinD 取数走 MCP 工具，**只能由 agent 调用**，Python 无法直连。
    因此分工是：
      * agent 按批调用 MCP，把「原始 markdown 表格」写进 build/seed/_raw_<batch>.txt
      * 本脚本读原始表格 → 解析成结构化数值 → 落 build/seed/_raw_<code>.json
      * 再由 batch_gen.py 生成 31 模块研报并推库

原始表格文件格式（_raw_<batch>.txt）：由 agent 拼接多段，每段以
    ###QUERY <market>|<query>
开头，后跟该次 MCP 返回的原始 answer 文本（含 markdown 表格）。
本脚本按 query 里的主体名单把行分配给对应股票。

用法：
    python batch_fetch.py --parse build/seed/_raw_b1.txt
    python batch_fetch.py --show 000519
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
TODO_P = os.path.join(SEED, '_todo_96.json')


# ------------------------------------------------------------------ 基础
def load_todo():
    return json.load(io.open(TODO_P, encoding='utf-8'))


def parse_cn_num(s):
    """'92.7394亿'→92.7394（亿）；'-4071.4763万'→-0.4071（亿）；'--'→None"""
    if s is None:
        return None
    s = str(s).strip().replace(',', '')
    if s in ('', '--', '-', 'N/A', 'nan', 'None'):
        return None
    mult = 1.0
    if s.endswith('万亿'):
        mult, s = 10000.0, s[:-2]
    elif s.endswith('亿'):
        mult, s = 1.0, s[:-1]
    elif s.endswith('万'):
        mult, s = 0.0001, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def split_cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def parse_md_tables(text):
    """从任意文本里抠出所有 markdown 表格 → [{'head':[...], 'rows':[...]}, ...]"""
    out = []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        l = lines[i].strip()
        if l.startswith('|') and i + 1 < len(lines) and set(lines[i + 1].strip()) <= set('|-: '):
            head = split_cells(l)
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith('|'):
                c = split_cells(lines[j])
                if len(c) < len(head):
                    c += [''] * (len(head) - len(c))
                rows.append(dict(zip(head, c[:len(head)])))
                j += 1
            out.append({'head': head, 'rows': rows})
            i = j
        else:
            i += 1
    return out


def col(row, *keys):
    """按列名关键词取列；keys 依次尝试，支持子串匹配。"""
    for k in keys:
        for c, v in row.items():
            if k in c:
                return v
    return None


def is_annual(date_str):
    return str(date_str).strip().endswith('1231')


def year_of(date_str):
    return str(date_str).strip()[:4]


def code_of(s):
    return re.sub(r'\D', '', str(s))[:6]


# ------------------------------------------------------------------ 解析各指标组
def absorb_fin(store, tables):
    """营收 / 归母净利 / 毛利率 / 净利率 / 经营现金流（年报）"""
    for t in tables:
        for r in t['rows']:
            code = code_of(col(r, '证券代码') or '')
            if not code:
                continue
            dt = col(r, '日期') or ''
            if not is_annual(dt):
                continue
            y = year_of(dt)
            e = store.setdefault(code, {})
            rev = parse_cn_num(col(r, '营业收入'))
            np_ = parse_cn_num(col(r, '归属于母公司所有者的净利润', '归母净利润'))
            gm = parse_cn_num(col(r, '销售毛利率'))
            nm = parse_cn_num(col(r, '销售净利率'))
            ocf = parse_cn_num(col(r, '经营活动产生的现金流量净额'))
            def put(key, v):
                if v is None:
                    return
                e.setdefault(key, {})[y] = v
            put('rev', rev); put('np', np_); put('gm', gm)
            put('nm', nm); put('ocf', ocf)


def absorb_ratio(store, tables):
    """ROE / ROIC / 资产负债率（年报）"""
    for t in tables:
        for r in t['rows']:
            code = code_of(col(r, '证券代码') or '')
            if not code:
                continue
            dt = col(r, '日期') or ''
            if not is_annual(dt):
                continue
            y = year_of(dt)
            e = store.setdefault(code, {})
            put = lambda k, v: (e.setdefault(k, {}).__setitem__(y, v) if v is not None else None)
            put('roe', parse_cn_num(col(r, '净资产收益率', 'ROE')))
            put('roic', parse_cn_num(col(r, '投入资本回报率', 'ROIC')))
            put('lev', parse_cn_num(col(r, '资产负债率')))
            put('eps', parse_cn_num(col(r, '每股收益', '基本每股收益')))
            put('dps', parse_cn_num(col(r, '每股股利', '每股派息', '分红')))
            put('divyield', parse_cn_num(col(r, '股息率')))


def absorb_val(store, tables):
    """最新估值：PE / PB / 市值 / 股价"""
    for t in tables:
        for r in t['rows']:
            code = code_of(col(r, '证券代码') or '')
            if not code:
                continue
            e = store.setdefault(code, {})
            for k, keys in (('pe', ('市盈率', 'PE')), ('pb', ('市净率', 'PB')),
                            ('mktcap', ('总市值',)), ('price', ('最新价', '收盘价'))):
                v = parse_cn_num(col(r, *keys))
                if v is not None:
                    e[k] = v


# ------------------------------------------------------------------ 主流程
def do_parse(path):
    txt = io.open(path, encoding='utf-8').read()
    blocks = re.split(r'^###\s*(QUERY|KIND)\b', txt, flags=re.M)
    # 组装成 [(kind, body), ...]
    segs = []
    i = 1
    while i + 1 < len(blocks):
        segs.append((blocks[i].strip(), blocks[i + 1]))
        i += 2
    print('原始文件 %s：%d 段' % (os.path.basename(path), len(segs) // 2))

    store = {}
    for kind, body in segs:
        # body 头部第一行是 kind 的描述（market|query 或 组名）
        head, _, rest = body.partition('\n')
        kindname = head.strip()
        tables = parse_md_tables(rest)
        nrow = sum(len(t['rows']) for t in tables)
        print('  [%s] %-46s 表 %d · 行 %d' % (kind, kindname[:46], len(tables), nrow))
        if kindname.startswith('FIN'):
            absorb_fin(store, tables)
        elif kindname.startswith('RATIO'):
            absorb_ratio(store, tables)
        elif kindname.startswith('VAL'):
            absorb_val(store, tables)
        elif kindname.startswith('DIV'):
            absorb_ratio(store, tables)
        else:
            absorb_fin(store, tables)
            absorb_ratio(store, tables)

    print('\n解析出 %d 只：' % len(store))
    for code in sorted(store):
        e = store[code]
        n = {k: len(v) for k, v in e.items() if isinstance(v, dict)}
        print('  %s  %s' % (code, n))
        io.open(os.path.join(SEED, '_raw_%s.json' % code), 'w', encoding='utf-8').write(
            json.dumps(e, ensure_ascii=False, indent=1))
    return store


def main():
    a = sys.argv[1:]
    if '--parse' in a:
        do_parse(a[a.index('--parse') + 1])
    elif '--show' in a:
        p = os.path.join(SEED, '_raw_%s.json' % a[a.index('--show') + 1])
        print(io.open(p, encoding='utf-8').read()[:3000])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
