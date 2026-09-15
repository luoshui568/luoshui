# -*- coding: utf-8 -*-
"""线上产物核对（v4 · 研报页 + 研报库 + 工作台跳转）

必须**二进制读**线上文件：文本模式会把 CRLF 归一化，导致 md5 误判「上传没生效」。

三方 = 本机 deploy/ + 线上 + 桌面副本，三页各查一遍。
桌面副本刻意保持与 deploy/ **逐字节一致**，并且三页放同一目录（桌面），
因为页面之间是相对路径互跳（`report.html?code=…` / `research.html`），file:// 下要能互相跳。
"""
import hashlib
import re
import shutil
import urllib.request

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
DESK = r'C:\Users\50522\Desktop'
DOM = 'https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com'

PAIRS = [
    ('index.html', 'index.html', r'矿产战略执行工作台.html'),
    ('report.html', 'report.html', 'report.html'),
    ('research.html', 'research.html', 'research.html'),
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
        '注册入口 按钮': 'id="g-regbtn"',
        '注册视图 容器': '<div id="g-reg" style="display:none">',
        '注册提交 doRegister': 'App.doRegister()',
        '注册走云端函数': 'wb_admin_register',
        '待批列表 RPC': 'wb_admin_pending_list',
        '审批 RPC': 'wb_admin_review',
        '审批区块 #admPending': 'id="admPending"',
        '按角色落脚 goHome': 'function goHome(){',
        '普通管理员落投资标的': "? 'stock' : 'dash'",
        '越权门禁 needSuper': 'needSuper()',
        '★导入新建走 insertRow': "insertRow('stocks', row);",
        '★非文本列空串清洗': 'function dropEmptyNonText(o){',
        '★时间戳列清单': "'info_at', 'sync_at',",
        '★补名称也走 updateRow': "updateRow('stocks', old.id, {name:nm});",
        '★孤儿记录计数 ORPHAN_N': 'var ORPHAN_N = 0;',
        '★拉取保留本机记录': 'var keep = S[k].filter(function(r){ return r && r.id && !seen[r.id]; });',
        '★设置页未上云提示': '本机有 / 云端没有',
        # ---- 多板块：一只标的可同时属于多个板块（2026-09-14 · 修「粘 157 个只进来 111 个」）----
        '★多板块 拆分 stkGrpsOf': 'function stkGrpsOf(r){',
        '★多板块 拼装 stkGrpSet': 'function stkGrpSet(a){',
        '★多板块 解析返回数组 stkGrpParse': 'function stkGrpParse(v){',
        '★多板块 判定 stkGrpHas': 'function stkGrpHas(r, g){',
        '★多板块 快捷标签增删 grpToggleIn': 'function grpToggleIn(tid, name){',
        '★多板块 标签条 CSS（别再只挂在 .stkPick 下）': '.qs .q{',
        # ---- 按角色收窄可见版块：ops 只可见「投资标的」（2026-09-14）----
        '★角色可见范围 pageAllowed': 'function pageAllowed(id){',
        '★角色可见范围 visiblePages': 'function visiblePages(){',
        '★角色可见范围 OPS_PAGES': 'var OPS_PAGES = ',
        '★越权跳转被拒提示': '仅超级管理员可见',
        '★团队成员视图提示': '团队成员视图',
        '★团队成员视图提示容器': 'id="opsHint"',
        '★计数徽标空值安全 setCnt': 'function setCnt(id, v){',
        # ---- 行情回写：PostgREST 批量写入要求同批 key 一致（2026-09-14）----
        '★行情回写 按 key 签名分组': 'var sigs = [], bySig = {};',
        '★行情回写 失败原因可见': '行情回写失败：',
        # ---- ops 也要能改密码 / 退登录 ⇒ 设置页留给它，改成页内按角色裁（2026-09-14）----
        '★ops 可见含设置页': "var OPS_PAGES = ['stock', 'research', 'set'];",
        # ---- 「研究报告」入口：两个角色都有，且**独立成页**（2026-09-14）----
        '★研究报告 导航项（ext 独立页）': "{id:'research', ic:'📚', name:'研究报告', en:'RESEARCH', ext:'research.html'}",
        '★研究报告 打开独立页 App.ext': "ext:function(u){ location.href = String(u || ''); },",
        '★研究报告 侧栏渲染成 ext 跳转': "var clk = p.ext ? ('App.ext(\\'' + p.ext + '\\')')",
        '★研究报告 App.go 也走跳转': 'App.ext(PAGES[pi].ext); return;',
        '★侧栏提示含三项': '开放「投资标的」「研究报告」「数据与设置」',
        '★研报份数徽标（独立轻请求，别碰 loadReportCodes）': "setCnt('research', (rows || []).length || '');",
        '★研报份数徽标函数': 'function loadReportCount(){',
        # ---- 拼音首字母搜索（2026-09-14）----
        '★拼音锚点表（23 声母 · 两个字符串）': 'var PY_A = ',
        '★拼音区间定位': "if(ch.localeCompare(PY_A.charAt(mid), 'zh') >= 0)",
        '★拼音按原串缓存': 'function pyInitCached(s){',
        '★拼音命中判定': 'function pyHit(src, q){',
        '★拼音自检失败即禁用': '宁可不支持拼音搜索',
        '★标的搜索接入拼音': 'pyHit(name + ind + reg + grp, pq)',
        '★首字母提示（工作台）': '支持拼音首字母，如 gyby',
        '★设置页角色裁剪 applySetScope': 'function applySetScope(){',
        '★私人卡片标记 data-sup': 'data-sup="1"',
        '★超管专属按钮 supOnly': 'supOnly',
        '★团队成员说明卡片': 'id="cardOpsHelp"',
        '★账号卡片 id': 'id="cardAdmin"',
        '★云端卡片 id': 'id="cardCloud"',
        '★ops 标题改写': '我的<span>账号</span>',
        '★团队成员使用说明': '使用说明（团队成员）',
        '★团队成员视图标识': '团队成员视图',
        # ---- 异步会话校验的过期结果竞态（2026-09-14 · 曾伪装成 26 项环境抖动）----
        '★会话校验 token 比对 chkTok': 'var chkTok = Auth.token;',
        '★过期结果作废': 'if(Auth.token !== chkTok) return;',
    },
    'report.html': {
        # ---- 研报标准模板 v3.1（31 模块 / 六篇）上线哨兵 · 2026-09-14 ----
        # 库内 5 份研报已升到 31 模块；若线上壳还是 v2.3，essence 会错误地插在
        # 模块 23 前面（中途冒出来）→ 这三条专门盯「模板改了忘上线」。
        '★模板 v3.1 版本注释（漏构建哨兵）': '研报标准模板 v3.1 · 31 模块 / 六篇',
        '★模板 v3.1：31 个模块文案': '31 个模块',
        '★模板 v3.1 essence 挂 m31': "String(m.no) === '31'",
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
        # ⚠️ 这条是「模板改了忘重新构建」的哨兵：idxText 只在模板里加过，
        #    漏构建时线上产物会缺它 → 图表标签直接把 {{fn:idxText:…}} 当文本画出来。
        'idxText 还原（漏构建哨兵）': 'idxText: function(a){',
        'idxColorList 还原': 'idxColorList: function(list){',
        'idxColorBreak 还原': 'idxColorBreak: function(a){',
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
        # 左侧竖排目录（红色主体 · fixed，不再被顶部操作条挡住）
        '目录左固定悬浮': 'position:fixed;z-index:80;',
        '目录滚动高亮': 'function tocSpy(',
        '目录项序号 data-i': 'data-i="',
        '锚点定位补偿': '.card[id]{scroll-margin-top:86px;}',
        # ---- 图表数据表「导入 Excel / CSV」（2026-09-14 · 用户：图表编辑增加可上传导入 excel）----
        '★导入 Excel 按钮': '📥 导入 Excel / CSV',
        '★导入工具条 CSS': '.rpt-iotools{',
        '★导入入口 impPick': 'impPick: function(){',
        '★上传解析 impTable': 'impTable: function(file){',
        '★灌表 impApply': 'impApply: function(key, rows, fname){',
        '★导出 CSV dlTable': 'dlTable: function(){',
        '★xlsx 解析 parseXlsx': 'function parseXlsx(buf){',
        '★zip 中央目录 unzipEntries': 'function unzipEntries(buf){',
        '★原生解压 deflate-raw': "new DecompressionStream('deflate-raw')",
        '★分隔文本解析 rowsFromText': 'function rowsFromText(text){',
        '★Excel 日期序列号还原 serialDate': 'function serialDate(n){',
        '★表头→系列映射 rowsToModel': 'function rowsToModel(rows, kind){',
        '★覆盖导入也走密码门禁': "['impTable','导入',true,null,",
        '★窄屏抽屉用 100%（不是 100vw）': '.rpt-drawer{width:100%}',
        # ---- 表格「增加行 / 删除行」（2026-09-14 · 模块正文表格 + 图表数据表）----
        '★图表表增行按钮': 'Rpt.gridAddRow()',
        '★图表表删行按钮': 'Rpt.gridDelFocus()',
        '★行内 ✕ 删行': 'gridDelRow(',
        '★增行 gridAddRow': 'gridAddRow: function(){',
        '★删行 gridDelRow': 'gridDelRow: function(idx){',
        '★删光标行 gridDelFocus': 'gridDelFocus: function(){',
        '★重画表格 gridPaint': 'gridPaint: function(m){',
        '★正文表增删行 rteRow': 'rteRow: function(id, delta){',
        '★找光标所在行 rteRowAt': 'function rteRowAt(id){',
        '★插行后光标落位 rteCaretIn': 'function rteCaretIn(el){',
        '★正文表工具条 ＋行': '">＋ 行</button>',
        '★正文表工具条 －行': '">－ 行</button>',
        '★删行专用按钮样式 .gx': "td.ix .gx{",
        '★删行挂门禁（act=删除）': "['gridDelRow','删除',false,null,",
        '★正文表删行挂门禁': "['rteRow','删除',false,",
    },
    'research.html': {
        '云配置注入 WB_CFG': 'window.WB_CFG',
        '读研报表 wb_reports': 'wb_reports?select=',
        '卡片容器': 'id="grid"',
        '顶栏容器': 'id="lbar"',
        '统计条容器': 'id="stats"',
        '卡片渲染 cardHtml': 'function cardHtml(r){',
        '类型识别 repKind': 'function repKind(r){',
        'jsonb 兜底 asArr': 'function asArr(v){',
        '摘要剥标签 stripHtml': 'function stripHtml(h){',
        '搜索 setQ': 'setQ:function(v){',
        '类型筛选 setKindIdx': 'setKindIdx:function(idx){',
        '排序 setSort': 'setSort:function(v){',
        '刷新 load': 'load:function(isRetry){',
        '★拼音锚点表（23 声母 · 两个字符串）': 'var PY_A = ',
        '★拼音区间定位': "if(ch.localeCompare(PY_A.charAt(mid), 'zh') >= 0)",
        '★拼音命中判定': 'function pyHit(src, q){',
        '★研报搜索接入拼音': "pyHit([r.name, r.title, r.subtitle, r.kicker, stripHtml(r.verdict_html)].join(' '), pq)",
        '★首字母提示（研报库）': '支持拼音首字母，如 gyby',
        '返回工作台 Lib.back': "back:function(){ location.href = 'index.html'; },",
        '进研报 report.html?code=': 'report.html?code=',
        '登录态与工作台共用': "var AUTH_KEY = 'wb_auth_v1';",
        '读失败可见': 'L.err = String(e && e.message || e);',
        '空态提示': '还没有研究报告',
        '免责声明': '不构成任何投资建议',
        '统计条 4 格 CSS': '.stats{display:grid;grid-template-columns:repeat(4,1fr)',
        '卡片 hover 抬升': '.card:hover{transform:translateY(-5px)',
        '启动即拉取': 'Lib.load(false);',
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

# ---------------------------------------------------------------------------
# [4] 构建新鲜度：模板里定义的每个函数、FNS 每个键都必须出现在产物里
#     —— 踩过的坑：report.template.html 加了 FNS.idxText，但没重新跑 build.py，
#        线上产物缺它 → 贵研铂业那张图的标签把 {{fn:idxText:3:-23.4%}} 当文本画出来。
#        这类「静态检查抓不到、肉眼也未必看得出」的问题，用这个哨兵兜住。
# ---------------------------------------------------------------------------
print()
print('=' * 66)
print('【构建新鲜度】模板 → 产物（防「改了模板忘重新构建」）')
print('=' * 66)
FRESH = [('index.html', 'app.template.html'), ('report.html', 'report.template.html'),
         ('research.html', 'research.template.html')]
fresh_ok = True
for art, tpl in FRESH:
    a = open(BASE + r'\deploy' + '\\' + art, encoding='utf-8').read()
    t = open(BASE + r'\deploy' + '\\' + tpl, encoding='utf-8').read()
    fns = sorted(set(re.findall(r'\bfunction\s+([A-Za-z_$][\w$]*)\s*\(', t)))
    miss = [n for n in fns if ('function %s(' % n) not in a]

    # FNS 具名标记表：模板里每个键都要在产物里
    mi = t.find('var FNS = {')
    fkeys, fmiss = [], []
    if mi >= 0:
        d, j = 0, t.find('{', mi)
        for k in range(j, len(t)):
            if t[k] == '{':
                d += 1
            elif t[k] == '}':
                d -= 1
                if d == 0:
                    block = t[j:k + 1]
                    break
        fkeys = sorted(set(re.findall(r'^\s{2}([A-Za-z_$][\w$]*)\s*:\s*function', block, re.M)))
        fmiss = [n for n in fkeys if ('%s: function(' % n) not in a]

    ok = not miss and not fmiss
    fresh_ok = fresh_ok and ok
    print('%s %-13s 模板函数 %3d 个 · 缺失 %s' % ('✅' if not miss else '❌', art, len(fns),
                                                miss or '无'))
    if fkeys:
        print('   %s FNS 标记 %d 个（%s）· 缺失 %s'
              % ('✅' if not fmiss else '❌', len(fkeys), ','.join(fkeys), fmiss or '无'))

print('结论：' + ('全部通过 ✅' if allok and fresh_ok else '有项目不通过 ❌'))
print('=' * 66)
