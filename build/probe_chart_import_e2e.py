# -*- coding: utf-8 -*-
"""图表数据表「导入 Excel / CSV」端到端验收（真机 Edge + 真 xlsx 字节 + 真云端数据）。

用户诉求：「图表编辑增加一个可上传导入 excel 表格上传编辑数据」。

本探针盯这条链路的**每一段**，全部在真浏览器里跑、喂真字节：
  ① 真 .xlsx（ZIP_DEFLATED + sharedStrings + styles）→ 解析出的行列与单元格值
  ② 真 .xlsx（ZIP_STORED，method=0）→ 不压缩条目也能解
  ③ `#` 序号列自动忽略；日期格式单元格解成 YYYY-MM-DD（不是 45000）
  ④ 没有表头的纯数字文件：第一行**不能**被当表头吃掉
  ⑤ 末尾幽灵空列被砍掉（不凭空多出一个系列）
  ⑥ 系列数量对齐：文件列多则按最后一列补、列少则裁掉多余系列（并同步 series.name）
  ⑦ UTF-8 BOM + CRLF + 引号逗号 的 CSV；GBK 编码的 CSV（decodeBuf 兜底）
  ⑧ 多工作表 xlsx：取第一张表（sheet1.xml），sheet2 的干扰内容不能串进来
  ⑨ .xls（旧版二进制）必须被明确拒绝，且表格保持原样
  ⑩ 导入后**断言 DOM 表格里的单元格值**（铁律：只看 JSON 不算验证）
  ⑪ 导出 → 再解析 的闭环（dlTable 的数据源 readGridCols/readGrid 能被 rowsFromText 解回）
  ⑫ 门禁：impTable 必须被 RGATE 包过（act='导入'、danger=true）

⚠️ 本探针**只改编辑框、不点保存** → 不写数据库、不碰用户真实研报数据。
"""
import base64
import html
import http.server
import io
import json
import os
import re
import socketserver
import subprocess
import threading
import urllib.request
import zipfile

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(BASE, 'deploy', 'report.html')
OUT = os.path.join(BASE, 'build', '_probe_chartimp.html')
PORT = 8919
CODE = '600456'

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


# ---------------------------------------------------------------- xlsx 造数据
def col_name(i):
    s, i = '', i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def xesc(t):
    return (str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def sheet_xml(grid, date_cells=()):
    """grid: list[list]（None/'' = 空单元格）。数字直接写，文本进 sharedStrings，
    date_cells 里的坐标用 s="1"（numFmtId=14 的日期格式）+ 原始序列号。"""
    shared, sidx = [], {}

    def sid(t):
        if t not in sidx:
            sidx[t] = len(shared)
            shared.append(t)
        return sidx[t]

    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<worksheet xmlns="%s"><sheetData>' % NS]
    for r, row in enumerate(grid, start=1):
        cells = []
        for c, v in enumerate(row):
            if v is None or v == '':
                continue
            ref = '%s%d' % (col_name(c), r)
            if (r - 1, c) in date_cells:
                cells.append('<c r="%s" s="1"><v>%s</v></c>' % (ref, v))
            elif isinstance(v, (int, float)):
                cells.append('<c r="%s"><v>%s</v></c>' % (ref, v))
            else:
                cells.append('<c r="%s" t="s"><v>%d</v></c>' % (ref, sid(str(v))))
        parts.append('<row r="%d">%s</row>' % (r, ''.join(cells)))
    parts.append('</sheetData></worksheet>')
    return ''.join(parts), shared


STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<styleSheet xmlns="%s">'
          '<fonts count="1"><font/></fonts><fills count="1"><fill/></fills>'
          '<borders count="1"><border/></borders>'
          '<cellStyleXfs count="1"><xf numFmtId="0"/></cellStyleXfs>'
          '<cellXfs count="2">'
          '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
          '<xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
          '</cellXfs>'
          '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
          '</styleSheet>') % NS


def mk_xlsx(grid, date_cells=(), method=zipfile.ZIP_DEFLATED, extra_sheets=0):
    sh, shared = sheet_xml(grid, date_cells)
    sst = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<sst xmlns="%s" count="%d" uniqueCount="%d">' % (NS, len(shared), len(shared))
           + ''.join('<si><t xml:space="preserve">%s</t></si>' % xesc(t) for t in shared)
           + '</sst>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', method) as z:
        z.writestr('[Content_Types].xml',
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   '</Types>')
        z.writestr('_rels/.rels',
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        z.writestr('xl/workbook.xml',
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="%s" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheets><sheet name="数据" sheetId="1" r:id="rId1"/></sheets></workbook>' % NS)
        z.writestr('xl/_rels/workbook.xml.rels',
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                   '</Relationships>')
        z.writestr('xl/sharedStrings.xml', sst)
        z.writestr('xl/styles.xml', STYLES)
        z.writestr('xl/worksheets/sheet1.xml', sh)
        for i in range(extra_sheets):
            # 干扰表：内容必须**不能**串进结果
            j, _ = sheet_xml([['干扰表内容', 999], ['不该出现', 888]])
            z.writestr('xl/worksheets/sheet%d.xml' % (i + 2), j)
    return base64.b64encode(buf.getvalue()).decode()


def b64text(s, enc='utf-8', bom=b''):
    return base64.b64encode(bom + s.encode(enc)).decode()


# 与用户截图一致的主用例：4 行 × 2 个系列
MAIN = [['类别', '营业收入', '归母净利润'],
        ['2023', 450.86, 4.68],
        ['2024', 475.04, 5.79],
        ['2025', 556.75, 6.41],
        ['2026H1', 226.52, 3.5]]

SERIAL_DATE = 45000                       # 2023-03-15
D2 = [['#', '类别', '数值A'],
      [1, SERIAL_DATE, 10],
      [2, 2024, 20]]
THREE = [['类别', '甲', '乙', '丙'],
         ['A', 1, 2, 3],
         ['B', 4, 5, 6]]
GHOST = [['类别', '甲', '乙', '', ''],
         ['A', 1, 2, None, None],
         ['B', 4, 5, None, None]]
NOHEAD = [['2023', 1, 2], ['2024', 3, 4]]

FILES = {
    'xlsx_deflate': mk_xlsx(MAIN),
    'xlsx_stored': mk_xlsx(MAIN, method=zipfile.ZIP_STORED),
    'xlsx_date': mk_xlsx(D2, date_cells={(1, 1), (2, 1)}),
    'xlsx_3sheets': mk_xlsx(MAIN, extra_sheets=1),
    'csv_bom': b64text('类别,营业收入,归母净利润\r\n2023,450.86,4.68\r\n2024,"475.04","5.79"\r\n',
                       bom=b'\xef\xbb\xbf'),
    'csv_gbk': b64text('类别,营业收入\r\n2023,450.86\r\n', enc='gbk'),
    'csv_ghost': b64text('类别,甲,乙,,\r\nA,1,2,,\r\nB,4,5,,\r\n'),
    'csv_nohead': b64text('2023,1,2\n2024,3,4\n'),
}
THREE_B64 = mk_xlsx(THREE)

# 日期断言用与 JS serialDate 完全相同的算法算期望值（UTC，避免时区差）
import datetime
EXP_DATE = (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=SERIAL_DATE)).strftime('%Y-%m-%d')

PROBE = '''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var R = window.__R;
  var F = %(files)s;
  var THREE = %(three)s;
  function out(){ document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R); }
  function u8(b64){
    var bin = atob(b64), a = new Uint8Array(bin.length);
    for(var i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
    return a;
  }
  function gridRows(){
    var trs = document.querySelectorAll('#c-grid .rpt-grid tbody tr'), o = [];
    for(var i = 0; i < trs.length; i++){
      var ins = trs[i].querySelectorAll('input'), r = [];
      for(var j = 0; j < ins.length; j++) r.push(ins[j].value);
      o.push(r);
    }
    return o;
  }
  function gridHead(){
    /* ⚠️ 第 1 个 <th> 是固定的行号列「#」，不是数据表的列 —— 必须跳过，
       否则每一条表头断言都会莫名其妙地多一个 #（本轮就栽在这）。 */
    var ths = document.querySelectorAll('#c-grid .rpt-grid thead th'), o = [];
    for(var i = 1; i < ths.length; i++) o.push(String(ths[i].textContent || '').trim());
    return o;
  }
  function json(){ return JSON.parse(($('c-json') || {}).value || '{}'); }
  function info(){ return String((($('c-gridinfo') || {}).textContent) || '').trim(); }

  /* ⚠️ 等异步解析完成**不能靠 ticks 硬等**：headless 的 --virtual-time-budget 会把
     定时器快进，而 FileReader / DecompressionStream 的完成任务要走一趟别的线程，
     轮次可能在回调之前就烧完。所以主用「事件推进」（impApply 一被调到就推下一步），
     ticks 只当兜底，并单独记录 R.stalls 看有没有哪一步是靠兜底过的。 */
  var done = 0, realApply = Rpt.impApply, pending = null;
  Rpt.impApply = function(){
    var r = realApply.apply(Rpt, arguments);
    done++;
    if(pending && !pending.byEvent){ pending.byEvent = true; }
    return r;
  };
  function imp(b64, name){ Rpt.impTable(new File([u8(b64)], name), RPASS_OK); }

  var steps = [], stalls = 0;
  function step(name, fn, wait){ steps.push({n:name, f:fn, w:!!wait}); }

  step('打开第一张非饼图的数据表', function(){
    R.chartKeys = St.chartKeys.length;
    var keys = St.chartKeys.filter(function(k){
      var o = (St.charts[k] || {}).opt || {}, s0 = (o.series || [])[0] || {};
      return s0.type !== 'pie';
    });
    R.pieKeys = St.chartKeys.length - keys.length;
    R.selKey = keys[0];
    Rpt.openChart(keys[0]);
    R.hasGrid = !!document.querySelector('#c-grid .rpt-grid input[data-r]');
    R.hasJson = !!$('c-json');
    R.tools = !!document.querySelector('.rpt-iotools');
    R.fileInput = !!$('c-file');
    R.dlFn = typeof Rpt.dlTable === 'function';
    R.pickFn = typeof Rpt.impPick === 'function';
    R.passOkGlobal = (typeof RPASS_OK === 'object');
    R.gate = {gated:Rpt.impTable.__gated === true, act:Rpt.impTable.__act, danger:Rpt.impTable.__danger};
  });

  step('xlsx（deflate）导入', function(){
    imp(F.xlsx_deflate, 'chart.xlsx');
  }, true);
  step('→ 断言 xlsx 结果', function(){
    R.head1 = gridHead(); R.rows1 = gridRows(); R.info1 = info();
    R.headMatch1 = (JSON.stringify(gridHead()) === JSON.stringify(readGridCols()));
    var o = json();
    R.s1_series = ((o.series || [])[0] || {}).name;
    R.s1_nseries = (o.series || []).length;
    /* ⚠️ xAxis 可能是对象也可能是数组（applyGrid 两种都吃）—— 探针也得两种都吃 */
    var xa = Array.isArray(o.xAxis) ? o.xAxis[0] : o.xAxis;
    R.s1_cats = ((xa && xa.data) || []).slice();
    R.s1_jsonOk = true;
  });

  step('xlsx（stored/method0）导入', function(){ imp(F.xlsx_stored, 'stored.xlsx'); }, true);
  step('→ 断言 stored', function(){
    R.rows2 = gridRows(); R.info2 = info();
  });

  step('多工作表 xlsx 导入（只取 sheet1）', function(){ imp(F.xlsx_3sheets, 'two.xlsx'); }, true);
  step('→ 断言没有串表', function(){
    var flat = JSON.stringify(gridRows());
    R.sheets_clean = flat.indexOf('干扰表内容') < 0 && flat.indexOf('999') < 0;
    R.sheets_rows = gridRows().length;
  });

  step('# 序号列 + 日期格式（真 xlsx）', function(){ imp(F.xlsx_date, 'date.xlsx'); }, true);
  step('→ 断言序号列被忽略 / 日期被还原 / 系列被裁到 1', function(){
    R.head4 = gridHead(); R.rows4 = gridRows();
    R.s4_nseries = (json().series || []).length;
  });

  step('3 列系列（系列不够要按最后一列补）', function(){ imp(THREE, 'three.xlsx'); }, true);
  step('→ 断言补出的系列', function(){
    var o = json(), s = o.series || [];
    R.s5_n = s.length;
    R.s5_names = s.map(function(x){ return x.name; });
    R.s5_head = gridHead();
    R.s5_data0 = (s[1] && s[1].data) || [];
    R.s5_types = s.map(function(x){ return x.type; });
  });

  step('CSV（UTF-8 BOM + CRLF + 引号）', function(){ imp(F.csv_bom, 'a.csv'); }, true);
  step('→ 断言 CSV', function(){ R.rows6 = gridRows(); R.head6 = gridHead(); R.info6 = info(); });

  step('CSV（GBK 编码）', function(){ imp(F.csv_gbk, 'gbk.csv'); }, true);
  step('→ 断言 GBK 兜底', function(){ R.head7 = gridHead(); R.rows7 = gridRows(); });

  step('CSV 末尾幽灵空列', function(){ imp(F.csv_ghost, 'ghost.csv'); }, true);
  step('→ 断言幽灵列被砍', function(){ R.head8 = gridHead(); R.info8 = info(); });

  step('CSV 没有表头（纯数字）', function(){ imp(F.csv_nohead, 'nohead.csv'); }, true);
  step('→ 断言第一行没被吃掉', function(){ R.rows9 = gridRows(); R.head9 = gridHead(); R.info9 = info(); });

  step('.xls 旧格式必须被拒绝', function(){
    R.beforeXls = JSON.stringify(gridRows());
    imp(F.csv_nohead, 'legacy.xls');
  });
  step('→ 断言拒绝且表格未变', function(){
    R.afterXls = JSON.stringify(gridRows());
    R.xlsToast = String((($('rptToast') || {}).textContent) || '').replace(/\\s+/g, ' ').slice(0, 120);
  });

  step('导出 → 解析 闭环', function(){
    var cols = readGridCols(), rows = readGrid().rows;
    var q = function(v){ v = String(v == null ? '' : v); return /[",\\n\\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
    var txt = ([cols.map(q).join(',')]).concat(rows.map(function(r){ return r.map(q).join(','); })).join('\\r\\n');
    R.rt_cols = rowsFromText(txt)[0];
    R.rt_rows = rowsFromText(txt).length - 1;
    R.rt_cols_n = cols.length; R.rt_rows_n = rows.length;
  });

  step('纯函数边界', function(){
    R.p_serial = serialDate(45000);
    R.p_datefmt = [isDateFmt(14, ''), isDateFmt(0, '0.00'), isDateFmt(0, 'yyyy-mm-dd'), isDateFmt(0, '#,##0')];
    R.p_model_head = rowsToModel(rowsFromText('月份,收入\\n1月,10\\n2月,20'), 'series');
    R.p_cast = [cellText(null), cellText('  a  b '), cellText(3.5)];
    R.p_unesc = xmlUnesc('&lt;a&gt;&amp;amp;&#65;&#x42;');
    R.p_colidx = [colIdx('A'), colIdx('Z'), colIdx('AA')];
  });

  step('留证：最终表格状态', function(){
    R.finalHead = gridHead();
    R.finalInfo = info();
    R.finalRows = gridRows().length;
    R.pageErrs = (window.__RPT_ERR || []).slice(0, 5);    /* 页面自己的错误钩子 */
    R.echartsUp = (typeof echarts !== 'undefined');        /* 注入没把 ECharts 打断 */
    R.chartsRendered = document.querySelectorAll('canvas').length;
  });

  /* 页面 boot 是异步的（要从云端把整份研报拉回来）→ 等 St.chartKeys 出现再开跑 */
  var si = 0, boot = 0;
  (function waitBoot(){
    boot++;
    R.bootTicks = boot;
    if((St.chartKeys && St.chartKeys.length) || boot > 80){
      if(!(St.chartKeys && St.chartKeys.length)) R.err = '研报没从云端加载出来（chartKeys=0）';
      R.bootSrc = (St.src || '');
      run();
      return;
    }
    setTimeout(waitBoot, 100);
  })();
  function run(){
    out();                              /* ★ 每步都回传一次：中途被虚拟时间截断也能看到进度 */
    if(si >= steps.length){ R.stage = 'done'; out(); return; }
    var st = steps[si++];
    R.lastStep = st.n;
    try{ st.f(); }
    catch(e){ R.err = st.n + ' → ' + String(e && e.message || e); R.stage = 'exception'; out(); return; }
    if(!st.w){ run(); return; }
    var base = done, ticks = 0;
    pending = {byEvent:false};
    out();
    (function wait(){
      ticks++;
      var ev = done > base;
      if(ev || ticks > 60){
        if(!ev){                    /* 靠兜底过的 → 记下来，别把「虚拟时间饿死异步回调」当成绩 */
          stalls++;
          R.stalls = stalls;
          R.stallSteps = R.stallSteps || [];
          R.stallSteps.push(st.n + ':' + ticks);
        }
        pending = null;
        run();
        return;
      }
      setTimeout(wait, 10);
    })();
  }
})();
</script>
'''

js = PROBE % {'files': json.dumps(FILES), 'three': json.dumps(THREE_B64)}

s = open(SRC, encoding='utf-8').read()
# ⚠️⚠️ 两个坑（都实踩过）：
#  ① ECharts 源码里含有 `'</body></html>'` 这种**字符串字面量**（saveAsImage 的 HTML 模板），
#     所以 `replace('</body>', …, 1)` 会把探针塞进 ECharts 的字符串里 —— 探针整段不执行，
#     还顺手把 ECharts 打断（ECharts 块直接语法错）。必须从**最后一个** `</body>` 注入。
#  ② 研报页自己在 <head> 里装了 window.onerror（写 window.__RPT_ERR），会**覆盖**我们的
#     window.onerror → 探针额外用 addEventListener('error') 挂一份，并直接读 __RPT_ERR。
onerr = ('<script>window.__R={err:[],stage:"boot"};'
         'window.addEventListener("error",function(e){'
         'window.__R.err.push("err:"+String(e.message||e)+" @"+(e.lineno||0));});'
         'window.addEventListener("unhandledrejection",function(e){'
         'window.__R.err.push("rej:"+String((e.reason&&e.reason.message)||e.reason));});'
         '</script>')
assert '<head>' in s
s = s.replace('<head>', '<head>\n' + onerr, 1)
assert '</body>' in s
_i = s.rfind('</body>')
s = s[:_i] + js + '\n' + s[_i:]
open(OUT, 'w', encoding='utf-8').write(s)
print('[1] 探针页已生成：%s（%d 字节）' % (OUT, os.path.getsize(OUT)))

NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
_core = js.split('<script>')[1].split('</script>')[0]
open(os.path.join(BASE, 'build', '_tmp_chartimp.js'), 'w', encoding='utf-8').write(_core)
_c = subprocess.run([NODE, '--check', os.path.join(BASE, 'build', '_tmp_chartimp.js')],
                    capture_output=True, text=True)
if _c.returncode != 0:
    print('[1b] 注入脚本语法错误：\n' + (_c.stderr or '')[-1500:])
    raise SystemExit(1)
print('[1b] 注入脚本 node --check 通过')


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


os.chdir(os.path.join(BASE, 'build'))
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', PORT), Quiet)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
print('[2] 本地 http：http://127.0.0.1:%d/' % PORT)

edge = None
for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
          r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
    if os.path.exists(c):
        edge = c
        break
assert edge, '找不到 msedge.exe'
print('[3] Edge：%s' % edge)

prof = os.path.join(BASE, 'build', '_probe_profile_chartimp')
os.makedirs(prof, exist_ok=True)          # 固定 profile，不删目录（safe-delete 守卫）
url = 'http://127.0.0.1:%d/_probe_chartimp.html?code=%s' % (PORT, CODE)
print('[4] 启动 headless Edge（真取云端研报 + 真解析 xlsx）…')
r = subprocess.run([edge, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                    '--user-data-dir=' + prof, '--virtual-time-budget=120000', '--dump-dom', url],
                   capture_output=True, timeout=420)
dom = r.stdout.decode('utf-8', 'ignore')
print('    DOM 长度 %d' % len(dom))

m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S) or re.search(r'PROBE_JSON:(\{.*\})', dom, re.S)
ok = fail = 0


def chk(name, cond, extra=''):
    global ok, fail
    if cond:
        ok += 1
        print('  [OK]   ' + name)
    else:
        fail += 1
        print('  [FAIL] ' + name + ('   → ' + str(extra) if extra != '' else ''))


print('\n' + '=' * 78)
print('图表数据表「导入 Excel / CSV」端到端验收')
print('=' * 78)

if not m:
    open(os.path.join(BASE, 'build', '_probe_chartimp_dom.txt'), 'w', encoding='utf-8').write(dom)
    print('[FAIL] 探针没有回传结果，DOM 已存 build/_probe_chartimp_dom.txt')
    print('\n结果：0 通过 / 1 失败')
    raise SystemExit(1)

d = json.loads(html.unescape(m.group(1)))     # ⚠️ --dump-dom 会把 < > & 变实体，先还原
print('阶段：%s   JS 错误：%s' % (d.get('stage'), d.get('err') or '无'))
print('最后一步：%s   兜底次数：%s %s' % (d.get('lastStep'), d.get('stalls'),
                                        d.get('stallSteps') or ''))
print('图表数：%s（跳过饼图 %s）   当前图表键：%s' % (d.get('chartKeys'), d.get('pieKeys'), d.get('selKey')))
print('xlsx 读入：%s  %s' % (d.get('info1'), d.get('head1')))
print('第 1 行：%s' % (d.get('rows1') or [''])[0])
print('最终表：%s  %s' % (d.get('finalInfo'), d.get('finalHead')))

chk('JS 零错误', not d.get('err'), d.get('err'))
chk('页面自己的错误钩子也为空（含 ECharts）', not (d.get('pageErrs') or []), d.get('pageErrs'))
chk('ECharts 没被探针注入打断（echarts 全局在 + 有 canvas）',
    d.get('echartsUp') is True and (d.get('chartsRendered') or 0) > 0,
    '%s / %s' % (d.get('echartsUp'), d.get('chartsRendered')))
chk('阶段跑完', d.get('stage') == 'done', d.get('stage'))

# ① 真 xlsx（deflate）
chk('① xlsx（deflate）表头 = 类别/营业收入/归母净利润',
    d.get('head1') == ['类别', '营业收入', '归母净利润'], d.get('head1'))
chk('① 探针读到的表头 = 页面自己的 readGridCols()', d.get('headMatch1') is True, d.get('headMatch1'))
chk('① xlsx 读出 4 行', len(d.get('rows1') or []) == 4, d.get('rows1'))
chk('① 首行单元格值 = 2023 / 450.86 / 4.68（断言 DOM 值）',
    (d.get('rows1') or [['']])[0] == ['2023', '450.86', '4.68'], (d.get('rows1') or [])[:1])
chk('① 末行 = 2026H1 / 226.52 / 3.5',
    (d.get('rows1') or [[]])[-1] == ['2026H1', '226.52', '3.5'], (d.get('rows1') or [])[-1:])
chk('① 数据表计数文案 = 4 行 × 2 个系列', d.get('info1') == '4 行 × 2 个系列', d.get('info1'))
chk('① 写回的 option：2 个系列 + 系列名来自表头',
    d.get('s1_nseries') == 2 and d.get('s1_series') == '营业收入',
    '%s / %s' % (d.get('s1_nseries'), d.get('s1_series')))
chk('① xAxis 类别同步成 4 个',
    (d.get('s1_cats') or [])[:2] == ['2023', '2024'] and len(d.get('s1_cats') or []) == 4,
    d.get('s1_cats'))

# ② stored zip
chk('② xlsx（method=0 不压缩）也能解', len(d.get('rows2') or []) == 4 and d.get('info2') == '4 行 × 2 个系列',
    '%s / %s' % (d.get('info2'), d.get('rows2')))

# ③ 多工作表：只取第一张
chk('③ 多工作表 xlsx 只取 sheet1（不串表）', d.get('sheets_clean') is True and d.get('sheets_rows') == 4,
    '%s / %s' % (d.get('sheets_clean'), d.get('sheets_rows')))

# ④ 序号列 + 日期
chk('④ `#` 序号列被忽略（表头不再有 #）', d.get('head4') == ['类别', '数值A'], d.get('head4'))
chk('④ 日期格式单元格 → %s（不是 45000）' % EXP_DATE,
    (d.get('rows4') or [['']])[0][0] == EXP_DATE, (d.get('rows4') or [])[:1])
chk('④ 只有 1 个系列列时裁掉多余系列', d.get('s4_nseries') == 1, d.get('s4_nseries'))

# ⑤ 系列补齐
chk('⑤ 文件 3 个系列 → 补到 3 个', d.get('s5_n') == 3, d.get('s5_n'))
chk('⑤ 补出的系列名 = 表头（甲/乙/丙）', d.get('s5_names') == ['甲', '乙', '丙'], d.get('s5_names'))
chk('⑤ 补出的系列沿用原类型（不变成 undefined）',
    all(t == d.get('s5_types')[0] for t in (d.get('s5_types') or [])) if d.get('s5_types') else False,
    d.get('s5_types'))
chk('⑤ 数据落到第 2 个系列', (d.get('s5_data0') or [])[:2] == [2, 5], d.get('s5_data0'))

# ⑥ CSV
chk('⑥ CSV（BOM+CRLF+引号）2 行数据', len(d.get('rows6') or []) == 2 and d.get('info6') == '2 行 × 2 个系列',
    '%s / %s' % (d.get('info6'), d.get('rows6')))
chk('⑥ CSV 引号里的数字原样读出',
    (d.get('rows6') or [[]])[-1] == ['2024', '475.04', '5.79'], (d.get('rows6') or [])[-1:])

# ⑦ GBK
chk('⑦ GBK 编码 CSV 中文表头正常（decodeBuf 兜底）', '营业收入' in (d.get('head7') or []), d.get('head7'))

# ⑧ 幽灵列
chk('⑧ 末尾幽灵空列被砍掉', d.get('head8') == ['类别', '甲', '乙'], d.get('head8'))

# ⑨ 无表头
chk('⑨ 没有表头时第一行**没被当表头吃掉**', len(d.get('rows9') or []) == 2, d.get('rows9'))
chk('⑨ 无表头时首列名回落到「类别」', (d.get('head9') or [])[:1] == ['类别'], d.get('head9'))

# ⑩ .xls 拒绝
chk('⑩ .xls 被拒绝且表格保持原样',
    d.get('beforeXls') == d.get('afterXls') and '另存为' in (d.get('xlsToast') or ''),
    d.get('xlsToast'))

# ⑪ 导出闭环
chk('⑪ 导出的 CSV 能被解析回来（列数一致）', d.get('rt_cols_n') == len(d.get('rt_cols') or []),
    '%s vs %s' % (d.get('rt_cols_n'), d.get('rt_cols')))
chk('⑪ 导出行数一致', d.get('rt_rows_n') == d.get('rt_rows'),
    '%s vs %s' % (d.get('rt_rows_n'), d.get('rt_rows')))

# ⑫ 纯函数
chk('⑫ serialDate(45000) = %s' % EXP_DATE, d.get('p_serial') == EXP_DATE, d.get('p_serial'))
chk('⑫ isDateFmt 判定正确', d.get('p_datefmt') == [True, False, True, False], d.get('p_datefmt'))
chk('⑫ rowsToModel 表头识别', (d.get('p_model_head') or {}).get('cols') == ['月份', '收入'],
    d.get('p_model_head'))
chk('⑫ cellText 规整空白/数字', d.get('p_cast') == ['', 'a b', '3.5'], d.get('p_cast'))
chk('⑫ xmlUnesc 实体还原', d.get('p_unesc') == '<a>&amp;AB', d.get('p_unesc'))
chk('⑫ colIdx A/Z/AA = 0/25/26', d.get('p_colidx') == [0, 25, 26], d.get('p_colidx'))

# ⑬ 门禁 + UI
g = d.get('gate') or {}
chk('⑬ impTable 被 RGATE 门禁包过（覆盖导入必须输密码）',
    g.get('gated') is True and g.get('act') == '导入' and g.get('danger') is True, g)
chk('⑬ 工具条 / 文件输入 / 导出 / 选文件按钮齐全',
    d.get('tools') and d.get('fileInput') and d.get('dlFn') and d.get('pickFn'), d)
chk('⑬ 真云端研报已加载（图表数 > 0）', (d.get('chartKeys') or 0) > 0, d.get('chartKeys'))
chk('⑬ 哨兵 RPASS_OK 在页面上可达（探针可直通门禁）', d.get('passOkGlobal') is True)

print('\n' + '=' * 78)
print('结果：%d 通过 / %d 失败' % (ok, fail))
print('=' * 78)
raise SystemExit(0 if fail == 0 else 1)
