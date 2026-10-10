# -*- coding: utf-8 -*-
"""生成「图表聚焦预览页」：从 deploy/report.html 复制一份，只留指定模块，并且
   用一段注入脚本把「非图表内容」全部隐藏 —— 每张图独占一行全宽，方便目视核查
   美化层的真实效果（不用 PIL 裁图，直接把图本身放大）。

   用法： _mk_gallery.py <输出html> <模块起> <模块止>     # 索引闭开区间
   例：   _mk_gallery.py build/_g1.html 0 2              # 第 0~1 个含图模块
"""
import io, json, os, re, sys

SRC = r'deploy\report.html'
SEED = r'build\seed\report_600456.json'

# 聚焦脚本：① 保留通往 [data-chart] 的整条祖先链 ② 其余全部隐藏
#           ③ 祖先链强制成块级（免得 .grid2 把图挤成半栏）④ 容器放大后手动 resize
FOCUS_JS = """
<script>
setTimeout(function(){
  var CH = document.querySelectorAll('#mods [data-chart]');
  if(!CH.length) return;
  /* keep = 通往图表的整条祖先链 ＋ 图表自身的整棵子树 ＋ 工具条子树
     ⚠️ 只保祖先链是不够的 —— ECharts 画出来的 canvas 是 [data-chart] 的后代，
        漏掉就会被一并 display:none，页面看着就是一张空卡（2026-09-17 踩过）。 */
  var kset = new Set();
  function keep(el){ if(el && !kset.has(el)) kset.add(el); }
  function keepChain(el){ while(el && el.id !== 'mods'){ keep(el); el = el.parentNode; } }
  for(var i = 0; i < CH.length; i++){
    keepChain(CH[i]);
    var sub = CH[i].querySelectorAll('*');
    for(var s = 0; s < sub.length; s++) keep(sub[s]);
  }
  var tb = document.querySelectorAll('#mods .rpt-toolbar');
  for(var q = 0; q < tb.length; q++){
    keepChain(tb[q]);
    var sb = tb[q].querySelectorAll('*');
    for(var r = 0; r < sb.length; r++) keep(sb[r]);
  }
  var all = document.querySelectorAll('#mods *');
  for(var j = 0; j < all.length; j++){
    if(!kset.has(all[j])) all[j].style.setProperty('display', 'none', 'important');
  }
  /* ⚠️ 这里千万别给 keep 全集无脑套 display:block —— keep 里含**卡片祖先链**，
     一设就把每一张含图卡片全点亮了，截图上只看得到最靠前那几张，后面批次的图
     会和第一批一模一样（2026-09-17 踩过）。栅格展平已由 CSS 阶段负责。 */
  for(var m = 0; m < CH.length; m++){
    CH[m].style.setProperty('display', 'block', 'important');
    CH[m].style.setProperty('height', '430px', 'important');
    CH[m].style.setProperty('margin', '10px 0 26px', 'important');
    CH[m].style.setProperty('width', '100%', 'important');
    var ins = (window.echarts && echarts.getInstanceByDom) ? echarts.getInstanceByDom(CH[m]) : null;
    if(ins) try{ ins.resize(); }catch(e){}
  }
}, 900);
</script>
"""


def mods_with_charts():
    o = json.loads(io.open(SEED, encoding='utf-8').read())
    out = []
    for m in sorted(o['mods'], key=lambda x: x.get('order') or x.get('seq') or 0):
        ids = re.findall(r'data-chart="([^"]+)"', m.get('html') or '')
        if ids:
            out.append((str(m.get('no')), ids))
    return out


def build(dst, lo, hi, src=None):
    t = io.open(src or SRC, encoding='utf-8').read()
    rows = mods_with_charts()
    sel = rows[lo:hi]
    nos = [n for n, _ in sel]
    ids = [i for _, ii in sel for i in ii]
    sel_css = ','.join('#mods .card#m%s' % n for n in nos)
    css = (
        '<style id="gallery">\n'
        '/* 图表聚焦预览：只留目标卡片，其余（侧栏、导航、其他模块）全隐藏 */\n'
        '.wrap > *:not(#mods){display:none!important;}\n'
        '#mods{display:block!important;}\n'
        '#mods > *{display:none!important;}\n'
        '%s{display:block!important;margin:0 0 16px!important;}\n'
        '/* 栅格容器必须在 CSS 阶段就摊平 —— 等 JS 再改，ECharts 早就按半栏宽度初始化完了 */\n'
        '#mods .grid2,#mods .grid3,#mods .grid4{display:block!important;}\n'
        '.wrap{padding:12px!important;max-width:none!important;}\n'
        'body{background:#fafafa!important;}\n'
        '*{animation:none!important;transition:none!important;}\n'
        '</style>\n' % sel_css
    )
    i = t.rfind('</html>')
    out = t[:i] + css + FOCUS_JS + t[i:]
    io.open(dst, 'w', encoding='utf-8').write(out)
    print('%-26s 模块 %-14s 图 %d 张: %s'
          % (os.path.basename(dst), ','.join(nos), len(ids), ' '.join(ids)))
    return len(ids)


if __name__ == '__main__':
    dst, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    build(dst, lo, hi)
    if len(sys.argv) <= 4:
        rows = mods_with_charts()
        print('\n含图表的模块共 %d 个 / 图 %d 张：'
              % (len(rows), sum(len(i) for _, i in rows)))
        for k, (n, ii) in enumerate(rows):
            print('  [%2d] m%-5s %s' % (k, n, ' '.join(ii)))
