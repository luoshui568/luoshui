# -*- coding: utf-8 -*-
"""生成本地图表预览页（内联 report.html 里的 ECharts + report_theme.css + 模块 8 正文），
   用于截图目视核对新图表。"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
BUILD = os.path.join(BASE, 'build')
REPORT = os.path.join(BASE, 'deploy', 'report.html')

html = io.open(REPORT, encoding='utf-8').read()
opens = [m.start() for m in re.finditer(r'<script[^>]*>', html)]
closes = [m.start() for m in re.finditer(r'</script>', html)]
print('script opens', opens)
print('script closes', closes)

# 第 2 个 script 块 = ECharts 内联包
start = opens[1] + len('<script>')
end = html.find('</script>', start)
js = html[start:end]
print('echarts bundle 长度 %d，含 echarts：%s，含 </script：%s'
      % (len(js), 'echarts' in js, '</script' in js))
assert 'echarts' in js and '</script' not in js

css = io.open(os.path.join(BUILD, 'report_theme.css'), encoding='utf-8').read()

seed = json.load(io.open(os.path.join(BUILD, 'seed', 'report_600456.json'), encoding='utf-8'))
mod8 = [m for m in seed['mods'] if str(m['no']) == '8'][0]['html']
chart = [c for c in seed['charts'] if c['id'] == 'chartBSTN'][0]
opt = json.dumps(chart['opt'], ensure_ascii=False)

page = (
    '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
    '<title>模块8图表预览</title>\n<style>\n' + css + '\n'
    'body{margin:0;background:#f6f1f2;}\n'
    'body,body *{animation:none!important;transition:none!important;}\n'
    '</style></head>\n<body>\n<div class="wrap">\n'
    '<div class="card" id="m8">\n' + mod8 + '\n</div>\n</div>\n'
    '<script>' + js + '</script>\n'
    '<script>\n'
    'var opt = ' + opt + ';\n'
    'var el = document.querySelector(\'[data-chart="chartBSTN"]\');\n'
    'var inst = echarts.init(el);\n'
    'inst.setOption(opt, true);\n'
    'window.__CHART_OK = 1;\n'
    'document.title = "OK";\n'
    'window.__H = el.getBoundingClientRect().height;\n'
    'window.__W = el.getBoundingClientRect().width;\n'
    '</script>\n</body></html>\n'
)
out = os.path.join(BUILD, '_preview_bstn.html')
io.open(out, 'w', encoding='utf-8').write(page)
print('已生成 %s（%d 字符）' % (out, len(page)))
