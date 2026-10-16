# -*- coding: utf-8 -*-
"""研报页「📂 公司资料库」端到端探针（2026-10-14）

用法：
  # 只读部分：开弹层 / 列表 / 空态 / 搜索框（不写任何数据）
  python3 build/probe_comfiles.py
  # 完整链路：真上传 5 种格式 → 逐个真预览 → 逐个真删除（管理员密码门）
  WB_PW=981208 python3 build/probe_comfiles.py --full

⚠️ 关于「探针不许写生产表」：
   --full 会真的往存储桶和 wb_company_files 写数据 —— 上传/删除本来就没法只读验证。
   所以整个探针跑在 **report_id = `__probe__`** 这个命名空间里（页面用 `?code=__probe__`
   打开，云端没有这份研报，走内置副本兜底，St.code 仍是 __probe__），
   真实研报的资料柜一行都不会碰到。
   ⚠️ 表只授了 SELECT/INSERT/UPDATE（没有 DELETE，删除一律软删），所以 `__probe__` 里
   会攒下历次运行的软删记录 —— 对象审计用「本次启动时刻」圈定本次的 5 条，不会被历史干扰。
   要硬清干净：DELETE FROM public.wb_company_files WHERE report_id='__probe__';
   （另：桶里 __probe__/ 下的对象也会留下，需要时用存储接口逐个删。）

为什么必须走真实时间（Popen + 轮询）而不是 --virtual-time-budget：
  上传要真的发 HTTP、密码要真的去云端校验，虚拟时间不会等这些 I/O。

★ 关于 PDF：headless 的 Edge/Chromium **不加载 PDF 阅读器组件**，iframe 里永远是一片深灰
   （拿合法 PDF + 无参数版本 + 直接导航三种方式做过对照，结果一致；试过 PdfOopif 等开关也无效）。
   所以 PDF 的验收**不靠截图**，而是：
     a) iframe 的 src 以 #view=FitH 结尾 + 底下那条降级提示条存在；
     b) 在 HTTP 层验对象本体可服务（HEAD 200 + application/pdf + Content-Length 对得上）。

做什么：
  1. 顶部操作条里找得到「📂 公司资料库」按钮，点开弹层（标题/公司名/搜索框/上传按钮齐备）
  2. 列表读完后是空态（__probe__ 从来没放过东西）
  3. 【--full】用 DataTransfer 造 5 个不同格式的 File 塞进 #fInput 并派发真实 change 事件
     （＝用户多选文件的真实路径，不直接调 Rpt.fUp）
  4. 【--full】弹管理员密码门 → 填账号密码 → 点确认 → 5 条进度条全部跑到 ✓ 完成
  5. 【--full】列表 5 行：类型徽标 / 图标底色 / 大小 / 时间 / 三个按钮 逐项核对
  6. 【--full】逐行点「👁 查看」，按 pv 字段核对走对分支：
       txt→<pre> 且正文逐字一致、csv→<pre> 且正文一致、img→<img naturalWidth>0
       （1×1 PNG，真的解码出来才算过）、pdf→<iframe #view=FitH> + 降级提示条、
       docx→「浏览器不能内嵌预览」提示块
  7. 【--full】逐行点「🗑」→ 每次都要过 danger 密码门 → 5 次删完列表清空
  8. HTTP 层审计（不依赖浏览器）：回读本次 5 条记录，逐个 HEAD/GET 对象本体，
     比对 Content-Length 与库里的 size_bytes，并确认 PNG 下载回来仍是合法 PNG 头
"""
import io, json, os, socket, subprocess, sys, tempfile, threading, time
import urllib.request, urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOT = []
SRC = os.environ.get('RPT_SRC') or os.path.join(ROOT, "deploy", "report.html")
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
CODE = '__probe__'          # ★ 测试命名空间：不碰任何真实研报
PW = os.environ.get('WB_PW', '')
USER = os.environ.get('WB_USER', 'luoshui')

# ── 测试素材规格：**单一来源**，同时喂给页内 JS（__FILES__）与下面的断言 ──────
#    kind/badge = 列表里应该显示的类型徽标；pmeta = 预览底栏的类型文案（CSV 会显示成 CSV
#    而不是 Excel —— 徽标说「用什么软件打开」，底栏说「这是什么」）；pv = fView 应走的预览分支：
#      pre    → <pre id="vTxt">（纯文本 / CSV 都走这条）
#      img    → <img>（要 naturalWidth>0 才算真解码出来）
#      iframe → <iframe>（PDF）+ 底下那条降级提示 .vhint
#      nopv   → 「浏览器不能内嵌预览」提示块
# ⚠️ PDF 内容**不**在截图里验（headless 无 PDF 阅读器，见文件头说明）⇒ 走功能性断言：
#    iframe 的 src 必须以 #view=FitH 结尾，且该地址 HEAD 回来是 200 + application/pdf。
PDF_BODY = ('%PDF-1.4\n'
            '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
            '2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n'
            'trailer\n<< /Size 3 /Root 1 0 R >>\n%%EOF\n')
FILES = [
    dict(nm='探针文件.txt', type='text/plain', kind='txt', badge='文本', pmeta='文本', pv='pre',
         mode='prefix', match='ABComfilesProbe-2026-10-14',
         body='ABComfilesProbe-2026-10-14\n' + 'x' * 1199),
    dict(nm='探针表.csv', type='text/csv', kind='csv', badge='Excel', pmeta='CSV', pv='pre',
         mode='contains', match='宝钛股份,600456,24.6',
         body='name,code,pe\n宝钛股份,600456,24.6\n西部超导,688122,38.4\n'),
    # 1×1 透明 PNG 的真实字节（浏览器解得出来 ⇒ naturalWidth 会是 1）
    dict(nm='探针图.png', type='image/png', kind='img', badge='图片', pmeta='图片', pv='img',
         b64='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='),
    dict(nm='探针档.pdf', type='application/pdf', kind='pdf', badge='PDF', pmeta='PDF', pv='iframe',
         body=PDF_BODY),
    dict(nm='探针稿.docx', kind='doc', badge='Word', pmeta='Word', pv='nopv',
         type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         body='PK\x03\x04fake-docx'),
]
DOCX_EXT = 'docx'
RUN_T0 = None       # 本次运行启动时刻（UTC），audit_objects 用它圈出「本次」的记录

INJECT = r"""
<script>
(function(){
  var out = {steps:[], t:0};
  var PW = '__PW__', USER = '__USER__';
  var TICK = 180;
  function log(s){ out.steps.push(s); }
  function post(){
    out.ms = Date.now() - out.t0;
    try{ fetch('/m', {method:'POST', body: JSON.stringify(out)}); }catch(e){}
  }
  function statText(){
    var e = document.getElementById('fStat');
    return e ? String(e.textContent || '') : '';
  }
  function wait(cond, ms, ok, errMsg){
    var t0 = Date.now();
    (function tick(){
      var v = false;
      try{ v = cond(); }catch(e){}
      if(v){ ok(); return; }
      if(Date.now() - t0 > ms){ out.err = errMsg || '超时'; post(); return; }
      setTimeout(tick, TICK);
    })();
  }
  function go(){
    out.t0 = Date.now();
    if(!(window.St && St.code)){ return setTimeout(go, 250); }
    var bar = document.getElementById('rbar');
    if(!bar || !bar.querySelector('.rbtn')) return setTimeout(go, 250);
    setTimeout(s1_open, 400);
  }
  /* 1. 顶部按钮 → 弹层 */
  function s1_open(){
    var btns = document.querySelectorAll('#rbar .rbtn');
    var hit = null;
    for(var i=0;i<btns.length;i++) if(btns[i].textContent.indexOf('公司资料库') >= 0) hit = btns[i];
    out.btnCount = btns.length;
    out.btnText = hit ? hit.textContent.trim() : '';
    if(!hit){ out.err = '顶部操作条里找不到「公司资料库」按钮'; return post(); }
    hit.click();
    wait(function(){ return document.querySelector('#rptFMask.on .rpt-fbox'); }, 8000, s2_shell, '弹层没打开');
  }
  /* 2. 弹层骨架 */
  function s2_shell(){
    out.opened = true;
    out.title = (document.querySelector('.rpt-fbox .hd .t') || {}).textContent || '';
    out.co    = (document.querySelector('.rpt-fbox .hd .co') || {}).textContent || '';
    out.hasSearch   = !!document.getElementById('fQ');
    out.hasUpload   = !!(document.querySelector('.rpt-fbox .bar .rbtn.pri'));
    out.hasFileInput= !!document.getElementById('fInput');
    out.multiple    = !!(document.getElementById('fInput') || {}).multiple;
    out.uploadTip   = (document.querySelector('.rpt-fbox .bar .tip') || {}).textContent || '';
    out.footHint    = (document.querySelector('.rpt-fbox .ft .hint') || {}).textContent || '';
    /* ⚠️ 判据不能用「#fStat 不再是读取中」—— 读取失败时 fStat 会被清成空串（falsy），
       那样等待永远等不到。改判「列表区出现 .fempty 或 .fl」，两条路都算读完。 */
    wait(function(){ return document.querySelector('#fBody .fempty, #fBody .fl'); },
         12000, s3_empty, '列表一直没读完（12s）');
  }
  /* 3. 空态 */
  function s3_empty(){
    out.stat0 = statText();
    /* ★ 统计胶囊：空柜/读失败时 fStat('') 只清文字，胶囊本身会剩一圈空红边（像渲染坏了）。
       CSS 用 `.rpt-fbox .hd .stat:empty{display:none}` 整枚收掉 ⇒ 这里量 computed display，
       断言「无文字 ⇒ display=none」。量 computed 而不是 offsetWidth，是为了不依赖字体/缩放。 */
    var _se = document.querySelector('.rpt-fbox .hd .stat');
    out.statDisp0 = _se ? getComputedStyle(_se).display : '(缺)';
    out.empty0 = !!document.querySelector('.fempty');
    out.emptyText0 = (document.querySelector('.fempty') || {}).textContent || '';
    out.rows0 = document.querySelectorAll('.fl').length;
    out.rptErr = (window.__RPT_ERR || []).join(' | ').slice(0, 300);
    out.loadErr = (window.St && St.loadErr) ? String(St.loadErr).slice(0, 200) : '';
    if(!__FULL__){ return post(); }
    s4_upload();
  }
  /* 4. 上传（DataTransfer + 真实 change 事件，等价于用户选文件）
        ★ 一次选 5 种格式：既验「多选」，也把 fView 的 5 条分支都走到
          （txt / csv→文本 / img / pdf / Office→不能预览提示）。
          素材规格由 Python 侧 __FILES__ 注入，**单一来源** —— 断言也用同一份。 */
  var CASES = __FILES__;
  /* ⚠️ 二进制素材必须给 Uint8Array，**不能**直接喂 atob() 出来的字符串：
     File 构造器对字符串按 UTF-8 编码，>0x7F 的字节会被撑成 2~3 字节 ⇒ 图片/PDF 静默损坏
     （踩过：1×1 PNG 68B 变成 82B，img.naturalWidth 永远是 0）。 */
  function bodyOf(c){
    if(!c.b64) return c.body;
    var s = atob(c.b64), u = new Uint8Array(s.length);
    for(var i=0;i<s.length;i++) u[i] = s.charCodeAt(i) & 255;
    return u;
  }
  function s4_upload(){
    var dt = new DataTransfer();
    for(var i=0;i<CASES.length;i++){
      dt.items.add(new File([bodyOf(CASES[i])], CASES[i].nm, {type: CASES[i].type}));
    }
    out.upNames = CASES.map(function(c){ return c.nm; });
    var inp = document.getElementById('fInput');
    inp.files = dt.files;
    out.inpFiles = inp.files.length;
    inp.dispatchEvent(new Event('change', {bubbles: true}));
    wait(function(){ return document.getElementById('rptPBox') || document.querySelector('.fqueue'); },
         12000, s5_gate, '点了上传却没有密码门也没有进度条');
  }
  /* 5. 密码门 */
  function sample(){
    var box = document.getElementById('rptPBox');
    var go = box ? box.querySelector('#rpGo') : null;
    return {b: box ? 1 : 0, go: go ? String(go.textContent) : '',
            dis: go ? !!go.disabled : null,
            err: (document.getElementById('rpErr') || {}).textContent || '',
            pg: document.querySelectorAll('.fprog').length,
            q: document.querySelectorAll('.fqueue').length,
            bk: (document.getElementById('fBody') || {children: []}).children.length,
            je: (window.__RPT_ERR || []).slice(-2).join(' ; ').slice(0, 180)};
  }
  function s5_gate(){
    var box = document.getElementById('rptPBox');
    out.gate1 = !!box;
    if(box){
      out.gate1Act = (box.querySelector('#rpGo') || {}).textContent || '';
      out.gate1Danger = /不可撤销/.test(box.textContent || '');
      out.gate1Keep = !!box.querySelector('#rpKeep');
      var u = box.querySelector('#rpUser'); if(u) u.value = USER;
      box.querySelector('#rpPass').value = PW;
      box.querySelector('#rpGo').click();
    }
    out.diag = [];
    var t0 = Date.now();
    (function tick(){
      var s = sample();
      if(out.diag.length < 26) out.diag.push(s);
      /* ① 5 条进度条**全部**跑出终态（✓/✕）才继续 —— 再往后列表刷新会连队列一起重建，采不到了；
         ② 记到之后再等 1.2s 让 fLoad 把新文件刷进列表，然后进下一步。
         ⚠️ 之前直接判「出现 .fprog 就进下一步」是错的：那会儿 st 还是「上传中」，
            会拿到假红；而判「等 .fprog.ok」又会因为刷新太快而永远等不到（fLoad 重建列表区）。 */
      var all = document.querySelectorAll('.fprog');
      var pend = document.querySelectorAll('.fprog:not(.ok):not(.bad)');
      if(all.length >= CASES.length && pend.length === 0){
        out.okSeen = (out.okSeen || 0) + 1;
        if(out.okSeen === 1){ s6_uploaded(); }
        return;
      }
      if(Date.now() - t0 > 60000){
        out.err = '点了「确认上传」后 60s 内还有 ' + pend.length + ' 条进度条没跑完（共 ' +
                  all.length + ' 条）';
        out.diag.push({tail: 1});
        post(); return;
      }
      setTimeout(tick, 300);
    })();
  }
  /* 6. 上传结果 */
  function s6_uploaded(){
    out.prog = [].slice.call(document.querySelectorAll('.fprog')).map(function(el){
      return {nm: (el.querySelector('.nm')||{}).textContent||'',
              st: (el.querySelector('.st')||{}).textContent||''};
    });
    out.gate1Err = (document.getElementById('rpErr') || {}).textContent || '';
    wait(function(){ return statText().indexOf('个文件') >= 0; }, 25000, s7_list, '上传后列表没刷新');
  }
  /* 7. 列表内容 */
  function s7_list(){
    var els = document.querySelectorAll('.fl');
    out.stat1 = statText();
    /* 反向：有文件时胶囊必须**看得见** —— 免得 `:empty` 规则写宽了把有内容的一起收掉。 */
    var _se1 = document.querySelector('.rpt-fbox .hd .stat');
    out.statDisp1 = _se1 ? getComputedStyle(_se1).display : '(缺)';
    out.rowCount = els.length;
    out.rows = [].slice.call(els).map(function(el){
      return {n: (el.querySelector('.fn')||{}).textContent||'',
              k: (el.querySelector('.fk')||{}).textContent||'',
              s: (el.querySelector('.fs')||{}).textContent||'',
              d: (el.querySelector('.fd')||{}).textContent||'',
              ico: (el.querySelector('.fi')||{}).textContent||'',
              icoCls: (el.querySelector('.fi')||{}).className||'',
              btns: [].slice.call(el.querySelectorAll('.fo .ib')).map(function(b){ return b.textContent.trim(); })};
    });
    /* 搜索过滤也顺手验一下（不该误伤） */
    var q = document.getElementById('fQ');
    if(q){ q.value = '探针'; q.dispatchEvent(new Event('input', {bubbles: true})); }
    out.searchHit = document.querySelectorAll('.fl').length;
    if(q){ q.value = 'zzz-不存在'; q.dispatchEvent(new Event('input', {bubbles: true})); }
    out.searchMiss = document.querySelectorAll('.fl').length;
    out.searchEmpty = !!document.querySelector('.fempty');
    if(q){ q.value = ''; q.dispatchEvent(new Event('input', {bubbles: true})); }
    var v = document.querySelector('.fl .fo .ib');
    out.viewBtn = v ? v.textContent.trim() : '';
    out.pv = []; pvI = 0;
    s8_next();
  }
  /* ---------- 预览分支遍历：按文件名逐个点「👁 查看」 ---------- */
  var pvI = 0;
  function rowByName(nm){
    var els = document.querySelectorAll('.fl');
    for(var i=0;i<els.length;i++){
      var t = (els[i].querySelector('.fn') || {}).textContent || '';
      if(t === nm) return els[i];
    }
    return null;
  }
  function s8_next(){
    if(pvI >= CASES.length){ document.getElementById('fQ').value = '';
                             return s10_del(); }
    var c = CASES[pvI];
    var row = rowByName(c.nm);
    if(!row){
      out.pv.push({nm:c.nm, miss:1});
      pvI++; return s8_next();
    }
    row.querySelector('.fo .ib').click();
    wait(function(){ return document.querySelector('#rptVMask.on .rpt-vbox'); },
         8000, s9_probe, '预览没打开：' + c.nm);
  }
  function s9_probe(){
    var c = CASES[pvI];
    var rec = {nm:c.nm, kind:c.kind, badge:c.badge,
               meta:(document.querySelector('.rpt-vbox .ft .meta')||{}).textContent||'',
               hasImg:  !!document.querySelector('.rpt-vbox .bd img'),
               hasIfr:  !!document.querySelector('.rpt-vbox .bd iframe'),
               hasPre:  !!document.querySelector('.rpt-vbox .bd pre'),
               hasNoPv: !!document.querySelector('.rpt-vbox .bd .nopv'),
               hasHint: !!document.querySelector('.rpt-vbox .bd .vhint'),
               hint:    (document.querySelector('.rpt-vbox .bd .vhint')||{}).textContent||''};
    var fr = document.querySelector('.rpt-vbox .bd iframe');
    if(fr) rec.src = fr.getAttribute('src') || '';
    /* 各分支有各自的「就绪」判据，跑完才记内容 —— 否则会采到半成品 */
    function ready(){
      if(c.pv === 'img'){
        var im = document.querySelector('.rpt-vbox .bd img');
        return im && im.complete && im.naturalWidth > 0;
      }
      if(c.pv === 'pre'){
        var p = document.getElementById('vTxt');
        return p && String(p.textContent || '').indexOf('读取中') < 0;
      }
      return true;                                  /* iframe / nopv 同步就能判 */
    }
    wait(ready, 12000, function(){
      var im2 = document.querySelector('.rpt-vbox .bd img');
      if(im2){ rec.natW = im2.naturalWidth; rec.natH = im2.naturalHeight; }
      var p = document.getElementById('vTxt');
      if(p){
        var t = String(p.textContent || '');
        rec.pvLen = t.length;
        rec.pvHead = t.slice(0, 34);
        rec.pvMatch = c.mode === 'prefix' ? (t.indexOf(c.match) === 0)
                                          : (t.indexOf(c.match) >= 0);
      }
      rec.dlBtn = !!(document.querySelector('.rpt-vbox .ft .rbtn'));
      out.pv.push(rec);
      pvI++;
      document.querySelector('.rpt-vbox .hd .x').click();
      wait(function(){ return !document.querySelector('#rptVMask.on'); }, 5000, s8_next, '预览关不掉');
    }, '预览内容一直没就绪：' + c.nm);
  }
  /* 9. 删除（danger 门：askPass 对 danger=true **不**走「免重复」短路，每次都会弹）
        5 个文件逐个删掉，顺便确认「删完一个列表立刻少一行」。 */
  var gate2N = 0, delTries = 0;
  function s10_del(){
    if(document.querySelectorAll('.fl').length === 0) return s12_done();
    delTries++;
    var del = document.querySelector('.fl .fo .ib.del');
    out.delBtn = del ? del.textContent.trim() : '';
    if(!del){ out.err = '列表里找不到删除按钮'; return post(); }
    var before = document.querySelectorAll('.fl').length;
    del.click();
    var t0 = Date.now();
    (function tick(){
      var box = document.getElementById('rptPBox');
      if(box){
        gate2N++;
        out.gate2 = true;
        out.gate2Act = (box.querySelector('#rpGo') || {}).textContent || '';
        out.gate2Danger = /不可撤销/.test(box.textContent || '');
        out.gate2UserBox = !!box.querySelector('#rpUser');
        var u = box.querySelector('#rpUser'); if(u) u.value = USER;
        box.querySelector('#rpPass').value = PW;
        box.querySelector('#rpGo').click();
        return s11_delgate(before);
      }
      /* 兜底：万一将来 danger 也允许免重复，删掉了就直接下一轮 */
      if(document.querySelectorAll('.fl').length < before){ s10_del(); return; }
      if(Date.now() - t0 > 9000){
        out.err = '点删除后 9s 既没弹密码门也没减少行数';
        post(); return;
      }
      setTimeout(tick, 220);
    })();
  }
  function s11_delgate(before){
    out.diag2 = out.diag2 || [];
    var t0 = Date.now();
    (function tick(){
      var s = sample();
      s.toast = (document.getElementById('rptToast') || {}).textContent || '';
      s.rows = document.querySelectorAll('.fl').length;
      s.stat = statText();
      if(out.diag2.length < 40) out.diag2.push(s);
      if(s.rows < before){
        if(s.rows === 0){ s12_done(); return; }
        s10_del(); return;
      }
      if(Date.now() - t0 > 25000){
        out.err = '删除确认后 25s 行数没减少（仍 ' + s.rows + ' 行，本轮第 ' + delTries + ' 次）';
        out.diag2.push({tail: 1});
        post(); return;
      }
      setTimeout(tick, 320);
    })();
  }
  function s12_done(){
    out.stat2 = statText();
    out.rows2 = document.querySelectorAll('.fl').length;
    out.empty2 = !!document.querySelector('.fempty');
    out.gate2Count = gate2N;
    out.delTries = delTries;
    post();
  }
  setTimeout(go, 300);
})();
</script>
</body>
"""


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n).decode('utf-8', 'replace')
        try:
            GOT.append(json.loads(body))
        except Exception:
            GOT.append({'raw': body[:300]})
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def inject(html, script):
    i = html.rfind('</body>')
    return html[:i] + script + html[i:]


# ── 下载通道：直接用探头对象的公开地址做 HEAD / GET 比对 ────────────────────
#    页面里「⬇」走的是 fetch(objectUrl) → blob → a[download]（同一条地址），
#    headless 里点下载会触发浏览器下载流程、断言不到 —— 所以改成在 HTTP 层验：
#    HEAD 回来 200 且 Content-Length == 表里的 size_bytes，GET 回来字节数也一致。
CFG = json.load(io.open(os.path.join(ROOT, 'build', 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
STORE = 'https://%s.api.tcloudbasegateway.com/v1/storages/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'User-Agent': 'wb-probe'}


def _req(url, method='GET'):
    return urllib.request.Request(url, headers=HDR, method=method)


def object_url(row):
    from urllib.parse import quote
    key = str(row.get('object_key') or '')
    segs = [quote(s, safe='') for s in key.split('/')]
    return STORE + 'object/' + quote(str(row.get('bucket') or 'company-files'), safe='') + '/' + '/'.join(segs)


def audit_objects(chk, t0):
    """逐个核对：表里的元数据 ↔ 桶里的真实对象（大小、字节数、MIME）。

    ⚠️ 只统计**本次运行**产生的记录（`t >= 本次启动时刻`）：
       __probe__ 里会攒下历次运行的软删记录，不过滤的话「5 条」永远对不上。
       表没有 DELETE 授权（只能软删），硬清要走云端 SQL，见文件头。"""
    from urllib.parse import quote
    try:
        with urllib.request.urlopen(_req(REST + 'wb_company_files?report_id=eq.__probe__'
                                        '&t=gte.' + quote(t0) +
                                        '&select=name,object_key,size_bytes,mime,bucket,is_del&limit=50'),
                                    timeout=30) as r:
            rows = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        chk('回读 __probe__ 记录', False, '查询失败：%s' % str(e)[:80]); return
    name2row = {r.get('name'): r for r in rows}
    chk('本次运行 5 条记录都在（软删后仍在，元数据完整）', len(rows) == len(FILES),
        '拿到 %d 条：%s' % (len(rows), [r.get('name') for r in rows]))
    chk('5 条都已被软删（is_del=true）', all(r.get('is_del') for r in rows),
        '未删：%s' % [r.get('name') for r in rows if not r.get('is_del')])
    for f in FILES:
        row = name2row.get(f['nm'])
        if not row:
            chk('%-14s 元数据' % f['nm'], False, '库里没这条'); continue
        url = object_url(row)
        try:
            with urllib.request.urlopen(_req(url, 'HEAD'), timeout=30) as r:
                clen = int(r.headers.get('Content-Length') or -1)
                ctype = r.headers.get('Content-Type') or ''
                chk('%-14s 对象 HEAD 200' % f['nm'], r.status == 200, 'HTTP %s · %s' % (r.status, ctype))
                chk('%-14s 大小与库一致（%d B）' % (f['nm'], row.get('size_bytes') or 0),
                    clen == (row.get('size_bytes') or 0), 'HEAD 报 %d B' % clen)
                chk('%-14s MIME=%s' % (f['nm'], f['type']), (f['type'].split(';')[0] in ctype or
                    (not ctype)), 'HTTP 回 %r' % ctype)
        except Exception as e:
            chk('%-14s 对象 HEAD 200' % f['nm'], False, '请求失败：%s' % str(e)[:70])
            continue
        # 真下载一次，比对字节数（GET 与 HEAD 都要对得上）
        try:
            with urllib.request.urlopen(_req(url), timeout=60) as r:
                blob = r.read()
            chk('%-14s 下载字节数一致' % f['nm'], len(blob) == (row.get('size_bytes') or 0),
                'GET 拿到 %d B' % len(blob))
            if f['pv'] == 'img':
                chk('%-14s 下载内容仍是合法 PNG' % f['nm'], blob[:8] == b'\x89PNG\r\n\x1a\n',
                    repr(blob[:8]))
        except Exception as e:
            chk('%-14s 下载字节数一致' % f['nm'], False, '下载失败：%s' % str(e)[:70])


def main():
    global RUN_T0
    full = '--full' in sys.argv
    if full and not PW:
        print('✗ --full 需要管理员密码：WB_PW=xxxx python3 build/probe_comfiles.py --full')
        return 2
    html = io.open(SRC, encoding='utf-8').read()
    tmp = tempfile.mkdtemp(prefix='_cf_')
    port = free_port()

    class H(Handler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=tmp, **kw)

    srv = HTTPServer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    js = (INJECT.replace('__PORT__', str(port))
                .replace('__PW__', PW)
                .replace('__USER__', USER)
                .replace('__FILES__', json.dumps(FILES, ensure_ascii=True))
                .replace('__FULL__', 'true' if full else 'false'))
    f = os.path.join(tmp, 'cf.html')
    io.open(f, 'w', encoding='utf-8').write(inject(html, js))
    url = 'http://127.0.0.1:%d/cf.html?code=%s' % (port, CODE)

    print('=' * 100)
    print('公司资料库探针   src=%s   模式=%s   report_id=%s' %
          (os.path.basename(SRC), '完整链路（真上传/真删除）' if full else '只读', CODE))
    print('=' * 100)
    RUN_T0 = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())   # ★ 早于任何上传，圈定本次运行
    p = subprocess.Popen([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-proxy-server',
                          '--window-size=1440,1000', '--user-data-dir=' + tempfile.mkdtemp(prefix='_cfe_'),
                          url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 240 and not GOT:
        time.sleep(0.3)
    p.terminate()
    try:
        p.wait(timeout=10)
    except Exception:
        p.kill()
    srv.shutdown()

    if not GOT:
        print('✗ 页面没有回传结果'); return 1
    m = GOT[0]
    red = []

    def chk(name, ok, detail=''):
        print('  %s %-34s %s' % ('✅' if ok else '❌', name, detail))
        if not ok:
            red.append(name)

    if m.get('err'):
        print('  ⚠️ 中断于：%s' % m['err'])
    if m.get('diag'):
        print('  密码门 / 上传阶段采样（每 0.4s 一条，最多 26 条）：')
        for i, s in enumerate(m['diag']):
            if s.get('tail'):
                print('     …（截断）')
                break
            print('     #%-2d 门=%s 按钮=%-8s 禁用=%-5s 错误=%-22s 进度条=%s 队列=%s 列表子节点=%s %s'
                  % (i, s.get('b'), (s.get('go') or '').replace('\n', ''),
                     s.get('dis'), repr((s.get('err') or '')[:20]),
                     s.get('pg'), s.get('q'), s.get('bk'), s.get('je') or ''))
    if m.get('diag2'):
        print('  删除阶段采样：')
        for i, s in enumerate(m['diag2']):
            if s.get('tail'):
                print('     …（截断）')
                break
            print('     #%-2d 门=%s 按钮=%-8s 禁用=%-5s 错误=%-20s 行数=%s 统计=%-16s toast=%s %s'
                  % (i, s.get('b'), (s.get('go') or '').replace('\n', ''), s.get('dis'),
                     repr((s.get('err') or '')[:18]), s.get('rows'), repr((s.get('stat') or '')[:14]),
                     repr((s.get('toast') or '')[:26]), s.get('je') or ''))
    print('步骤：%s' % ' → '.join(m.get('steps') or []) or '(无)')
    print('-' * 100)
    chk('顶部有「公司资料库」按钮', '公司资料库' in (m.get('btnText') or ''), m.get('btnText'))
    chk('点开后弹层出现', bool(m.get('opened')))
    chk('标题正确', m.get('title') == '📂 公司资料库', repr(m.get('title')))
    chk('公司名占位（__probe__）', bool(m.get('co')), repr(m.get('co')))
    chk('上传按钮 / 多选 input / 搜索框', bool(m.get('hasUpload')) and bool(m.get('hasFileInput')) and bool(m.get('hasSearch')) and bool(m.get('multiple')))
    # ⚠️ 空态有两种：真·空柜（读成功）与「读取失败」（也渲染 .fempty）。
    #    必须按文案区分 —— 否则云端连不上时探针会假绿。
    _et = m.get('emptyText0') or ''
    chk('列表读取完成', bool(m.get('stat0')) or bool(m.get('empty0')),
        '初始统计=%r' % m.get('stat0'))
    chk('读取成功（空柜而非报错）', ('资料柜还是空的' in _et) or (m.get('rows0') or 0) > 0,
        (m.get('rows0') or 0) and ('%s 行' % m.get('rows0')) or _et.strip()[:40])
    # 统计胶囊：有文字就必须看得见；没文字就必须整枚收掉（只剩红边的空壳是回归）。
    # 收掉的实现是 CSS `:empty`，所以基线老页面跑这条会红 —— 属预期，说明该修还没上线。
    _sd = m.get('statDisp0')
    chk('统计胶囊空/非空两态都对（:empty 收掉）',
        (bool(m.get('stat0')) and _sd != 'none') or (not m.get('stat0') and _sd == 'none'),
        'stat=%r display=%s' % (m.get('stat0'), _sd))
    if m.get('rptErr'):
        print('    页面 JS 错误：%s' % m.get('rptErr'))
    if not full:
        print('-' * 100)
        print('（只读模式到此为止；加 --full 跑上传/预览/删除）')
        print('结论：%s' % ('全绿' if not red else ('有 %d 项不过：%s' % (len(red), '、'.join(red)))))
        return 0 if not red else 1

    N = len(FILES)
    chk('起点是空态', bool(m.get('empty0')) and m.get('rows0') == 0,
        '空态文案=%r' % (m.get('emptyText0') or '')[:26])
    chk('change 事件收到 %d 个文件（多选）' % N, m.get('inpFiles') == N, '收到 %s 个' % m.get('inpFiles'))
    chk('上传前弹管理员密码门', bool(m.get('gate1')))
    chk('上传门是「确认上传」非不可逆',
        (m.get('gate1Act') or '').startswith('确认上传') and m.get('gate1Danger') is False,
        '按钮=%r danger=%s' % (m.get('gate1Act'), m.get('gate1Danger')))
    chk('上传门带「15 分钟免重复」勾选', bool(m.get('gate1Keep')))
    chk('密码门没有报错', not (m.get('gate1Err') or '').strip(), 'err=%r' % m.get('gate1Err'))
    prog = m.get('prog') or []
    ok_cnt = len([p for p in prog if '完成' in (p.get('st') or '')])
    chk('进度条全部跑出终态（✓ 完成）', bool(m.get('okSeen')) and ok_cnt == N,
        '✓ %d/%d；采集时残留=%s' % (ok_cnt, N, prog))
    chk('上传后统计出现「个文件」', '个文件' in (m.get('stat1') or ''), m.get('stat1'))
    chk('有文件时统计胶囊仍然看得见（:empty 没写宽）', m.get('statDisp1') not in ('none', '(缺)'),
        'stat=%r display=%s' % (m.get('stat1'), m.get('statDisp1')))

    # ── 列表：每个格式的类型徽标 / 图标底色 / 三个按钮 ────────────────────────
    rows = m.get('rows') or []
    chk('列表出现 %d 行' % N, len(rows) == N, 'rowCount=%s 名称=%s'
        % (m.get('rowCount'), [r.get('n') for r in rows]))
    by_name = {r.get('n'): r for r in rows}
    ICON_OF = {'txt': 'k-txt', 'csv': 'k-xls', 'img': 'k-img', 'pdf': 'k-pdf', 'doc': 'k-doc'}
    for f in FILES:
        r = by_name.get(f['nm'])
        if not r:
            chk('%-14s 出现在列表里' % f['nm'], False, '没找到这一行')
            continue
        chk('%-14s 类型=%s' % (f['nm'], f['badge']), r.get('k') == f['badge'], repr(r.get('k')))
        chk('%-14s 图标底色=%s' % (f['nm'], ICON_OF[f['kind']]), ICON_OF[f['kind']] in (r.get('icoCls') or ''),
            repr(r.get('icoCls')))
        chk('%-14s 三个按钮齐（查看/下载/删除）' % f['nm'], len(r.get('btns') or []) == 3, str(r.get('btns')))
        chk('%-14s 大小已格式化 / 时间已格式化' % f['nm'],
            bool(r.get('s')) and len(r.get('d') or '') == 16 and '-' in (r.get('d') or ''),
            '%s · %s' % (r.get('s'), r.get('d')))
    chk('文件名保留中文原名', all(f['nm'] in by_name for f in FILES),
        '缺：%s' % [f['nm'] for f in FILES if f['nm'] not in by_name])

    chk('搜索「探针」命中 %d 行' % N, m.get('searchHit') == N, '命中=%s' % m.get('searchHit'))
    chk('搜索无结果时显示空态', m.get('searchMiss') == 0 and bool(m.get('searchEmpty')),
        '未命中=%s' % m.get('searchMiss'))

    # ── 预览：逐格式验分支（这是本次功能的重点） ──────────────────────────────
    pv = {p.get('nm'): p for p in (m.get('pv') or [])}
    chk('5 个文件都点开了预览', len(pv) == N, '拿到 %d 条：%s' % (len(pv), list(pv)))
    for f in FILES:
        p = pv.get(f['nm'])
        if not p or p.get('miss'):
            chk('%-14s 预览' % f['nm'], False, '没点开 / 行不存在')
            continue
        tag = '%-14s 预览走 %s 分支' % (f['nm'], {'pre': '文本', 'img': '图片', 'iframe': 'PDF', 'nopv': '不可预览提示'}[f['pv']])
        if f['pv'] == 'pre':
            chk(tag, p.get('hasPre') and not p.get('hasImg') and not p.get('hasIfr') and not p.get('hasNoPv'))
            chk('%-14s 预览正文正确' % f['nm'], bool(p.get('pvMatch')),
                '开头=%r len=%s' % (p.get('pvHead'), p.get('pvLen')))
        elif f['pv'] == 'img':
            chk(tag, p.get('hasImg') and not p.get('hasPre') and not p.get('hasIfr'))
            chk('%-14s 图片真的解码出来了' % f['nm'], (p.get('natW') or 0) > 0,
                'naturalWidth=%s naturalHeight=%s' % (p.get('natW'), p.get('natH')))
        elif f['pv'] == 'iframe':
            chk(tag, p.get('hasIfr') and not p.get('hasPre') and not p.get('hasImg'))
            chk('%-14s iframe 地址带 #view=FitH' % f['nm'],
                str(p.get('src') or '').endswith('#view=FitH'), repr(p.get('src'))[-60:])
            chk('%-14s 带「不内嵌 PDF」降级提示条' % f['nm'],
                bool(p.get('hasHint')) and '下载' in (p.get('hint') or ''), repr((p.get('hint') or '')[:30]))
        else:
            chk(tag, p.get('hasNoPv') and not p.get('hasPre') and not p.get('hasImg') and not p.get('hasIfr'))
        chk('%-14s 底栏类型=%-5s 且有下载按钮' % (f['nm'], f['pmeta']),
            f['pmeta'] in (p.get('meta') or '') and bool(p.get('dlBtn')), repr(p.get('meta')))

    # ── PDF：headless 渲染不了 ⇒ 用「对象本体可服务」做功能性断言 ─────────────
    pvpdf = pv.get([f['nm'] for f in FILES if f['pv'] == 'iframe'][0]) or {}
    src = pvpdf.get('src') or ''
    if src:
        try:
            import urllib.request
            rq = urllib.request.Request(src, method='HEAD')
            with urllib.request.urlopen(rq, timeout=15) as resp:
                ct = resp.headers.get('Content-Type') or ''
                chk('PDF 对象 HEAD 200 + application/pdf', resp.status == 200 and 'pdf' in ct.lower(),
                    'HTTP %s · %s' % (resp.status, ct))
        except Exception as e:
            chk('PDF 对象 HEAD 200 + application/pdf', False, '请求失败：%s' % str(e)[:80])
    else:
        chk('PDF 对象 HEAD 200 + application/pdf', False, '没拿到 iframe 地址')

    chk('删除按钮存在并弹出密码门', bool(m.get('gate2')))
    chk('删除门标为不可撤销', m.get('gate2Danger') is True, '按钮=%r' % m.get('gate2Act'))
    chk('每次删除都弹门（%d 次）' % N, m.get('gate2Count') == N,
        '弹门 %s 次 / 删了 %s 轮' % (m.get('gate2Count'), m.get('delTries')))
    chk('逐个删完后列表清空', m.get('rows2') == 0 and bool(m.get('empty2')),
        'rows=%s stat=%r' % (m.get('rows2'), m.get('stat2')))
    audit_objects(chk, RUN_T0)

    print('-' * 100)
    print('结论：%s' % ('全绿 ✅' if not red else ('❌ 有 %d 项不过：%s' % (len(red), '、'.join(red)))))
    print('用时 %.1fs' % ((m.get('ms') or 0) / 1000.0))
    return 0 if not red else 1


if __name__ == '__main__':
    sys.exit(main())
