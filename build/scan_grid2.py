# -*- coding: utf-8 -*-
"""扫描全库 .grid2 结构，复刻 stackWide() 判据，评估「全是图 → 保持并排」的影响面。
只读，不写库。"""
import json, io, re, os, urllib.request, urllib.parse

BUILD = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(io.open(os.path.join(BUILD, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest' % cfg['envId']
KEY = cfg['key']


def req(path):
    url = BASE + '/' + path
    r = urllib.request.Request(url, headers={
        'apikey': KEY, 'Authorization': 'Bearer ' + KEY,
        'Accept': 'application/json'})
    with urllib.request.urlopen(r, timeout=60) as f:
        return json.loads(f.read().decode('utf-8'))


def page_all(table, select='*', order='id.asc'):
    out, off, step = [], 0, 1000
    while True:
        chunk = req('%s?select=%s&order=%s&limit=%d&offset=%d'
                    % (table, urllib.parse.quote(select), order, step, off))
        out += chunk
        if len(chunk) < step:
            break
        off += step
    return out


TOK = re.compile(r'<div\b[^>]*>|</div>', re.I)


def build_tree(html):
    """把 div 序列解析成带原始片段 raw 的树（raw 含开标签本身）。"""
    h = html or ''
    root = {'cls': '__root__', 'raw': h, 'kids': []}
    stack, starts = [root], [0]
    for mt in TOK.finditer(h):
        t = mt.group(0)
        if t.lower().startswith('</'):
            if len(stack) > 1:
                node = stack.pop()
                node['raw'] = h[starts[-1]:mt.end()]
                starts.pop()
        else:
            c = re.search(r'class="([^"]*)"', t)
            node = {'cls': c.group(1) if c else '', 'raw': '', 'kids': [], 'open': t}
            stack[-1]['kids'].append(node)
            stack.append(node)
            starts.append(mt.start())
    while len(stack) > 1:                 # 未闭合的兜底
        node = stack.pop()
        node['raw'] = h[starts.pop():]
    return root


def has_vis(node):
    """严格复刻 stackWide 判据 k.querySelector('table,[data-chart],canvas,svg')。
    ⚠️ querySelector 只看**后代**、不看元素自身 ⇒ 先把自身开标签剥掉再判。
    实测影响：m23 的 data-chart 挂在子块的孙 div 上 → 算 vis；
    若某子块自己就是 [data-chart]（内部空旷）则**不算** vis。"""
    blob = re.sub(r'^\s*<div\b[^>]*>', '', node['raw'], count=1, flags=re.I)
    return bool(re.search(r'<table\b|data-chart\s*=|</?canvas\b|<svg\b', blob, re.I))


def walk_grid2(node, out):
    for k in node['kids']:
        if 'grid2' in (k['cls'] or '').split():
            out.append(k)
        walk_grid2(k, out)


reps = page_all('wb_reports', 'id,code,name,toc')
mods = page_all('wb_report_mods', 'id,code,no,seq,title,html')
print('研报 %d 份 · 模块 %d 条\n' % (len(reps), len(mods)))

by = {}
for m in mods:
    by.setdefault(m.get('code'), []).append(m)

GRAND = {'g2': 0, 'vis': 0, 'allchart': 0, 'mixed': 0, 'puretext': 0}
for rep in sorted(reps, key=lambda r: str(r.get('code') or '')):
    code = rep.get('code')
    ms = sorted(by.get(code, []),
                key=lambda x: int(x['no']) if str(x.get('no') or '').isdigit() else 0)
    stat = {'g2': 0, 'vis': 0, 'allchart': 0, 'mixed': 0, 'puretext': 0}
    lines = []
    for m in ms:
        root = build_tree(m.get('html') or '')
        gs = []
        walk_grid2(root, gs)
        for g in gs:
            subs = [k for k in g['kids'] if k['cls'] is not None]
            vis = [k for k in subs if has_vis(k)]
            txt = [k for k in subs if not has_vis(k)]
            nch = len(re.findall(r'data-chart\s*=', g['raw'], re.I))
            has_tbl = bool(re.search(r'<table\b', g['raw'], re.I))
            stat['g2'] += 1
            if not vis:
                stat['puretext'] += 1
                tag = '纯文字 → 保持两栏'
            else:
                stat['vis'] += 1
                if len(vis) == 2 and not txt and not has_tbl:
                    stat['allchart'] += 1
                    tag = '★两子块全是图(无表无文字) → 建议并排'
                else:
                    stat['mixed'] += 1
                    tag = '含表/含文字 → 保持整行'
            lines.append('    m%-3s %-18s 子块=%d 图=%d 表=%s 文字子块=%d | %s'
                         % (m.get('no'), (m.get('title') or '')[:16], len(subs),
                            nch, 'Y' if has_tbl else '-', len(txt), tag))
    print('【%s】%-26s 模块%2d | grid2=%d  全是图=%d  混合=%d  纯文字=%d'
          % (code, (rep.get('name') or '')[:24], len(ms),
             stat['g2'], stat['allchart'], stat['mixed'], stat['puretext']))
    for l in lines:
        print(l)
    print()
    for k in GRAND:
        GRAND[k] += stat[k]

print('=' * 70)
print('全库合计： grid2 = %d 处' % GRAND['g2'])
print('  ★全是图（建议并排） : %d 处' % GRAND['allchart'])
print('  混合（表或文字+图）  : %d 处  → 维持整行' % GRAND['mixed'])
print('  纯文字（维持两栏）   : %d 处' % GRAND['puretext'])
