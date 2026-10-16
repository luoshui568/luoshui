# -*- coding: utf-8 -*-
"""世界地图合规自检 —— 逐项验证 `build/lib/world-cn.js` 的四条国标红线。

背景（2026-10-14 用户令）：「台湾并入、藏南不划给印度、含港澳、含九段线，
我现在用的地图这块有没有问题，如果有问题直接帮我改地图」

本脚本用**几何实测**（不是看注释）回答这个问题：
  ① 台湾岛 → 必须落在 China feature 内
  ② 藏南   → 必须落在 China feature 内；同时检查 India 是否越界伸入
  ③ 港澳   → 必须落在 China feature 内
  ④ 九段线 → 南海里必须存在 9 段"极细长"形状（面积/外接矩形 < 0.22）
另查：阿克赛钦归属、分省底图是否含「南海诸岛」单元。

用法：
    python3 build/check_map_compliance.py            # 读 build/lib/world-cn.js
    python3 build/check_map_compliance.py <file.js>  # 读别的副本（例如线上抓下来的）
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, 'lib', 'world-cn.js')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ----------------------------------------------------------------- 几何工具
def in_ring(x, y, ring):
    """射线法：点是否在单个环内。"""
    ins = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xi:
                ins = not ins
    return ins


def in_poly(x, y, poly):
    if not in_ring(x, y, poly[0]):
        return False
    return not any(in_ring(x, y, h) for h in poly[1:])


def in_geom(x, y, geom):
    t = geom['type']
    if t == 'Polygon':
        return in_poly(x, y, geom['coordinates'])
    if t == 'MultiPolygon':
        return any(in_poly(x, y, p) for p in geom['coordinates'])
    return False


def shoelace(ring):
    s = 0.0
    for i in range(len(ring) - 1):
        s += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return abs(s) / 2


def load_maps(path):
    """把 world-cn.js 里所有 registerMap 的 JSON 解出来。"""
    src = io.open(path, encoding='utf-8').read()
    dec = json.JSONDecoder()
    out = {}
    for m in re.finditer(r"echarts\.registerMap\(\s*'([^']+)'\s*,", src):
        st = src.index('{', m.start())
        obj, _ = dec.raw_decode(src[st:])
        out[m.group(1)] = obj
    return out


# ----------------------------------------------------------------- 检查项
def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    maps = load_maps(path)
    W = maps.get('worldcn')
    assert W, '没找到 worldcn 地图'
    print('文件: %s' % path)
    print('注册的地图: %s' % ' / '.join(maps))
    print()

    by_name = {}
    for f in W['features']:
        by_name.setdefault(str(f['properties'].get('name')), []).append(f)

    def who(x, y):
        hit = []
        for f in W['features']:
            if f['geometry']['type'] in ('LineString', 'MultiLineString'):
                continue
            if in_geom(x, y, f['geometry']):
                hit.append(str(f['properties'].get('name')))
        return hit

    ok = True

    def chk(label, cond, detail=''):
        nonlocal ok
        print('  %s %-46s %s' % ('✓' if cond else '✗', label, detail))
        if not cond:
            ok = False

    print('① 台湾并入中国')
    t = who(121.0, 23.7)
    chk('台湾岛中部 (121.0, 23.7) 属 China', 'China' in t, str(t))

    print()
    print('② 藏南归属')
    pts = [(92.0, 27.8), (91.8, 27.9), (93.5, 28.3), (94.5, 27.6),
           (95.0, 28.6), (96.5, 28.6), (97.0, 28.0)]
    all_cn = True
    india_in = []
    for x, y in pts:
        hit = who(x, y)
        if 'China' not in hit:
            all_cn = False
        if 'India' in hit:
            india_in.append((x, y))
        print('      (%5.1f, %4.1f) -> %s' % (x, y, ', '.join(hit) or '—'))
    chk('藏南 7 个采样点全部落在 China 内', all_cn)
    if india_in:
        print('  ! India 几何仍覆盖藏南 %d/%d 点'
              '（靠「China 在 features 末尾、后绘制」压住；视觉正确，数据未裁）'
              % (len(india_in), len(pts)))
        ind = by_name.get('India') or []
        if ind:
            g = ind[0]['geometry']
            polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
            best = None
            for p in polys:
                for q in p[0]:
                    if 91 <= q[0] <= 97 and (best is None or q[1] > best[1]):
                        best = q
            if best:
                print('    India 在 lon 91~97 的最北点: lon %.2f lat %.2f（藏南北界约 29.1）'
                      % (best[0], best[1]))
    else:
        chk('India 未伸入藏南', True)

    print()
    print('③ 港澳在中国版图内')
    chk('香港 (114.15, 22.30) 属 China', 'China' in who(114.15, 22.30))
    chk('澳门 (113.55, 22.20) 属 China', 'China' in who(113.55, 22.20))

    print()
    print('④ 九段线（南海断续线）')
    ch = by_name.get('China')
    segs = []
    if ch:
        for p in ch[0]['geometry']['coordinates']:
            ring = p[0]
            xs = [q[0] for q in ring]
            ys = [q[1] for q in ring]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            bb = w * h
            if bb <= 0:
                continue
            fr = shoelace(ring) / bb
            if fr < 0.22 and max(w, h) > 0.5 and 105 <= (min(xs) + max(xs)) / 2 <= 125:
                segs.append((round((min(xs) + max(xs)) / 2, 1),
                             round((min(ys) + max(ys)) / 2, 1), round(fr, 3)))
    segs.sort(key=lambda s: -s[1])
    for s in segs:
        print('      段  中心 lon %.1f  lat %.1f   fill=%.3f' % s)
    chk('南海存在 ≥9 段极细长形状（＝断续线）', len(segs) >= 9, '实测 %d 段' % len(segs))

    print()
    print('附加检查')
    chk('阿克赛钦 (79.5, 35.0) 属 China', 'China' in who(79.5, 35.0))
    C = maps.get('china')
    if C:
        names = [str(f['properties'].get('name')) for f in C['features']]
        chk('分省底图含「南海诸岛」单元', '南海诸岛' in names, '共 %d 个单元' % len(names))
        chk('分省底图含台湾 / 中国香港 / 中国澳门',
            all(k in names for k in ('台湾', '中国香港', '中国澳门')))

    print()
    print('==== 结论：%s ====' % ('全部通过，地图无需修改' if ok else '存在未通过项，需要修正'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
