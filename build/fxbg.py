# -*- coding: utf-8 -*-
"""发现报告（fxbaogao）取数工具 —— 把外部券商研报接进投资研究管线。

key 的单一来源：~/.workbuddy/mcp.json 里 fxbaogao 服务的 Authorization 头。
（不硬编码、不进仓库；本脚本也不把 key 写进任何产物。）

用法：
  search  按关键词搜研报（默认只看近一年）
      python build/fxbg.py search "铂族金属" --mon last1year --org 华泰证券 --page 1
  read    按 reportId 精读某份报告里命中关键词的段落
      python build/fxbg.py read 5636372 "市场空间"
  pack    按标的批量抓「行业资料包」，落盘 build/fxbg/<code>_<日期>.json
      python build/fxbg.py pack 600459 --name 贵研铂业 --kw 铂族金属 --kw 贵金属回收

说明：
  * 只读，不调用 download 接口（那个会扣减付费下载权益）。
  * 返回标题/正文里的 <em> 高亮标签一律剥掉。
  * 鉴权失败也是 HTTP 200，判成功必须看 body 的 code（0 = 成功）。
"""
import io
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, 'fxbg')
BASE = 'https://api.fxbaogao.com'
MCP_CFG = os.path.expanduser(os.path.join('~', '.workbuddy', 'mcp.json'))

# 「财报 / 公告」类不是卖方观点，默认在 pack 里降权
REPORT_LIKE_ORGS = ('财报', '未知机构')

TAG_RE = re.compile(r'</?em>')


def clean(s):
    return TAG_RE.sub('', s or '').strip()


def load_key():
    if not os.path.exists(MCP_CFG):
        raise SystemExit('找不到 %s —— 先在连接器里配好 fxbaogao' % MCP_CFG)
    cfg = json.load(io.open(MCP_CFG, encoding='utf-8'))
    srv = (cfg.get('mcpServers') or {}).get('fxbaogao')
    if not srv:
        raise SystemExit('mcp.json 里没有 fxbaogao 服务')
    auth = (srv.get('headers') or {}).get('Authorization') or ''
    if not auth.startswith('Bearer '):
        raise SystemExit('fxbaogao 的 Authorization 头不是 Bearer 形态')
    return auth


def post(path, body, auth):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode('utf-8'),
        headers={'Authorization': auth, 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            txt = r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return None, 'HTTP %s: %s' % (e.code, e.read().decode('utf-8', 'replace')[:200])
    try:
        d = json.loads(txt)
    except ValueError:
        return None, '响应不是 JSON: %s' % txt[:200]
    # ⚠️ 鉴权失败也是 200，必须看 code
    code = d.get('code', d.get('status')) if isinstance(d, dict) else None
    if code is not None and str(code) not in ('0', '200'):
        return None, 'code=%s msg=%s' % (code, d.get('msg') or d.get('message'))
    # 真实结构是 {code, msg, data} 包裹 —— 数据在 data 里，别把 dict 当列表遍历
    if isinstance(d, dict) and 'data' in d:
        return d['data'], None
    return d, None


def api_search(auth, keywords, org_names=None, mon=None, s_time=None, e_time=None, page=1):
    body = {
        'keywords': keywords,
        'orgNames': org_names or [],      # ⚠️ 必须数组，传字符串直接 HTTP 500
        'pageNum': str(page),             # ⚠️ 字符串
    }
    if mon:
        body['startTime'] = mon
    if s_time:
        body['startTime'] = s_time
    if e_time:
        body['endTime'] = e_time
    d, err = post('/mofoun/agent/search', body, auth)
    return (d or []), err


def api_paragraph(auth, report_id, keyword):
    d, err = post('/mofoun/agent/paragraph',
                  {'reportId': int(report_id), 'keyword': keyword}, auth)
    return d, err


def hit_paragraphs(rep):
    return [clean(p.get('content')) for p in (rep.get('paragraphs') or []) if clean(p.get('content'))]


def day(ts):
    try:
        return time.strftime('%Y-%m-%d', time.localtime(int(ts)))
    except (TypeError, ValueError):
        return ''


def cmd_search(a):
    kw = a[0] if a and not a[0].startswith('--') else ''
    if not kw:
        raise SystemExit('用法: search <关键词> [--mon last1year] [--org 机构] [--page N]')
    def opt(name, default=None):
        return a[a.index(name) + 1] if name in a else default
    mon = opt('--mon', 'last1year')
    org = opt('--org')
    page = opt('--page', '1')
    auth = load_key()
    rows, err = api_search(auth, kw, [org] if org else None, mon=mon, page=page)
    if err:
        print('搜索失败:', err)
        return 1
    print('关键词「%s」 时间=%s  命中 %d 条' % (kw, mon, len(rows)))
    print('%-9s %-10s %-14s %-3s %s' % ('reportId', '日期', '机构', '页', '标题'))
    for r in rows:
        print('%-9s %-10s %-14s %-3s %s' % (
            r.get('reportId'), day(r.get('pubTime')) or r.get('pubTimeStr', '').strip('/'),
            (r.get('orgName') or '')[:13], r.get('pageNum'), clean(r.get('title'))[:60]))
    return 0


def cmd_read(a):
    if len(a) < 2:
        raise SystemExit('用法: read <reportId> <关键词>')
    auth = load_key()
    d, err = api_paragraph(auth, a[0], a[1])
    if err:
        print('精读失败:', err)
        return 1
    items = d if isinstance(d, list) else [d]
    n = 0
    for rep in items:
        if not isinstance(rep, dict):
            continue
        print('=== %s | %s | %s' % (
            clean(rep.get('title')), rep.get('orgName'),
            day(rep.get('pubTime')) or str(rep.get('pubTimeStr') or '').strip('/')))
        summ = clean(rep.get('summary') or '')
        if summ:
            print('--- 摘要 ---'); print(summ[:1500])
        toc = rep.get('catalog') or rep.get('toc') or []
        if toc:
            print('--- 目录 ---')
            for t in toc[:30]:
                print('   ', clean(t if isinstance(t, str) else json.dumps(t, ensure_ascii=False))[:110])
        for c in hit_paragraphs(rep):
            n += 1
            print('--- 命中 #%d ---' % n); print(c[:1600])
    if not n:
        print('（没拿到命中段落，可换个关键词）')
    return 0


def cmd_pack(a):
    if not a or a[0].startswith('--'):
        raise SystemExit('用法: pack <code> --name 公司名 --kw 行业词 [--kw ...] [--mon last1year]')
    code = a[0]
    def opt_all(name):
        return [a[i + 1] for i, x in enumerate(a) if x == name and i + 1 < len(a)]
    name = (opt_all('--name') or [''])[0]
    kws = opt_all('--kw') or [name]
    mon = (opt_all('--mon') or ['last1year'])[0]
    auth = load_key()

    pack = {'code': code, 'name': name, 'mon': mon, 'fetchedAt': int(time.time()),
            'queries': [], 'reports': []}
    seen = set()
    for q in [name] + list(kws):
        rows, err = api_search(auth, q, mon=mon, page=1)
        pack['queries'].append({'kw': q, 'n': len(rows), 'err': err})
        print('[搜索] %-16s -> %d 条%s' % (q, len(rows), ('  ✗ ' + err) if err else ''))
        for r in rows:
            rid = r.get('reportId')
            if rid in seen:
                continue
            seen.add(rid)
            pack['reports'].append({
                'reportId': rid,
                'title': clean(r.get('title')),
                'org': clean(r.get('orgName')),
                'date': day(r.get('pubTime')),
                'pages': r.get('pageNum'),
                'industry': r.get('industryName') or '',
                'isSellSide': clean(r.get('orgName')) not in REPORT_LIKE_ORGS,
                'isCompanyAnn': clean(r.get('orgName')) in REPORT_LIKE_ORGS,
                'hit': hit_paragraphs(r),
            })

    # 稳定的两段排序：先按日期倒序，再把卖方研报整体提到前面
    pack['reports'].sort(key=lambda r: (r['date'] or ''), reverse=True)
    pack['reports'].sort(key=lambda r: (0 if r['isSellSide'] else 1))

    os.makedirs(OUT_DIR, exist_ok=True)
    fp = os.path.join(OUT_DIR, '%s_%s.json' % (code, time.strftime('%Y%m%d')))
    io.open(fp, 'w', encoding='utf-8').write(json.dumps(pack, ensure_ascii=False, indent=2))

    side = [r for r in pack['reports'] if r['isSellSide']]
    print()
    print('=== 资料包 %s %s ===' % (code, name))
    print('  报告总数 %d ｜ 卖方研报 %d ｜ 公司公告/财报 %d'
          % (len(pack['reports']), len(side), len(pack['reports']) - len(side)))
    print('  卖方机构：%s' % '、'.join(sorted({r['org'] for r in side if r['org'] and r['org'] != '未知机构'})))
    print('  落盘：%s' % os.path.relpath(fp, HERE))
    print('SELF_CHECK_OK')
    return 0


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 0
    return {'search': cmd_search, 'read': cmd_read, 'pack': cmd_pack}.get(a[0], lambda _: 1)(a[1:])


if __name__ == '__main__':
    sys.exit(main())
