# -*- coding: utf-8 -*-
"""模块 25 / 27 本地预览页（用于截图目视核对）。

· ECharts 内联包直接从 deploy/report.html 抠出来（保证与线上同一版本）
· CSS 用 build/report_theme.css
· 数据用 build/seed/report_600456.json（刚重刷过，与线上库一致）
· 用 URL hash 切卡片：#m25 / #m27，避免一次截一张超长图
· ★ 必须注入 animation:none!important —— 否则无头截图会整张空白（踩过两次）
"""
import io
import json
import os
import re

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
BUILD = os.path.join(BASE, 'build')
REPORT = os.path.join(BASE, 'deploy', 'report.html')

html = io.open(REPORT, encoding='utf-8').read()
opens = [m.start() for m in re.finditer(r'<script[^>]*>', html)]
start = opens[1] + len('<script>')
end = html.find('</script>', start)
js = html[start:end]
assert 'echarts' in js and '</script' not in js, 'ECharts 内联包提取失败'
print('ECharts 内联包 %d 字符' % len(js))

css = io.open(os.path.join(BUILD, 'report_theme.css'), encoding='utf-8').read()
seed = json.load(io.open(os.path.join(BUILD, 'seed', 'report_600456.json'), encoding='utf-8'))
mods = {str(m['no']): m['html'] for m in seed['mods']}
charts = {c['id']: c['opt'] for c in seed['charts']}
print('seed: %d 模块 / %d 图表；m25 %d 字 · m27 %d 字'
      % (len(mods), len(charts), len(mods['25']), len(mods['27'])))

# 只渲染这两个模块、这两张图
need = {}
for k in ('chartEstimate', 'chart_eps'):
    assert k in charts, 'seed 缺图表 %s' % k
    need[k] = charts[k]

page = (
    '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
    '<title>模块 25 / 27 预览</title>\n<style>\n' + css + '\n'
    'body{margin:0;background:#f6f1f2;}\n'
    'body,body *{animation:none!important;transition:none!important;}\n'
    '.card{display:none;}\n'
    '.card.on{display:block;}\n'
    '</style></head>\n<body>\n<div class="wrap">\n'
    '<div class="card" id="m25">' + mods['25'] + '</div>\n'
    '<div class="card" id="m27">' + mods['27'] + '</div>\n'
    '</div>\n'
    '<script>' + js + '</script>\n'
    '<script>\n'
    'var CHARTS = ' + json.dumps(need, ensure_ascii=False) + ';\n'
    'var want = (location.hash || "#m25").replace("#", "");\n'
    'var cards = document.querySelectorAll(".card");\n'
    'for(var i = 0; i < cards.length; i++){\n'
    '  if(cards[i].id === want) cards[i].className = "card on";\n'
    '}\n'
    'var slots = document.querySelectorAll("[data-chart]");\n'
    'var n = 0;\n'
    'for(var j = 0; j < slots.length; j++){\n'
    '  var el = slots[j];\n'
    '  var k = el.getAttribute("data-chart");\n'
    '  if(!CHARTS[k]) continue;\n'
    '  if(el.offsetParent === null) continue;\n'   # 只渲染当前可见卡片里的图
    '  try{\n'
    '    var inst = echarts.init(el);\n'
    '    inst.setOption(CHARTS[k], true);\n'
    '    n++;\n'
    '  }catch(e){ el.innerHTML = "渲染失败: " + e.message; }\n'
    '}\n'
    'window.__RENDERED = n;\n'
    'window.__SLOTS = slots.length;\n'
    'window.__WANT = want;\n'
    'document.title = want + " | 已渲染 " + n + " 图";\n'
    '</script>\n</body></html>\n'
)
out = os.path.join(BUILD, '_preview_m2527.html')
io.open(out, 'w', encoding='utf-8').write(page)
print('已生成 %s（%d 字符）' % (out, len(page)))
