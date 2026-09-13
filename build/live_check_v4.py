# -*- coding: utf-8 -*-
"""线上产物核对（v4 · 研报页 + 工作台跳转）

必须**二进制读**线上文件：文本模式会把 CRLF 归一化，导致 md5 误判「上传没生效」。

三方 = 本机 deploy/ + 线上 + 桌面副本，两页各查一遍。
桌面副本刻意保持与 deploy/ **逐字节一致**，并且两页放同一目录（桌面），
因为工作台里的名称链接是相对路径 `report.html?code=…`，file:// 下要能互相跳。
"""
import hashlib
import shutil
import urllib.request

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
DESK = r'C:\Users\50522\Desktop'
DOM = 'https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com'

PAIRS = [
    ('index.html', 'index.html', r'矿产战略执行工作台.html'),
    ('report.html', 'report.html', 'report.html'),
]


def md5b(b):
    return hashlib.md5(b).hexdigest()


def get(url, tries=3):
    last = None
    for _ in range(tries):
        try:
            r = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'})
            with urllib.request.urlopen(r, timeout=90) as f:
                return f.read()
        except Exception as e:
            last = e
    raise last


FEATS = {
    'index.html': {
        '研报链接样式 rptLink': '.stkTab a.rptLink{',
        '研报链接辅助 rptHref': 'function rptHref(r){',
        '研报代码缓存 RPT_CODES': 'var RPT_CODES = {}, _rptCodesLoaded = false;',
        '拉取研报代码 loadReportCodes': 'function loadReportCodes(cb){',
        '名称列链接': 'a class="nm rptLink',
        '代码列链接': 'a class="cd rptLink',
        '打开研报 openReport': 'openReport:function(code){',
        '操作列 📄 按钮': "App.openReport(\\'",
        '名称可点击提示': '点标的名称即可打开它的深度研究报告',
        '表格渲染后拉一次': 'loadReportCodes(function(){ renderStockTable(); });',
        '原有：板块标签条': 'function renderStockGrps(',
        '原有：管理员删除 RPC': 'wb_admin_delete_row',
    },
    'report.html': {
        '云配置注入 RPT_CFG': 'window.RPT_CFG',
        '离线兜底副本 RPT_SEED': 'window.RPT_SEED',
        '三表：研报头': 'wb_reports',
        '三表：模块': 'wb_report_mods',
        '三表：图表': 'wb_report_charts',
        '删除走管理员 RPC': 'wb_admin_delete_row',
        '红主题主色变量': '--accent:#c8102e',
        '红色 hero 渐变': '#4a0710 0%,#a3122a 52%,#c8102e 100%',
        '编辑器命名空间 Rpt': 'var Rpt = {',
        '编辑模式开关': 'toggleEdit: function(',
        '页眉保存': 'svHead: function(',
        '图表保存': 'svChart: function(',
        '具名标记还原': 'function revive(node, opt){',
        '标记容错（多花括号）': "String(arg).replace(/[}\\s]+$/, '')",
        '图表数据表模型': 'function chartModel(opt){',
        '图表数据表写回': 'function applyGrid(opt, model){',
        '管理面板 DOM': 'id="rptDrawer"',
        'ECharts 内联': 't.version="5.5.1"',
        'forecastTip 还原': 'forecastTip',
        'stackSum 还原': 'stackSum',
        '正文可视化编辑区': "rteField('m-edit'",
        '结论/本质/页脚也是可视化': "rteField('h-vc'",
        '富文本工具条': 'function rteBar(id, withChart){',
        '载入时把图表转成标签': 'function rteLoad(html){',
        '保存时把标签还原成图': 'function rteSave(html){',
        '未改动就不洗排版': 'function rteRead(id, orig){',
        '源码区默认折叠': '代码（一般不用动',
        '写库前清洗 HTML': 'function sanitizeHtml(html){',
        '图表标签不可编辑': 'rte-chip[data-chart]',
        '新建研报先查重': "wb_reports?id=eq.' + code + '&select=id,name,title'",
        '防覆盖拒绝文案': '不能重复创建',
    },
}

SECRETS = ['981208', 'passHash']

rows = []
allok = True
for name, cloud, deskname in PAIRS:
    print('=' * 66)
    print('【%s】' % name)
    print('=' * 66)
    local = open(BASE + r'\deploy' + '\\' + name, 'rb').read()
    live = get('%s/%s' % (DOM, cloud))
    print('[1] 三方 md5')
    print('    本机 deploy/%-12s %s  %d 字节' % (name, md5b(local), len(local)))
    print('    线上      %-12s %s  %d 字节' % (name, md5b(live), len(live)))
    same = (md5b(local) == md5b(live))
    print('    本机 == 线上：%s' % ('✅' if same else '❌'))

    dpath = DESK + '\\' + deskname
    try:
        desk = open(dpath, 'rb').read()
    except Exception:
        desk = None
    if desk is None or md5b(desk) != md5b(local):
        shutil.copyfile(BASE + r'\deploy' + '\\' + name, dpath)
        desk = open(dpath, 'rb').read()
        print('    桌面副本已刷新 → %s' % md5b(desk))
    print('    桌面 %-16s %s  %d 字节' % (deskname, md5b(desk), len(desk)))
    print('    桌面 == 本机：%s' % ('✅' if md5b(desk) == md5b(local) else '❌'))

    text = live.decode('utf-8', 'replace')
    print('\n[2] 线上关键特征串')
    bad = 0
    for k, v in FEATS[name].items():
        hit = v in text
        if not hit:
            bad += 1
        print('    %s %s' % ('✅' if hit else '❌', k))
    print('    合计 %d/%d 命中' % (len(FEATS[name]) - bad, len(FEATS[name])))

    print('\n[3] 安全回归')
    sec_ok = True
    for s in SECRETS:
        n = text.count(s)
        print('    %-10s 出现次数 %d（须为 0）' % (s, n))
        if n:
            sec_ok = False
    if name == 'index.html':
        print('    report.html 链接存在 :', 'report.html?code=' in text)
        sec_ok = sec_ok and ('report.html?code=' in text)
    print()
    rows.append((name, same, md5b(desk) == md5b(local), bad == 0, sec_ok))
    allok = allok and same and bad == 0 and sec_ok

print('=' * 66)
for name, s1, s2, s3, s4 in rows:
    print('%-14s 线上一致 %s · 桌面一致 %s · 特征串 %s · 无明文密码 %s'
          % (name, '✅' if s1 else '❌', '✅' if s2 else '❌', '✅' if s3 else '❌', '✅' if s4 else '❌'))
print('结论：' + ('全部通过 ✅' if allok else '有项目不通过 ❌'))
print('=' * 66)
