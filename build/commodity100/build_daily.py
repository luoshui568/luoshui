#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组装《大宗商品日线对比图》单文件离线页面。
模板 template_daily.html + 内联 Chart.js + 内联日线数据 -> deliver/*.html
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
DEST = '/Users/luoshui/WorkBuddy/2026-10-10-22-59-27/luoshui/deliver'
NAME = '大宗商品日线对比图-2005-2026.html'
# 云端凭据与数据文库 / 研报库共用同一份（匿名可发布 key，属可公开凭据）
CLOUD_JSON = os.path.abspath(os.path.join(BASE, '..', 'cloud.json'))
# 构建开关（{"builtin": false} ＝ 不注入打包的内置日线数据）
OPTS_JSON = os.path.join(BASE, 'build_opts.json')


def build_opts():
    """构建开关。

    build_opts.json 里 {"builtin": false} 表示**不把内置 31 条日线打进页面** ——
    整页只剩「我的商品」（存云端），体积从 ~1.9MB 掉到 ~0.2MB。
    临时恢复：命令行加 --with-builtin；强制去掉：--no-builtin。
    """
    o = {'builtin': True}
    try:
        if os.path.exists(OPTS_JSON):
            o.update(json.load(open(OPTS_JSON, encoding='utf-8')))
    except Exception as e:
        print('  ! build_opts.json 读取失败（按默认「带内置数据」构建）：', e)
    if '--with-builtin' in sys.argv:
        o['builtin'] = True
    if '--no-builtin' in sys.argv:
        o['builtin'] = False
    return o


def cloud_js():
    """把 envId + key 注入页面，供「我的商品」读写云端。文件缺失时留空 → 前端自动降级本机。"""
    try:
        cfg = json.load(open(CLOUD_JSON, encoding='utf-8'))
        env = str(cfg.get('envId') or '').strip()
        key = str(cfg.get('key') or '').strip()
        if not env or not key:
            return 'window.WB_CFG = { envId: "", key: "", rest: "" };'
        return ('window.WB_CFG = { envId: %s, key: %s, rest: %s };'
                % (json.dumps(env), json.dumps(key),
                   json.dumps('https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % env)))
    except Exception as e:
        print('  ! 云端配置读取失败（将降级为本机存储）：', e)
        return 'window.WB_CFG = { envId: "", key: "", rest: "" };'


def build(diag=None, opts=None):
    opts = opts or build_opts()
    if opts.get('builtin'):
        data_js = open(f'{BASE}/data/daily_data.json', encoding='utf-8').read()
    else:
        data_js = '{"groups":[]}'        # 空内置：页面上只剩「我的商品」
    tpl = open(f'{BASE}/template_daily.html', encoding='utf-8').read()
    out = (tpl
           .replace('/*__CLOUD__*/',    cloud_js())
           .replace('/*__CHARTJS__*/', open(f'{BASE}/data/chart.umd.js', encoding='utf-8').read())
           .replace('/*__XLSX__*/',    open(f'{BASE}/xlsx_lite.js', encoding='utf-8').read())
           .replace('/*__DATA__*/',    data_js))
    for ph in ('/*__CLOUD__*/', '/*__CHARTJS__*/', '/*__XLSX__*/', '/*__DATA__*/'):
        assert ph not in out, '占位符未替换干净：' + ph
    if diag:
        out = out.replace('</body>', diag + '\n</body>', 1)
    return out


if __name__ == '__main__':
    opts = build_opts()
    html = build(None, opts)
    os.makedirs(DEST, exist_ok=True)
    p = f'{DEST}/{NAME}'
    open(p, 'w', encoding='utf-8').write(html)
    print('built:', p)
    print('体积:', round(len(html.encode('utf-8')) / 1024 / 1024, 2), 'MB')
    print('内置数据:', '✓ 已打包（31 条内置序列）' if opts.get('builtin')
          else '✗ 未打包（页面上只有「我的商品」，开关在 build_opts.json）')
    print('日期控件:', 'dt-from' in html, 'dt-to' in html, '| 自定义按钮:', 'btn-custom' in html)
    print('上传能力:', 'openUpload' in html, '| xlsx 解析:', 'parseXlsx' in html,
          '| 编辑面板:', 'openEdit' in html)
    print('导出能力:', '✓ 宽表 Excel 写出（xlsxBytes）+ CSV 写出（csvWideText）'
          if ('xlsxBytes' in html and 'csvWideText' in html) else '✗ 导出函数缺失')
    env_in = 'window.WB_CFG = { envId: "fdels568' in html
    print('云端配置:', '✓ 已注入' if env_in else '✗ 未注入（将降级本机存储）',
          '| 云端 API 层:', 'WBCloud' in html)
