# -*- coding: utf-8 -*-
"""产出**独立单文件**深度研究报告 HTML（双击即可离线打开）。

与 build.py 的关系：
  * build.py 的 build_report() 把 seed 路径硬编码成 `report_600456.json`（宝钛兜底链），
    并固定写 `deploy/report.html`；
  * 本脚本是「一码一文件」的旁路：读 `seed/report_<code>.json`，
    同样把 echarts / 国标世界地图 / 主题 CSS / 云配置内联进 report.template.html，
    但产出到 `deliver/` 下的中文命名文件 —— 不碰宝钛的构建链与 deploy 产物。

用法：
    python build_report_single.py 600392
    python build_report_single.py 600392 --out /tmp/x.html
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEPLOY = os.path.join(ROOT, 'deploy')
SEED = os.path.join(HERE, 'seed')
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from _norm_bold import balance, convert                     # noqa: E402


def rd(p):
    return json.load(io.open(p, encoding='utf-8'))


def normalize_bold(seed):
    """正文 `**x**` → `<b>x</b>` 归一。

    壳里**没有** markdown 转换（`sanitizeHtml` 只做安全清洗），所以正文里残留的
    `**` 会原样显示成星号。项目的既定做法是渲染后用 `build/_norm_bold.py` 归一
    （它同时兜住 002408 那种「`</b>` 误写成 `**`」导致整篇变粗的笔误）。
    本脚本直接把这一步放在**注入之前**，保证产出的单文件是干净的。
    """
    stat = {'pair': 0, 'lone': 0, 'drop': 0, 'mod': 0}
    bad = []
    for m in seed['mods']:
        h = m.get('html') or ''
        if '**' not in h:
            continue
        new, st = convert(h)
        stat['pair'] += st['pair']
        stat['lone'] += st['lone']
        stat['drop'] += st['drop']
        if new == h:
            continue
        b = balance(new)
        if b or st['left']:
            bad.append('no=%s（%s%s）' % (m.get('no'), ' '.join(b),
                                          '｜残留 ** ×%d' % st['left'] if st['left'] else ''))
            continue
        m['html'] = new
        stat['mod'] += 1
    assert not bad, '正文归一自检未过：%s' % '；'.join(bad)
    return stat


def build(code, out_path=None):
    seedp = os.path.join(SEED, 'report_%s.json' % code)
    if not os.path.exists(seedp):
        sys.exit('缺少 %s —— 先跑 python report_build_v31.py %s' % (seedp, code))
    seed = rd(seedp)
    bold = normalize_bold(seed)

    tpl = io.open(os.path.join(DEPLOY, 'report.template.html'), encoding='utf-8').read()
    lib = io.open(os.path.join(HERE, 'lib', 'echarts.min.js'), encoding='utf-8').read()
    worldmap = io.open(os.path.join(HERE, 'lib', 'world-cn.js'), encoding='utf-8').read()
    css = io.open(os.path.join(HERE, 'report_theme.css'), encoding='utf-8').read()
    cf = rd(os.path.join(HERE, 'cloud.json'))
    cloud = {'envId': cf['envId'], 'key': cf['key']}

    for ph in ('/*__ECHARTS__*/', '/*__REPORTCSS__*/', '/*__RPTCFG__*/', '/*__WORLDMAP__*/'):
        assert ph in tpl, 'report.template.html 缺少占位符 ' + ph

    cfg_js = ('window.RPT_CFG = ' + json.dumps(cloud, ensure_ascii=False) + ';\n'
              + 'window.RPT_SEED = '
              + json.dumps(seed, ensure_ascii=False, separators=(',', ':')) + ';')

    out = (tpl.replace('/*__ECHARTS__*/', lib)
              .replace('/*__WORLDMAP__*/', worldmap)
              .replace('/*__REPORTCSS__*/', css)
              .replace('/*__RPTCFG__*/', cfg_js))

    if not out_path:
        name = seed['report'].get('name') or code
        out_path = os.path.join(ROOT, 'deliver', '%s-%s-深度研究报告.html' % (name, code))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    io.open(out_path, 'w', encoding='utf-8').write(out)
    return out_path, seed, bold


if __name__ == '__main__':
    a = sys.argv[1:]
    code = a[0] if a and not a[0].startswith('--') else '600392'
    outp = None
    if '--out' in a:
        outp = a[a.index('--out') + 1]
    dst, seed, bold = build(code, outp)
    print('已生成 %s  (%.1f KB)' % (dst, os.path.getsize(dst) / 1024.0))
    print('  %s（%s）· %d 模块 · %d 图'
          % (seed['report']['name'], seed['report']['code'],
             len(seed['mods']), len(seed['charts'])))
    print('  正文 `**` 归一：成对 %d 处 → <b> ｜ 未闭合收尾 %d ｜ 碎片删除 %d ｜ 影响模块 %d'
          % (bold['pair'], bold['lone'], bold['drop'], bold['mod']))
