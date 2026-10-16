# -*- coding: utf-8 -*-
"""修正研报里「数据区间 …（10 年）」的年份数错误（2026-10-14 用户截图指出）。

★ 病根：`report_build_v31.py` 把年数**写死成 10 年**，而实际取到的 iFinD 年度序列
  是 2021~2025 共 5 个年度 ⇒ 徽标、报告说明、一句话本质三处都跟着错。
  截图上「数据区间 2021~2025（10 年）」一眼就不对（用户圈的就是这里）。

★ 做法：**从徽标里的年份区间反推真实年数**，不去猜、不写死；三处文案一起改：
   ① badges    `数据区间 2021~2025（10 年）`        → `（5 年）`
   ② notice    `财务数据为 10 年序列（2021~2025…`   → `5 年序列`
   ③ essence   `过去十年赚了多少钱` / `10 年实测`    → `过去五年` / `5 年实测`
  中文数字（五 / 十）也一并按年数生成，免得写成「过去 5 年」半中半洋。

★ 幂等：按真实年数写入，重复跑结果不变。只动「年数」这一个数字，
  正文一个字不改。

用法：
    python3 build/fix_span_year.py --dry     # 只打印将要改什么
    python3 build/fix_span_year.py           # 写库
    python3 build/fix_span_year.py --check   # 回读校验
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'],
       'Content-Type': 'application/json',
       'Prefer': 'return=minimal'}

CN = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八',
      9: '九', 10: '十', 11: '十一', 12: '十二', 13: '十三', 14: '十四', 15: '十五'}

SPAN_RE = re.compile(r'数据区间\s*(\d{4})\s*[~～\-—]\s*(\d{4})')
COUNT_RE = re.compile(r'（\s*\d+\s*年\s*）')
NOTE_RE = re.compile(r'(财务数据为\s*)(\d+)\s*年序列')
ESS_CN_RE = re.compile(r'过去(十|\d+)\s*年')
ESS_NUM_RE = re.compile(r'(\d+)\s*年实测')


def cn(n):
    return CN.get(n, str(n))


def req(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(REST + path, data=data, headers=HDR, method=method)
    with urllib.request.urlopen(r, timeout=180) as resp:
        raw = resp.read().decode('utf-8', 'replace')
        return json.loads(raw) if raw.strip() else None


def fix_badges(badges):
    """返回 (新年数字, 新 badges)；没有区间徽标则返回 (None, 原值)"""
    if not isinstance(badges, list):
        return None, badges
    n = None
    for b in badges:
        m = SPAN_RE.search(b or '')
        if m:
            n = int(m.group(2)) - int(m.group(1)) + 1
            break
    if not n:
        return None, badges
    out = []
    for b in badges:
        out.append(COUNT_RE.sub('（%d 年）' % n, b) if SPAN_RE.search(b or '') else b)
    return n, out


def fix_text(s, n):
    """把说明/本质里的年数改成 n（中文数字 + 阿拉伯数字都覆盖）。
    返回**字符串**（None 归一成 ''），免得 None != '' 被误判成「有改动」。"""
    if not s:
        return ''
    s = NOTE_RE.sub(lambda m: '%s%d 年序列' % (m.group(1), n), s)
    s = ESS_CN_RE.sub(lambda m: '过去%s年' % cn(n), s)
    s = ESS_NUM_RE.sub(lambda m: '%d 年实测' % n, s)
    return s


def main():
    mode = 'apply'
    if '--dry' in sys.argv:
        mode = 'dry'
    elif '--check' in sys.argv:
        mode = 'check'

    rows = req('GET', 'wb_reports?select=id,code,name,badges,notice_html,essence_html'
                      '&order=code.asc')
    print('=' * 96)
    print('「数据区间 10 年」年份修正 · %s' % ('试运行' if mode == 'dry' else
                                        '回读校验' if mode == 'check' else '写入'))
    print('=' * 96)
    changed = 0
    for r in rows:
        n, badges = fix_badges(r.get('badges') or [])
        if not n:
            continue
        code = r['code']
        notice = fix_text(r.get('notice_html'), n)
        ess = fix_text(r.get('essence_html'), n)
        hits = []
        if badges != (r.get('badges') or []):
            hits.append('徽标')
        if notice != (r.get('notice_html') or ''):
            hits.append('报告说明')
        if ess != (r.get('essence_html') or ''):
            hits.append('一句话本质')

        if mode == 'check':
            wrong = []
            if any(re.search(r'（\d+ 年）', b or '') and
                   int(re.search(r'（(\d+) 年）', b).group(1)) != n
                   for b in (r.get('badges') or []) if SPAN_RE.search(b or '')):
                wrong.append('徽标')
            if re.search(r'财务数据为\s*(?!%d\b)\d+\s*年序列' % n, r.get('notice_html') or ''):
                wrong.append('报告说明')
            if re.search(r'过去(?!%s年)十?\d*年' % cn(n), r.get('essence_html') or ''):
                wrong.append('一句话本质')
            print('%-8s %-8s 真实年数=%d  %s'
                  % (code, (r.get('name') or '')[:8], n,
                     '✅ 已一致' if not wrong else '❌ 仍不对：' + '、'.join(wrong)))
            continue

        if not hits:
            continue
        print('%-8s %-8s 真实年数=%d  待改：%s' % (code, (r.get('name') or '')[:8], n,
                                                  '、'.join(hits)))
        for b in (badges if '徽标' in hits else []):
            if SPAN_RE.search(b or ''):
                print('     徽标 → %s' % b[-46:])
        if '报告说明' in hits:
            m = NOTE_RE.search(r.get('notice_html') or '')
            if m:
                print('     说明 → %s%d 年序列（原：%s）' % (m.group(1), n, m.group(0).strip()))
        if '一句话本质' in hits:
            for m in ESS_CN_RE.finditer(r.get('essence_html') or ''):
                print('     本质 → 过去%s年' % cn(n))
            for m in ESS_NUM_RE.finditer(r.get('essence_html') or ''):
                print('     本质 → %d 年实测' % n)

        if mode == 'dry':
            continue

        body = {}
        if '徽标' in hits:
            body['badges'] = badges
        if '报告说明' in hits:
            body['notice_html'] = notice
        if '一句话本质' in hits:
            body['essence_html'] = ess
        req('PATCH', 'wb_reports?id=eq.%s' % r['id'], body)
        changed += 1
    if mode != 'check':
        print('-' * 96)
        print('%s %d 份' % ('试运行结束，未写库：' if mode == 'dry' else '已写入：', changed))
    return 0


if __name__ == '__main__':
    sys.exit(main())
