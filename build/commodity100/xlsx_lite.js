/* ============================================================================
   零依赖 xlsx / csv 解析（约 6 KB）
   —— 从 deploy/datalib.template.html 的第「一、xlsx 解析」节逐字抽取，两份保持同源。
      不引任何第三方库：xlsx 本质是 zip，用浏览器原生能力即可解开。

   xlsx = zip（[Content_Types].xml + xl/workbook.xml + xl/sharedStrings.xml + xl/worksheets/*.xml）
   步骤：读 zip 中央目录 → DecompressionStream('deflate-raw') 解压需要的几个 XML
        → DOMParser 解析 → 取共享字符串 / 还原日期 / 拼二维数组

   对外只暴露三个函数：
     XLSX.parseXlsx(buf)   ArrayBuffer → Promise<{工作表名: 二维数组}>
     XLSX.parseCsv(text)   字符串 → 二维数组
     XLSX.serialToDate(v)  Excel 日期序列号 → Date
   ============================================================================ */
var XLSX = (function(){
  var DAY = 86400000;

  function rd16(b,o){ return b[o] | (b[o+1] << 8); }
  function rd32(b,o){ return (b[o] | (b[o+1] << 8) | (b[o+2] << 16) | (b[o+3] << 24)) >>> 0; }
  function bstr(b,o,len){ var s = ''; for(var i = 0; i < len; i++) s += String.fromCharCode(b[o+i]); return s; }

  /* 读 zip 中央目录：给出 {文件名: {method, csize, start}} */
  function zipIndex(b){
    if(b.length < 22 || b[0] !== 0x50 || b[1] !== 0x4b) throw new Error('不是 zip/xlsx 文件（缺少 PK 标记）');
    var eocd = -1, from = Math.max(0, b.length - 66000);
    for(var i = b.length - 22; i >= from; i--){
      if(b[i] === 0x50 && b[i+1] === 0x4b && b[i+2] === 0x05 && b[i+3] === 0x06){ eocd = i; break; }
    }
    if(eocd < 0) throw new Error('zip 目录尾部（EOCD）缺失，文件可能被截断');
    var cnt = rd16(b, eocd + 10), off = rd32(b, eocd + 16), out = {}, p = off;
    for(var j = 0; j < cnt; j++){
      if(rd32(b, p) !== 0x02014b50) throw new Error('zip 中央目录第 ' + (j + 1) + ' 项损坏');
      var method = rd16(b, p + 10), csize = rd32(b, p + 20);
      var nlen = rd16(b, p + 28), elen = rd16(b, p + 30), clen = rd16(b, p + 32);
      var lho  = rd32(b, p + 42);
      var name = bstr(b, p + 46, nlen);
      var lnl  = rd16(b, lho + 26), lel = rd16(b, lho + 28);
      out[name] = {method:method, csize:csize, start:lho + 30 + lnl + lel};
      p += 46 + nlen + elen + clen;
    }
    return out;
  }
  /* 取出某个条目并解压（method 0 = 存储，8 = deflate） */
  function unzipEntry(b, ent){
    if(!ent) return Promise.resolve(null);
    var raw = b.subarray(ent.start, ent.start + ent.csize);
    if(ent.method === 0) return Promise.resolve(raw);
    if(ent.method !== 8) return Promise.reject(new Error('不支持的压缩方式 method=' + ent.method + '（请另存为 CSV 上传）'));
    if(typeof DecompressionStream === 'undefined')
      return Promise.reject(new Error('当前浏览器不支持解压 xlsx（DecompressionStream 缺失），请把工作表另存为 CSV 再上传'));
    var stream = new Blob([raw]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
    return new Response(stream).arrayBuffer().then(function(ab){ return new Uint8Array(ab); });
  }
  function xmlDoc(u8){
    var txt = new TextDecoder('utf-8').decode(u8);
    var d = new DOMParser().parseFromString(txt, 'application/xml');
    if(d.getElementsByTagName('parsererror').length) throw new Error('XML 解析失败');
    return d;
  }
  /* 共享字符串表：<si> 里可能有多段 <r><t> */
  function parseShared(doc){
    var out = [], si = doc.getElementsByTagName('si');
    for(var i = 0; i < si.length; i++){
      var ts = si[i].getElementsByTagName('t'), s = '';
      for(var j = 0; j < ts.length; j++) s += ts[j].textContent;
      out.push(s);
    }
    return out;
  }
  /* 列号：A→0, B→1, AA→26 */
  function colIdx(ref){
    var s = String(ref || '').replace(/[^A-Z]/g, ''), n = 0;
    for(var i = 0; i < s.length; i++) n = n * 26 + (s.charCodeAt(i) - 64);
    return n - 1;
  }
  /* 日期序列号（1900 体系，含闰年 bug）→ Date */
  function serialToDate(v){
    var days = Math.floor(v), frac = v - days;
    var ms = Date.UTC(1899, 11, 30) + days * DAY + Math.round(frac * DAY);
    return new Date(ms);
  }
  function pad2(n){ return (n < 10 ? '0' : '') + n; }
  function fmtDate(d){
    var s = d.getUTCFullYear() + '-' + pad2(d.getUTCMonth() + 1) + '-' + pad2(d.getUTCDate());
    if(d.getUTCHours() || d.getUTCMinutes() || d.getUTCSeconds())
      s += ' ' + pad2(d.getUTCHours()) + ':' + pad2(d.getUTCMinutes());
    return s;
  }
  /* 样式表：哪几个 s 索引是日期格式（内置 14~22 / 45~47，或自定义格式串里含 y/m/d） */
  function parseStyles(doc){
    var dateS = {}, custom = {}, nf = doc.getElementsByTagName('numFmt');
    for(var i = 0; i < nf.length; i++){
      var id = parseInt(nf[i].getAttribute('numFmtId'), 10), cd = nf[i].getAttribute('formatCode') || '';
      /* 去掉引号里的字面量再判断，避免 "元/月" 之类被误判成日期 */
      var bare = cd.replace(/"[^"]*"/g, '').replace(/\[[^\]]*\]/g, '');
      if(/[yY]/.test(bare) || /[dD]/.test(bare) && /[mM]/.test(bare)) custom[id] = 1;
    }
    var cx = doc.getElementsByTagName('cellXfs')[0];
    if(!cx) return dateS;
    var xf = cx.getElementsByTagName('xf');
    for(var k = 0; k < xf.length; k++){
      var id2 = parseInt(xf[k].getAttribute('numFmtId') || '0', 10);
      if((id2 >= 14 && id2 <= 22) || (id2 >= 45 && id2 <= 47) || custom[id2]) dateS[k] = 1;
    }
    return dateS;
  }
  /* 一张工作表 → 二维数组 */
  function sheetGrid(doc, shared, dateS){
    var rows = doc.getElementsByTagName('row'), out = [];
    for(var i = 0; i < rows.length; i++){
      var cs = rows[i].getElementsByTagName('c'), arr = [], maxc = -1;
      for(var j = 0; j < cs.length; j++){
        var c = cs[j], ref = c.getAttribute('r'), t = c.getAttribute('t');
        var ci = ref ? colIdx(ref) : j;
        if(ci < 0) ci = j;
        var sAttr = c.getAttribute('s');
        var vEl = c.getElementsByTagName('v')[0];
        var tEl = c.getElementsByTagName('t')[0];
        var val = '';
        if(t === 's')         val = shared[parseInt(vEl ? vEl.textContent : '0', 10)] || '';
        else if(t === 'inlineStr') val = tEl ? tEl.textContent : '';
        else if(t === 'str')  val = vEl ? vEl.textContent : (tEl ? tEl.textContent : '');
        else if(t === 'b')    val = (vEl && vEl.textContent === '1') ? 'TRUE' : 'FALSE';
        else if(vEl){
          var raw = vEl.textContent, num = parseFloat(raw);
          if(raw !== '' && !isNaN(num) && /^-?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(raw)){
            if(sAttr != null && dateS[sAttr] && num > 0 && num < 2958466) val = fmtDate(serialToDate(num));
            else val = num;
          } else val = raw;
        }
        arr[ci] = val;
        if(ci > maxc) maxc = ci;
      }
      for(var k = 0; k <= maxc; k++) if(arr[k] === undefined) arr[k] = '';
      /* 整行空白就丢掉（xlsx 里常带大量空行占位） */
      var any = arr.some(function(x){ return x !== '' && x != null; });
      if(any) out.push(arr);
    }
    return out;
  }
  /* 裁掉右侧与底部整列/整行为空的部分 */
  function trimGrid(g){
    if(!g.length) return [];
    var rows = g.length, cols = 0;
    g.forEach(function(r){ if(r.length > cols) cols = r.length; });
    while(cols > 0){
      var empty = true;
      for(var i = 0; i < rows; i++){ var v = g[i][cols-1]; if(v !== '' && v != null){ empty = false; break; } }
      if(!empty) break;
      cols--;
    }
    var out = [];
    for(var r = 0; r < rows; r++){
      var line = [];
      for(var c = 0; c < cols; c++){ var v = g[r][c]; line.push(v == null ? '' : v); }
      var any = line.some(function(x){ return x !== ''; });
      if(any) out.push(line);
    }
    return out;
  }
  /* 主入口：ArrayBuffer → {sheet 名: 二维数组} */
  function parseXlsx(buf){
    var b = new Uint8Array(buf), idx = zipIndex(b);
    var need = ['xl/workbook.xml', 'xl/_rels/workbook.xml.rels', 'xl/sharedStrings.xml', 'xl/styles.xml'];
    var task = {};
    need.forEach(function(n){ task[n] = unzipEntry(b, idx[n]); });
    var sheetNames = Object.keys(idx).filter(function(n){ return /^xl\/worksheets\/sheet\d+\.xml$/.test(n); });
    sheetNames.forEach(function(n){ task[n] = unzipEntry(b, idx[n]); });
    return Promise.all(need.concat(sheetNames).map(function(n){ return task[n]; })).then(function(list){
      var map = {};
      need.concat(sheetNames).forEach(function(n, i){ map[n] = list[i]; });
      var shared = map['xl/sharedStrings.xml'] ? parseShared(xmlDoc(map['xl/sharedStrings.xml'])) : [];
      var dateS  = map['xl/styles.xml'] ? parseStyles(xmlDoc(map['xl/styles.xml'])) : {};
      /* 工作表顺序 + 显示名 */
      var order = [], nameByRid = {};
      if(map['xl/_rels/workbook.xml.rels']){
        var rd = xmlDoc(map['xl/_rels/workbook.xml.rels']).getElementsByTagName('Relationship');
        for(var i = 0; i < rd.length; i++){
          var tg = String(rd[i].getAttribute('Target') || '').replace(/^\/?xl\//, '').replace(/^\//, '');
          nameByRid[rd[i].getAttribute('Id')] = 'xl/' + tg;
        }
      }
      if(map['xl/workbook.xml']){
        var sh = xmlDoc(map['xl/workbook.xml']).getElementsByTagName('sheet');
        for(var j = 0; j < sh.length; j++){
          var rid = sh[j].getAttribute('r:id') || sh[j].getAttribute('id');
          var path = nameByRid[rid] || ('xl/worksheets/sheet' + (j + 1) + '.xml');
          order.push({name: sh[j].getAttribute('name') || ('工作表' + (j + 1)), path: path});
        }
      }
      if(!order.length) order = sheetNames.map(function(n, i){ return {name:'工作表' + (i + 1), path:n}; });
      var out = {}, cnt = 0;
      order.forEach(function(o){
        var u8 = map[o.path] || map[o.path.replace('xl/', '')];
        if(!u8) return;
        var g = sheetGrid(xmlDoc(u8), shared, dateS);
        g = trimGrid(g);
        if(g.length){ out[o.name] = g; cnt++; }
      });
      if(!cnt) throw new Error('没有解析到任何数据行（工作表是空的？）');
      return out;
    });
  }
  /* CSV / TSV：支持双引号包裹、逗号或制表符 */
  function parseCsv(text){
    text = String(text).replace(/^\uFEFF/, '');
    var firstLine = text.split(/\r?\n/)[0] || '';
    var cand = [',', '\t', ';'];
    var delim = ',', best = -1;
    cand.forEach(function(d){
      var n = firstLine.split(d).length;
      if(n > best){ best = n; delim = d; }
    });
    var rows = [], cur = [], cell = '', q = false;
    for(var i = 0; i < text.length; i++){
      var ch = text[i];
      if(q){
        if(ch === '"'){ if(text[i+1] === '"'){ cell += '"'; i++; } else q = false; }
        else cell += ch;
      } else if(ch === '"') q = true;
      else if(ch === delim){ cur.push(cell); cell = ''; }
      else if(ch === '\n'){ cur.push(cell); rows.push(cur); cur = []; cell = ''; }
      else if(ch === '\r'){ /* 跳过 */ }
      else cell += ch;
    }
    cur.push(cell);
    rows.push(cur);
    var maxc = 0;
    rows.forEach(function(r){ if(r.length > maxc) maxc = r.length; });
    var out = [];
    rows.forEach(function(r){
      var line = r.map(function(x){ return x == null ? '' : x.trim(); });
      while(line.length < maxc) line.push('');
      if(line.some(function(x){ return x !== ''; })) out.push(line);
    });
    return trimGrid(out);
  }

  return { parseXlsx: parseXlsx, parseCsv: parseCsv, serialToDate: serialToDate,
           colIdx: colIdx, trimGrid: trimGrid, fmtDate: fmtDate };
})();
