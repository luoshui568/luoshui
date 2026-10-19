# -*- coding: utf-8 -*-
"""生成 `build/block_font.css` —— 把**阿里巴巴普惠体 3.0** 的子集以 base64 内嵌。

为什么要内嵌而不是外链：
    研报是**单文件离线页**（可直接拖进浏览器、可邮件发、可存 U 盘），
    外链 CDN 在离线场景直接失效 ⇒ 字体必须躺在 HTML 里。

为什么要子集化：
    普惠体原文件 Regular 4.85 MB / Bold 5.09 MB，两个字重 base64 后 13 MB，
    页面直接废掉。按「全库实际用字 + GB2312 一级常用字」裁到 4,191 字后
    各 626 KB，base64 合计约 1.67 MB（页面 2.2 MB → 约 3.9 MB）。

    ★ 为什么留 GB2312 一级（3,755 字）而不是只留实际用字（2,256 字）：
      研报还在持续写新公司，生僻人名/地名一旦不在子集里就会掉回系统字体，
      同一段里出现两种字形。多花的 600 KB 买这个保险值。

重新生成（字体或字符集变了才需要跑）：
    python3 build/make_font_css.py            # 只生成 CSS
    python3 build/make_font_css.py --fetch    # 顺便重下原字体并重做子集

⚠️ `build/font/*.woff2` 与 `build/block_font.css` 都**不入库**（.gitignore）：
   体积大、且是派生物。换机器时按上面 --fetch 重跑即可。
"""
import base64
import io
import os
import subprocess
import sys

REPO = '/Users/luoshui/WorkBuddy/2026-10-10-22-59-27/luoshui'
FONTDIR = os.path.join(REPO, 'build', 'font')
OUT = os.path.join(REPO, 'build', 'block_font.css')
REG = os.path.join(FONTDIR, 'apht-regular.woff2')
BOLD = os.path.join(FONTDIR, 'apht-bold.woff2')
CHARSET = os.path.join(FONTDIR, 'charset.txt')

# 官方镜像（raw.githubusercontent.com 在本机被墙，只能走 api.github.com）
GH = ('https://api.github.com/repos/LuRenDing2020/'
      'AlibabaPuHuiTi-Fonts-Resource/contents/Alibaba-PuHuiTi-%s.woff2')

FAMILY = 'Alibaba PuHuiTi'
STACK = ('"Alibaba PuHuiTi","Alibaba PuHuiTi 3.0","AlibabaPuHuiTi",'
         '"PingFang SC","Hiragino Sans GB","Microsoft YaHei",'
         'system-ui,-apple-system,"Segoe UI",sans-serif')


def fetch_and_subset():
    """下载原字体 → 按字符集裁 → 落盘。需要 fonttools + brotli。"""
    os.makedirs(FONTDIR, exist_ok=True)
    for name, dst in (('Regular', REG), ('Bold', BOLD)):
        raw = os.path.join(FONTDIR, '_raw_%s.woff2' % name.lower())
        print('  下载 %s …' % name, end=' ', flush=True)
        # ★ 必须校验字节数：api.github.com 偶尔截断，截断的 woff2 会让
        #   fontTools 报 "brotli: decoder failed"（踩过一次）
        for attempt in range(4):
            subprocess.run(['curl', '-sSL', '--max-time', '280',
                            '-H', 'Accept: application/vnd.github.raw',
                            '-o', raw, GH % name], check=False)
            if os.path.getsize(raw) > 4_000_000:
                break
            print('重试%d…' % (attempt + 1), end=' ', flush=True)
        print('%.2f MB' % (os.path.getsize(raw) / 1e6))
        subprocess.run([sys.executable, '-m', 'fontTools.subset', raw,
                        '--text-file=' + CHARSET, '--flavor=woff2',
                        '--no-hinting', '--output-file=' + dst], check=True)
        os.remove(raw)
        print('  子集 %s → %.0f KB' % (name, os.path.getsize(dst) / 1024))


def face(weight, path):
    b64 = base64.b64encode(open(path, 'rb').read()).decode('ascii')
    return (
        '@font-face{\n'
        '  font-family:"%s";\n'
        '  src:url(data:font/woff2;base64,%s) format("woff2");\n'
        '  font-weight:%d;font-style:normal;font-display:swap;\n'
        '}\n' % (FAMILY, b64, weight)
    )


def main():
    if '--fetch' in sys.argv:
        fetch_and_subset()
    for p in (REG, BOLD):
        assert os.path.exists(p), '缺字体 %s ⇒ 先跑 make_font_css.py --fetch' % p

    css = ['/* ===== 阿里巴巴普惠体 3.0（子集内嵌 · %d/%d KB）=====' %
           (os.path.getsize(REG) // 1024, os.path.getsize(BOLD) // 1024),
           ' * 由 build/make_font_css.py 生成，**不要手改**。',
           ' * 覆盖写法用 `*` + !important：主题里有 4 处 font-family（含宋体首列），',
           ' * 不加 !important 压不住；全站唯一字体是用户明确要求。',
           ' */']
    css.append(face(400, REG))
    css.append(face(700, BOLD))
    css.append('*,*::before,*::after{font-family:%s !important;}\n' % STACK)

    txt = '\n'.join(css)
    io.open(OUT, 'w', encoding='utf-8').write(txt)
    print('产物 %s  %.2f MB' % (OUT, len(txt.encode('utf-8')) / 1e6))
    print('  @font-face 条数:', txt.count('@font-face'))
    print('  全局规则:', 'font-family' in txt.split('@font-face')[-1])


if __name__ == '__main__':
    main()
