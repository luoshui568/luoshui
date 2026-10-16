#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""十字光标验证：注入合成 mousemove 后截图 + 输出状态，用于确认图区内十字线可见。"""
import os
import subprocess
import build_daily

BASE = os.path.dirname(os.path.abspath(__file__))
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
SHOTS = '/tmp/shots'

DIAG = r'''
<div id="dbg" style="position:fixed;left:0;bottom:0;z-index:99999;background:#000;color:#0f0;
  font:12px monospace;padding:4px 6px;line-height:1.5;white-space:pre-wrap;max-width:1400px"></div>
<script>
window.addEventListener('load', function(){
  var rafRan = 0;
  requestAnimationFrame(function(){ rafRan++; });
  window.__force = location.hash === '#draw';
  var info = [], cnt = 0, err = '';
  setTimeout(function(){
    var cv = document.getElementById('cv'), r = cv.getBoundingClientRect();
    var x = r.left + r.width*0.62, y = r.top + r.height*0.42;
    cv.dispatchEvent(new MouseEvent('mousemove',
      {clientX:x, clientY:y, bubbles:true, cancelable:true}));
    var a = chart.chartArea || {};
    info.push('on=' + XH.on + ' XH=' + XH.x.toFixed(1) + ',' + XH.y.toFixed(1));
    info.push('area=' + [a.left,a.top,a.right,a.bottom].map(function(v){return (v||0).toFixed(0);}).join('/'));
    info.push('cv=' + chart.canvas.clientWidth + 'x' + chart.canvas.clientHeight + ' raf=' + rafRan);
    info.push('ds=' + chart.data.datasets.length + ' xhair=' + state.xhair);
    // 插件是否注册 / 是否挂到实例上 / afterDraw 是否被调用
    var P = Chart.registry.plugins.get('xhair');
    info.push('plugObj=' + !!P + ' hasAfterDraw=' + !!(P && P.afterDraw));
    var svc = chart._plugins;
    info.push('svc=' + Object.keys(svc || {}).join('|'));
    var arr = (svc && (svc._plugins || svc.plugins || svc._cache)) || [];
    info.push('attached=[' + [].map.call(arr, function(o){
      return o.id || (o.plugin && o.plugin.id) || (o.options && o.options.id) || '?'; }).join(',') + ']');
    if(P){
      var orig = P.afterDraw;
      P.afterDraw = function(){ cnt++; try{ return orig.apply(this, arguments); }catch(e){ err = String(e && (e.message||e)); } };
    }
    chart.draw();
    setTimeout(function(){
      info.push('afterDrawCalls=' + cnt + ' err=' + (err || 'none'));
      // 直接读画布像素：确认十字线是否真的进了位图
      var g = chart.ctx, dpr = chart.currentDevicePixelRatio || 1;
      var pick = function(cx, cy){
        var d = g.getImageData(Math.round(cx*dpr), Math.round(cy*dpr), 1, 1).data;
        return d[0] + ',' + d[1] + ',' + d[2];
      };
      info.push('dpr=' + dpr);
      info.push('像素 竖线上=' + pick(XH.x, 40) + '  竖线中=' + pick(XH.x, 300) +
                '  横线上=' + pick(400, XH.y) + '  空白=' + pick(400, 40));
      // 把画布位图当图片贴到页面上（衬不透明底），验证截图链路
      var box = document.createElement('div');
      box.style.cssText = 'position:fixed;left:0;top:0;width:659px;height:314px;background:#070a10;' +
        'z-index:99998;border:2px solid #0f0;overflow:hidden';
      var img = document.createElement('img');
      img.src = chart.canvas.toDataURL();
      img.style.cssText = 'display:block;width:659px';
      box.appendChild(img);
      document.body.appendChild(box);
      document.getElementById('dbg').textContent = info.join('\n');
    }, 200);
  }, 900);
});
</script>
'''


def shot(name, html_path, w=1440, h=2400, force=False):
    os.makedirs(SHOTS, exist_ok=True)
    png = f'{SHOTS}/{name}.png'
    cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
           '--hide-scrollbars', f'--window-size={w},{h}', '--virtual-time-budget=5000',
           f'--screenshot={png}', f'file://{html_path}' + ('#draw' if force else '')]
    subprocess.run(cmd, capture_output=True, timeout=180)
    return png


def dump(html_path, w=1440, h=2400):
    dom = subprocess.run([EDGE, '--headless=new', '--no-sandbox', '--disable-gpu',
                          '--disable-dev-shm-usage', f'--window-size={w},{h}',
                          '--virtual-time-budget=5000', '--dump-dom', f'file://{html_path}'],
                         capture_output=True, timeout=180).stdout.decode('utf-8', 'ignore')
    i = dom.find('id="dbg"')
    return dom[i:i + 420].split('>')[1].split('<')[0] if i > 0 else 'DBG NOT FOUND'


if __name__ == '__main__':
    html = build_daily.build(DIAG)
    p = f'{BASE}/t_xh.html'
    open(p, 'w', encoding='utf-8').write(html)
    print('DBG:', dump(p))
    print('png:', shot('xh', p, force=True))
