# -*- coding: utf-8 -*-
"""把 pptx_*.json 打印成可读摘要（分页），用于撰写研报。

用法： python build/pptx_digest.py 000830 [起始页] [结束页]
"""
import io
import json
import os
import re
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')


def brief(v, n=90):
    s = str(v).replace('\n', ' / ')
    return s if len(s) <= n else s[:n] + '…'


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else '000830'
    a = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    b = int(sys.argv[3]) if len(sys.argv) > 3 else 999
    j = json.load(io.open(os.path.join(SRC, 'pptx_%s.json' % code), encoding='utf-8'))
    print('### %s %s  ·  %s  ·  共 %d 页' % (code, j['name'], j['src'], len(j['slides'])))
    print()
    for sl in j['slides']:
        p = sl['page']
        if p < a or p > b:
            continue
        print('=' * 78)
        print('### 第 %d 页' % p)
        for it in sl['items']:
            if 'text' in it:
                t = it['text']
                if t.strip():
                    print('  [文] ' + brief(t, 600))
            if 'table' in it:
                print('  [表] %d 行：' % len(it['table']))
                for r in it['table']:
                    print('       | ' + ' | '.join(brief(c, 26) for c in r))
            if 'chart' in it:
                c = it['chart']
                print('  [图] %s' % c.get('chart_type'))
                if c.get('title'):
                    print('       标题: ' + brief(c['title'], 80))
                cats = c.get('categories')
                if cats:
                    print('       类目(%d): %s' % (len(cats), brief(cats, 260)))
                for s in c.get('series', []):
                    vals = s.get('values') or []
                    print('       %s(%d): %s' % (brief(s.get('name'), 34), len(vals), brief(vals, 260)))
        print()


if __name__ == '__main__':
    main()
