# -*- coding: utf-8 -*-
"""线上产物核对（v4 · 研报页 + 研报库 + 工作台跳转）

必须**二进制读**线上文件：文本模式会把 CRLF 归一化，导致 md5 误判「上传没生效」。

三方 = 本机 deploy/ + 线上 + 工作区 deliver/ 副本，三页各查一遍。
副本刻意保持与 deploy/ **逐字节一致**，并且三页放同一目录（deliver/），
因为页面之间是相对路径互跳（`report.html?code=…` / `research.html`），file:// 下要能互相跳。
★ 2026-09-21：落点由桌面改为 `deliver/`（用户要求桌面不留副本）。
"""
import hashlib
import re
import shutil
import time
import urllib.request

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
# ★ 2026-09-21 起**不再写桌面**（用户明确要求「桌面不留副本，改落工作区 deliver/」）。
#   第三方副本仍然保留、仍与本机逐字节比，只是换了个落点 —— 三页同目录的约束不变。
DESK = BASE + r'\deliver'
DOM = 'https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com'

PAIRS = [
    ('index.html', 'index.html', r'矿产战略执行工作台.html'),
    ('report.html', 'report.html', 'report.html'),
    ('research.html', 'research.html', 'research.html'),
    # ★ 2026-10-10：研报库页脚新增「友情链接」→ 本节页面。
    #   线上 /research.html 的 .frd-a 指向它，所以它必须进核对范围，
    #   否则链接坏了这个脚本也不会报（盲区）。
    ('market-history.html', 'market-history.html', 'market-history.html'),
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
        '★模板 v3.1 版本注释（漏构建哨兵）': '研报标准模板 v3.1-gold · 31 模块（母本＝宝钛股份 600456，2026-09-21）',
        '★模板 v3.1：31 个模块文案': '31 个模块',
        # ⚠️ 原来是 "String(m.no) === '31'" —— 标定「essence 挂在最后一个模块」。
        #    2026-09-17 改成按"最后一个模块"判断（600456 已从 31 模块精简为 29 模块，
        #    写死编号会让它的 essence 直接消失）。探针也跟着改，否则永远假红。
        '★一句话本质挂最后一个模块（兼容 29/31 模块）': 'm === _lastMod',
        '云配置注入 RPT_CFG': 'window.RPT_CFG',
        '离线兜底副本 RPT_SEED': 'window.RPT_SEED',
        '三表：研报头': 'wb_reports',
        '三表：模块': 'wb_report_mods',
        '三表：图表': 'wb_report_charts',
        '删除走管理员 RPC': 'wb_admin_delete_row',
        # ⚠️ 2026-09-17 整体换色（去粉 + 参考图鲜红 #d0202f + 参考图青蓝 #00b0f0），
        #    这两条探针原本钉的是旧砖红 #c8102e / #a3122a，换色后一直假红 —— 已同步。
        '红主题主色变量': '--accent:#d0202f',
        '红色 hero 渐变': '#4a0a15 0%,#c81a33 52%,#d0202f 100%',
        '★青蓝主题色（参考图 #00b0f0）': '#00b0f0',
        # ★ 2026-09-17 同图多系列「色相去重」（用户报「全是红色无法区分」）：
        #   钉住去重函数 + 撞车判据 + PB/PE 语义色 + 图表亮红档，防止被模板回退。
        '★多系列色相去重 btDistinct': 'function btDistinct(list){',
        '★色相撞车判据 btClash': 'function btClash(a, b){',
        '★PB/PE 语义色 btNameColor': 'function btNameColor(name){',
        '★去重已接线（SERC）': 'SERC = btDistinct(SERC);',
        '★图表亮红档（不粉）': '#dd3543',
        # ★ 2026-09-17 并排改整行（图表/表格独占一行、文字排到下面）：探针钉住
        #   渲染层归一函数 + 三处类名，防止以后再构建时被模板回退掉。
        '★并排改整行 归一函数 stackWide': 'function stackWide(root){',
        '★并排改整行 容器类 gr-stack': 'gr-stack',
        '★并排整行 CSS grid2.gr-stack': 'grid2.gr-stack',
        '★文字块 gr-txt': 'gr-txt',
        # ★ 2026-09-20 两张图并排（用户要求「两张图放到同一行」）：只有「两个子块
        #   全是图、无文字、无表格」才加 .gr-pair（全库 43 处 .grid2 仅 1 处命中）。
        #   探针钉住判据分支 + 容器类 + 窄栏留白函数，防止再构建时被模板回退。
        '★两张图并排 容器类 gr-pair': 'gr-pair',
        '★两张图并排 CSS grid2.gr-pair': 'grid2.gr-pair',
        '★并排窄栏顶部留白 pairTopPad': 'function pairTopPad(slot, opt){',
        # ★ 2026-09-20 库里没数据的图表槽位不再显示空框（用户：「下面这块被删除了的
        #   直接去掉不要显示」）。浏览态整块隐藏；编辑态保留占位（唯一填图入口）。
        #   探针钉住分支判据 + 空判据函数 + 并排收尾，防止再构建时被模板回退。
        '★空图浏览态整块隐藏 rpt-slotgone': 'rpt-slotgone',
        '★空图判据 optEmpty': 'function optEmpty(opt){',
        '★空图隐藏分支': 'if(!rec || optEmpty(rec.opt)){',
        '★空图并排收尾 sweepGoneSlots': 'function sweepGoneSlots(list){',
        '★空图并排收尾 CSS gr-solo': 'grid2.gr-solo',
        # ★ 2026-09-20 评分卡给每条原则补一行简明分析（用户：「在中间的空白列按
        #   这种简明扼要的分析帮我补全」）。原则名右侧那片空白本来纯浪费 ——
        #   现在同一个格子里、名称下方放 sc-note，权重/进度条/分数跨两行居中。
        #   ⚠️ 探针必须同步，否则改完必然假红（老坑）。
        '★评分卡分析行 sc-note': '.sc-note{grid-column:2;grid-row:2;',
        '★评分行两行网格': 'grid-template-columns:30px minmax(0,1fr) 46px 150px 36px;gap:4px 13px',
        '★窄屏 note 独占整行': '.sc-note{grid-column:1/-1;grid-row:3;',
        # ★ 2026-09-20 评分卡视觉升级（用户：「样式帮我做的好看一点」）。
        #   纯 CSS，零 HTML/JS 改动、零数据改动（分数/权重/总分/文案一字未动）。
        #   ⚠️ 三个坑已写进技能 §31.12：① 表头 ::before 必须 position:absolute，
        #   否则被 flex 居中成一条「划在标题下的细线」；② 行分隔线不能改成 border
        #   （会把卡片两层渐变切成两截），要用 background-image 画 1px；
        #   ③ 分数按档位着色只能用后代选择器借 :has()（sc-val 自身没有 hi/mid 类）。
        # ★★★ 2026-09-20 视觉升级。⚠️ 线上 report.html 的那行是 CRLF（\r\n）——
        #   探针里写死 `\n` 会「本地绿、线上红」假红一次（本轮踩过）。
        #   ⇒ 跨行的特征串一律只用 `{` 结尾，绝不在键里带换行与缩进。
        '★评分卡表头金点绝对定位': '.criteria-head::before{',
        '★评分卡表头金点锚左': 'position:absolute;left:21px;top:50%;transform:translateY(-50%);',
        '★评分卡表头标题居中': 'justify-content:center;gap:12px;padding:14px 20px;',
        '★评分卡编号方形徽章': 'width:26px;height:26px;border-radius:9px;',
        '★评分卡行分隔线用 background 画': 'background-size:100% 1px,100% 0;background-position:0 100%,0 100%;',
        '★评分卡分数按档着色 has': '.sc-line:has(.sc-bar i.mid) .sc-val{',
        '★评分卡总分条金红顶线': '.sc-total::before{content:"";position:absolute;left:0;right:0;top:0;height:2px;',
        '★评分卡窄屏列宽': 'grid-template-columns:26px minmax(0,1fr) 40px 1fr 34px',
        # —— 槽 29 动态调整（2026-09-22）：交互件在壳里、运行时生成 ⇒ 只能对着壳的产物验 ——
        '★评分卡动态调整入口': 'function scoreLive(root){',
        '★评分卡动态调整挂载': 'scoreLive(box);',
        '★评分卡实时条类名（防与状态类撞名）': "live.className = 'sc-livebar';",
        '★评分卡实时条样式': '.sc-livebar{display:flex;align-items:center;gap:9px;flex-wrap:wrap;',
        '★评分卡可拖动进度条': '.criteria.sc-live .sc-bar{position:relative;cursor:ew-resize;touch-action:none;',
        '★评分卡手柄跟分数走': 'left:var(--scp);',
        '★评分卡分数可直接改': '.sc-inp{width:100%;border:0;background:transparent;',
        '★评分卡调整后徽标转红': '.gauge-wrap.sc-dirty .gauge-badge{background:linear-gradient(135deg,#e43644,#a8111f);',
        # —— 槽 29 评分「提交到数据库」（2026-09-22 · 用户令「这个数据改完要提交到数据库里去」）——
        # 交互件与变换都在壳里、运行时生成 ⇒ 同样只能对着壳的产物验。
        '★评分卡提交按钮': '<button class="lv-btn lv-save" type="button" style="display:none">💾 提交到数据库</button>',
        '★评分卡提交按钮样式': '.sc-livebar .lv-btn.lv-save{border-color:#a8111f;background:#a8111f;color:#fff;',
        '★评分卡落库变换 scBuildHtml': 'function scBuildHtml(mod, scores){',
        '★评分卡点名句规范化 scNoteSentence': 'function scNoteSentence(scores, names){',
        # ★ 2026-09-22 追加：点名句「自洽即保留」（母本那句是手写措辞，无条件重写等于降级）
        '★评分卡点名句自洽即保留 scNoteConsistent': 'function scNoteConsistent(body, scores){',
        '★评分卡自洽判据（项号+分数逐一对上）': 'if(i < 0 || i > 9 || parseInt(m[2], 10) !== scores[i]) return false;',
        '★评分卡自洽则原样返回': 'if(body.indexOf(\'主要得分项为\') >= 0 && scNoteConsistent(body, scores)) return a + body + c;',
        '★评分卡纯数组总分 scTotalW': 'function scTotalW(scores, ws){',
        '★评分卡取值一致性判据（防 .sc-val 笔误静默改总分）': 'var storedTn = tnEl ? scFn(tnEl.textContent) : null;',
        '★评分卡提交前须为整数': '十项都要 0-10 的整数才能提交',
        '★评分卡落库方法 Rpt.commitScore': 'commitScore: function(id, material){',
        '★评分卡落库挂密码门 RGATE': "['commitScore','提交',false,null,",
        '★评分卡落库成功文案': '评分已写入数据库 —— 所有人看到的都是这一版',
        '★评分卡临时调整标记 data-sc-dyn': "mod.srcP.setAttribute('data-sc-dyn', '1');",
        # ★ 2026-09-22 追加：卡片定位改成「向上找最近 [data-mod]」
        #   —— 模块正文里一个未闭合的行内标签就会让 parentNode 取不到 data-mod，
        #      进而 mod.html 为空、提交按钮永远失败（002408 m1 实测踩到）。
        '★评分卡卡片定位（向上找 data-mod）': 'var card = null, _p = crit;',
        '★评分卡卡片定位注释': '_p = _p.parentNode;',
        # ⚠️ 别再往这里加 `data-w` —— 它在**模块 HTML** 里（score_lock 渲染），
        #    壳产物里没有 ⇒ 加进来必假红一次（2026-09-22 踩过）。那条归 _probe_lock29.py 管。
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
        # ⚠️ 2026-09-20：目录新增「投资核心」锚到页面顶部的核心结论区 #verdict
        #    （不是模块卡）→ CSS 选择器扩成 `.card[id], #verdict{…}`。
        #    旧探针钉的是旧串 `.card[id]{…}`，改完必然假红 —— 已同步。
        '锚点定位补偿': '.card[id], #verdict{scroll-margin-top:86px;}',
        # ---- 目录改十段（2026-09-20 · 用户重排）----
        #    投资核心 / 公司简介 / 公司业务 / 公司营收 / 公司投资 /
        #    公司链条 / 行业分析 / 供需分析 / 盈利预测 / 企业评分
        #    ⚠️ toc 存在库里，线上壳验不到它 —— 这几条真正盯的是
        #    「库改了但 seed 没同步 / 忘了重新构建」：seed 会以 RPT_SEED 注入壳内。
        '★目录十段：投资核心': '"text":"投资核心"',
        '★目录锚点 verdict（指向核心结论区）': '"anchor":"verdict"',
        '★目录十段：公司链条': '"text":"公司链条"',
        '★新增模块 行业分析（发现报告素材）': '"title":"钛行业介绍与市场规模"',
        '★新增模块 供需分析（发现报告素材）': '"title":"供需格局与平衡表"',
        # ---- 模块移位（2026-09-20 下午 · 用户：「m24 移到公司营收的 m11 下面」）----
        #    ⚠️ toc 的 JSON 键序是 **text 在前、anchor 在后**（不是 anchor 在前），
        #       拼探针串时别按直觉写反了。移位后「公司投资」「公司链条」的锚点各 +1。
        '★移位后 m12 = 产品价格与成本': '"no":"12","title":"产品价格与成本"',
        '★目录锚点 公司投资 → m17（顺延）': '"text":"公司投资","anchor":"m17"',
        # ⚠️ 2026-09-20 17:44 修正：风险矩阵已还原为 m19（归回「公司投资」段尾），
        #    公司链条段首变回 m20。此前这条钉的是 m19（合并后顺延），已不再成立。
        '★目录锚点 公司链条 → m20（修正后）': '"text":"公司链条","anchor":"m20"',
        # ---- 模块合并（2026-09-20 傍晚 · 用户：「m19 并入 m25，在 m25 下方加入」）----
        #    ⚠️ 用户原意指的 m19 是 **「行业总览与市场空间」**（他页面上的编号），
        #       而移位后库里 m19 恰好是「风险矩阵」—— 第一版并错了对象，
        #       17:44 已按合并前快照还原并重做（`build/fix_merge_600456.py`）。
        #    最终态（31 → 30 个模块，首份非 31 的研报 —— 别再按 31 写死）：
        #      · m19 = 风险矩阵（**还原**，归回「公司投资」段尾）
        #      · m24 = 钛行业介绍与市场规模（含并入的「行业总览与市场空间」整节）
        #      · 「公司链条」锚点 m20；「行业分析 / 供需分析 / 盈利预测 / 企业评分」各 −1
        '★合并后 m24 = 钛行业介绍与市场规模': '"no":"24","title":"钛行业介绍与市场规模"',
        '★目录锚点 行业分析 → m24（合并后顺延）': '"text":"行业分析","anchor":"m24"',
        '★m19 已还原为风险矩阵（未并入）': '"no":"19","title":"风险矩阵"',
        '★m24 并入「行业总览与市场空间」': '<h3>行业总览与市场空间</h3>',
        '★风险矩阵 5 张风险卡仍在（现 m19）': '① 可转债募投项目达产不及预期',
        # ---- 毛利构成图（2026-09-20 17:28 并发会话/用户自助加入 m11）----
        #    ★ 这条是为了防止未来某次全量同步/构建把它丢掉；看图见「产品收入结构」右侧。
        '★m11 毛利构成图 chartGrossMix': 'chartGrossMix',
        # ---- 新增模块 m25「产量储量分布及价格分析」（2026-09-20 傍晚 · 用户给 4 份 xlsx
        #      + iFinD MCP 补齐国内分省储量与攀枝花矿价）----
        #    ⚠️ 插在 m25 位置 ⇒ 原 m25..m30 整体顺延为 m26..m31；toc 里
        #       「供需分析 / 盈利预测 / 企业评分」锚点各 +1（「行业分析」仍是 m24 不动）。
        #       这几条同时盯两件事：再构建时被模板回退、库改了但 seed 没同步。
        '★新增模块 m25 = 产量储量分布及价格分析': '"no":"25","title":"产量储量分布及价格分析"',
        '★m25 图①全球储量地图 chartTiWorldMap': 'chartTiWorldMap',
        '★m25 图②储量vs产量占比 chartTiShare': 'chartTiShare',
        '★m25 图③中国分省储量 chartTiCNProv': 'chartTiCNProv',
        '★m25 图④攀枝花钛矿价格 chartTiPrice': 'chartTiPrice',
        '★顺延后 toc 供需分析 → m26': '"text":"供需分析","anchor":"m26"',
        '★顺延后 toc 盈利预测 → m27': '"text":"盈利预测","anchor":"m27"',
        '★顺延后 toc 企业评分 → m29': '"text":"企业评分","anchor":"m29"',
        # ---- 合规世界地图（2026-09-20 · build/lib/world-cn.js 注入）----
        #    ⚠️ ECharts 官方 world（Natural Earth）的中国画法**不合国标**：台湾未并入、
        #       藏南划给印度、无九段线 —— 直接用会踩地图合规红线。
        #       现已换成 DataV 100000_full 国标数据重建的 China feature。
        #       这条只做「占位符注入成功」的粗判，几何层面的硬校验在文末 [6] 段。
        '★合规世界地图 注册 worldcn': "echarts.registerMap('worldcn'",
        # ---- 地图「可自由缩放」+ 中国储量分布图（2026-09-20 傍晚 · 用户：
        #      「样式做好看一点，下面加一张中国储量分布图，改成可自由缩放的那种」）----
        #    ⚠️ 这几条盯的是渲染层（模板）与数据层（库 opt）**两侧**：
        #       · roam / scaleLimit 由模板的地图分支注入（库 opt 里也各写一份兜底）
        #       · scaleLimit 是必填 —— 默认 zoomLimit=null ⇒ 缩放无上下界，滚轮几下就飞走
        #       · .rpt-mapguide 是「滚轮缩放/拖动平移/双击复位」提示条
        '★地图判据 isMapChart': 'function isMapChart(opt){',
        '★地图取系列 mapSeriesOf': 'function mapSeriesOf(opt){',
        '★地图缩放 roam 兜底': 'if(mser.roam === undefined) mser.roam = true;',
        '★地图缩放 scaleLimit 兜底': 'if(!mser.scaleLimit) mser.scaleLimit = { min: 1, max: 12 };',
        '★地图提示条 容器': "mg.className = 'rpt-mapguide';",
        '★地图提示条 文案': '滚轮 <b>缩放</b>',
        '★地图双击复位': 'mg.ondblclick = mg.onclick;',
        '★中国地图世界槽位 chartTiCNMap': 'chartTiCNMap',
        '★国标中国省级地图 注册 china': "echarts.registerMap('china'",
        '★浅底纹专用 btTintKeep': 'function btTintKeep(c){',
        '★m25 新增中国储量图图注': '本图为<b>中国原生钛铁矿（TiO₂）资源储量分布</b>',
        # ---- m25 两张储量地图第三轮改版（2026-09-20 晚，用户给了四张截图）----
        # ⚠️⚠️ 探针特征串**绝不跨行**：线上 report.html 是 CRLF、本地 css 是 LF，
        #    键里带 \n 会「本地绿、线上红」假红。只用同行连续片段或 `{` 结尾。
        # ① 令牌安全网：认不出的 {{fn:}} 令牌返回空串，绝不泄漏成可见文字
        '★令牌安全网 认不出返空串': "if(m) return '';",
        '★令牌安全网 半截令牌也拦': "if(node.indexOf('{{') >= 0) return '';",
        # ② 地图 tooltip 走函数（世界=中文名+占比，中国=三段式）
        '★世界地图 tooltip 函数 mapTip': 'mapTip: function(a, opt){',
        '★中国地图 tooltip 函数 mapCnTip': 'mapCnTip: function(a, opt){',
        #    地图 tooltip 的数值「归一化」（标量 / 三元数组两种 data 形态都能取）
        '★地图 tooltip 数值归一化': 'function numOf(d){',
        # ③ 地图按数据分档上色：beauty 见到 ≥2 种 areaColor 就整段跳过归一
        '★地图分档上色 免归一判据': 'var tiered = Object.keys(areaSet).length >= 2;',
        # ④ 装饰性 scatter（全透明标注层）不被刷成数据系列
        '★装饰图层 免上色判据': "return parts.length > 3 && parseFloat(parts[3]) < 0.06;",
        # ⑤ 中国地图从气泡改区域铺色后，槽位仍在（防重排丢图）
        '★m25 中国地图新图注': '中国原生钛铁矿储量分布',
        # ---- 目录不再显示「第X篇」前缀 · 文案统一 4 字并居中（2026-09-16）----
        '★目录剥「第X篇」前缀 tocLabel': 'function tocLabel(s){',
        '★目录条目居中（四字文案）': 'text-align:center;white-space:nowrap;overflow:hidden',
        '★编辑面板保存也剥前缀': 'text:tocLabel(s)',
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
    'market-history.html': {
        '页面标题': '中国股市牛熊全史',
        '全景走势图容器 chartAll': 'id="chartAll"',
        '二十九轮总览': '二十九轮',
        '逐轮复盘注解': '复盘注解',
        '制度大事记': '制度大事记',
        '术语注解表': '术语注解',
        '幅度刻度口径（非线性压缩）': '非线性压缩',
        '纵轴对数刻度': '对数刻度',
        '免责声明': '免责声明',
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
        print('    deliver 副本已刷新 → %s' % md5b(desk))
    print('    deliver %-13s %s  %d 字节' % (deskname, md5b(desk), len(desk)))
    print('    deliver == 本机：%s' % ('✅' if md5b(desk) == md5b(local) else '❌'))

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
    print('%-14s 线上一致 %s · deliver 一致 %s · 特征串 %s · 无明文密码 %s'
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

# ---------------------------------------------------------------------------
# [5] 首页文档：域名根 / 必须就是工作台
#     —— 踩过的坑（2026-09-16）：托管 IndexDocument 曾指向 index_GS.html（**另一个应用**
#        「市场研究工作站 · 历史档期版」），于是用户访问域名根拿到的是那个应用，
#        而上面 [1] 只比对三个「显式文件名」，这个盲区一直没被发现 —— 用户写复盘
#        「点灰底丢稿」时才发现他打开的根本不是这一版。
#        根路径直接比 md5，等价于校验首页文档配置；CDN 可能脏读，所以带 cache-buster。
# ---------------------------------------------------------------------------
print()
print('=' * 66)
print('【首页文档】域名根 / 是否直达工作台（防 IndexDocument 指向别的应用）')
print('=' * 66)
root_ok = False
try:
    rb = get('%s/?t=%d' % (DOM, int(time.time())))
    rt = rb.decode('utf-8', 'replace')
    rti = re.search(r'<title>(.*?)</title>', rt, re.S)
    lc = open(BASE + r'\deploy\index.html', 'rb').read()
    root_ok = (md5b(rb) == md5b(lc))
    print('    域名根 /            %s  %d 字节' % (md5b(rb), len(rb)))
    print('    deploy/index.html   %s  %d 字节' % (md5b(lc), len(lc)))
    print('    title              : %s' % (rti.group(1).strip()[:60] if rti else '?'))
    print('    根 == 工作台        : %s' % ('✅' if root_ok else '❌ 首页文档可能仍指向别的文件'))
except Exception as e:
    print('    ❌ 抓根路径失败：%s' % e)

# 改首页文档不该删掉同目录下的其它应用 —— 存活哨兵
print('    —— 同目录其它应用存活检查（不应受影响）——')
ALIVE = [('index_GS.html', '市场研究工作站')]
for f, want in ALIVE:
    try:
        ab = get('%s/%s' % (DOM, f))
        at = ab.decode('utf-8', 'replace')
        print('    %s %-16s %8d 字节 · title 含「%s」：%s'
              % ('✅' if want in at else '⚠️', f, len(ab), want, want in at))
    except Exception as e:
        print('    ⚠️ %-16s 取不到（%s）' % (f, e))

print()
print('=' * 66)
print('【合规世界地图】线上产物里注册的 worldcn 几何是否为国标口径')
print('=' * 66)
# 为什么单独查：ECharts 官方 world 数据的中国版图不合国标（台湾未并入、藏南划给印度、
# 无九段线）。字符串探针只能证明「注入过」，证明不了「几何是对的」。这里把线上
# report.html 里的 GeoJSON 抠出来，直接量几何：features 数、China 是否压在最末、
# 经纬度包络是否下探到 3.4°N（九段线）、面片数是否够（含南海诸岛）。
import json as _json
geo_ok = False
try:
    rt = get('%s/report.html' % DOM).decode('utf-8', 'replace')
    gi = rt.find("echarts.registerMap('worldcn'")
    gj = rt.find('{', rt.find(',', gi))
    geo = _json.JSONDecoder().raw_decode(rt[gj:])[0]
    feats = geo['features']
    names = [f['properties'].get('name') for f in feats]
    ci = names.index('China') if 'China' in names else -1
    gg = feats[ci]['geometry'] if ci >= 0 else None
    polys = len(gg['coordinates']) if gg and gg['type'] == 'MultiPolygon' else 0
    xs, ys = [], []
    stack = [gg['coordinates']] if gg else []
    while stack:
        c = stack.pop()
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1])
        elif c:
            stack.extend(c)
    s_min, s_max = (round(min(ys), 2), round(max(ys), 2)) if ys else (0, 0)
    print('    features            %d（官方 world 为 216 + 自己补的 China = 217）' % len(feats))
    print('    China 位置          %d / %d %s'
          % (ci, len(names) - 1, '✅ 压在最末（最后绘制，盖住印度在藏南的着色）'
             if ci == len(names) - 1 else '❌ 不在末尾 ⇒ 藏南可能被印度着色盖住'))
    print('    China 面片 / 点     %d 面 / %d 点（≥250 面才含南海诸岛与九段线）' % (polys, len(xs)))
    print('    China 纬度包络      %.2f°N ~ %.2f°N %s'
          % (s_min, s_max, '✅ 下探到南海九段线' if s_min < 5 else '❌ 没到南海 ⇒ 九段线缺失'))
    print('    独立 Taiwan feature : %s（须为无 —— 台湾须并入 China）'
          % ('❌ 存在！' if 'Taiwan' in names else '无 ✅'))
    geo_ok = (len(feats) == 217 and ci == len(names) - 1 and polys >= 250 and s_min < 5
              and 'Taiwan' not in names)
    print('    判定                : %s' % ('✅ 合规' if geo_ok else '❌ 不合规'))
except Exception as e:
    print('    ❌ 抠取 worldcn 几何失败：%s' % e)

print()
print('=' * 66)
print('【国标中国省级地图 + 可自由缩放】线上注册的 china 几何与两张地图的 roam 配置')
print('=' * 66)
# 为什么单独查：
#   ① registerMap('china') 是 2026-09-20 新增的（m25 中国储量分布图用它当底图）。
#      省界若缺台湾/香港/澳门，或丢了南海诸岛与九段线，就是合规问题 —— 字符串探针
#      只能证明「调用过 registerMap」，证明不了「35 个面片齐、含九段线」。
#   ② roam / scaleLimit 是「可自由缩放」的命门。且 scaleLimit 必须是**有限区间**：
#      ECharts 默认 null ⇒ 缩放无上下界，滚轮几下地图就飞出画布再也找不回来。
#      这里把线上两图的 opt 抠出来，直接断言 roam===true 且 scaleLimit 有 min/max。
cn_ok = roam_ok = False
try:
    rt2 = get('%s/report.html' % DOM).decode('utf-8', 'replace')
    ci2 = rt2.find("echarts.registerMap('china'")
    cj = rt2.find('{', rt2.find(',', ci2))
    cn = _json.JSONDecoder().raw_decode(rt2[cj:])[0]
    cf = cn['features']
    cnames = [f['properties'].get('name') for f in cf]
    has = lambda n: n in cnames
    # 九段线 feature 的 adcode 以 100000_JD 结尾
    jd = [f for f in cf if str(f['properties'].get('adcode') or '').endswith('_JD')]
    ys2 = []
    for f in jd:
        stack = [f['geometry']['coordinates']]
        while stack:
            c = stack.pop()
            if c and isinstance(c[0], (int, float)):
                ys2.append(c[1])
            elif c:
                stack.extend(c)
    s_min2 = round(min(ys2), 2) if ys2 else 99
    need = ['北京', '四川', '新疆', '台湾', '中国香港', '中国澳门']
    miss = [n for n in need if not has(n)]
    print('    中国省级 features   %d（34 省级 + 南海诸岛 = 35）' % len(cf))
    print('    关键面片齐全        %s%s'
          % ('✅' if not miss else '❌ 缺 ' + ','.join(miss),
             '' if not miss else ''))
    print('    九段线 feature      %d 个 · 纬度下探 %.2f°N %s'
          % (len(jd), s_min2, '✅ 含九段线' if s_min2 < 5 else '❌ 九段线缺失'))
    cn_ok = (len(cf) == 35 and not miss and s_min2 < 5)
    print('    判定                : %s' % ('✅ 合规' if cn_ok else '❌ 不合规'))

    # ---- 两图 roam / scaleLimit 硬断言（从线上 seed 里抠 opt）----
    # ★★ 架构变更（2026-09-20 晚）：roam/scaleLimit 从 **geo** 搬到了 **map series**。
    #    原因：geo 一旦被 series 用 geoIndex 引用，区域填充权就归 geo，
    #    data[].itemStyle.areaColor 全部失效（12 国全是灰的根因）。
    #    ⇒ 现在 map series **不带 geoIndex**、自己铺满绘图区并自带 roam/scaleLimit；
    #      geo 退化为「透明、silent 的 scatter 坐标锚点」，roam=False 是**有意为之**
    #      （锚点跟着 series 走，自己再开 roam 只会两层错位）。
    #    所以断言改为：**map series** 必须有 roam=True + 有限 scaleLimit。
    sd = _json.JSONDecoder().raw_decode(
        rt2[rt2.find('{', rt2.find('window.RPT_SEED')):])[0]
    charts = sd.get('charts') or {}
    if isinstance(charts, list):
        charts = {c.get('id') or c.get('chart_id'): c for c in charts}
    for ck in ('chartTiWorldMap', 'chartTiCNMap'):
        rec = charts.get('600456_' + ck) or charts.get(ck)
        if not rec:
            print('    %-18s ❌ 线上 seed 里找不到这张图' % ck); continue
        o = rec.get('opt') or {}
        g = o.get('geo') or {}
        sm = None
        for s in (o.get('series') or []):
            if s.get('type') == 'map':
                sm = s
        if not sm:
            print('    %-18s ❌ 找不到 map series' % ck); continue
        sl = sm.get('scaleLimit') or {}
        ok = (sm.get('roam') is True and sl.get('min') is not None
              and sl.get('max') is not None and sl['max'] > 1)
        # 反面断言：map series **不能**带 geoIndex（带了 region 填色就失效）
        no_geo_idx = sm.get('geoIndex') is None
        ok = ok and no_geo_idx
        # 且 data 里必须真的有多档 areaColor（证明「按数据上色」而不是被统一刷灰）
        tiers = set()
        for d in (sm.get('data') or []):
            it = (d or {}).get('itemStyle') or {}
            if isinstance(it.get('areaColor'), str):
                tiers.add(it['areaColor'])
        ok = ok and len(tiers) >= 2
        roam_ok = ok if ck == 'chartTiWorldMap' else (roam_ok and ok)
        print('    %-18s series.roam=%-5s scaleLimit=%-10s geoIndex=%-4s 色档=%d %s'
              % (ck, sm.get('roam'),
                 ('{%s..%s}' % (sl.get('min'), sl.get('max'))) if sl else 'None',
                 sm.get('geoIndex'), len(tiers),
                 '✅' if ok else '❌'))
    print('    判定                : %s'
          % ('✅ 两图均可自由缩放（series.roam + 有限 scaleLimit）且按数据分档上色'
             if roam_ok else '❌ 缩放/上色未就位'))
except Exception as e:
    print('    ❌ 校验中国地图 / roam 失败：%s' % e)

print()
print('结论：' + ('全部通过 ✅' if allok and fresh_ok and root_ok and geo_ok and cn_ok and roam_ok
              else '有项目不通过 ❌'))
print('=' * 66)
