# -*- coding: utf-8 -*-
"""
build.py —— 從 src/ 組出可直接部署的「321聖經講義－啟示錄」三語網站。

用法：
    python3 build.py            # 組建
    python3 build.py --check    # 資料健檢（節數、六層、缺漏）

源碼結構：
    src/book.json                書卷資訊（三語書名、章數、顏色等）
    src/app/{tc,sc,en}/shell.html  外殼（含 __BOOK__ __DATA__ __APP__ 等佔位）
    src/app/{tc,sc,en}/app.js      程式（書卷相關內容一律讀 BOOK 物件）
    src/data/{tc,sc,en}/data.json  各語言的講義內容
    src/sw.js.tpl                  Service Worker 模板

輸出（皆在專案根目錄，可直接給 GitHub Pages 用）：
    index.html   繁體中文
    sc.html      简体中文
    en.html      English
    sw.js        Service Worker（離線快取）

三個語言版本平放在同一層，靠檔名互連 —— 網站放在網域根目錄或子路徑都能運作。
"""
import os, sys, json, hashlib

BASE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(BASE, 'src')
APP  = os.path.join(SRC, 'app')
DATA = os.path.join(SRC, 'data')

LANGS = [('tc', 'index.html', 'zh-Hant'),
         ('sc', 'sc.html',    'zh-Hans'),
         ('en', 'en.html',    'en')]


def book():
    return json.load(open(os.path.join(SRC, 'book.json'), encoding='utf-8'))


def sha(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()[:12]


# ── 組出一個語言版本 ────────────────────────────────────
def render(bk, lang):
    m     = bk[lang]
    d     = os.path.join(APP, lang)
    shell = open(os.path.join(d, 'shell.html'), encoding='utf-8').read()
    app   = open(os.path.join(d, 'app.js'),     encoding='utf-8').read()
    data  = json.dumps(json.load(open(os.path.join(DATA, lang, 'data.json'), encoding='utf-8')),
                       ensure_ascii=False, separators=(',', ':'))

    # 單卷版：sw.js 與頁面同層；沒有書架，__HOME__ 指回自己
    runtime = dict(id=bk['id'], ch=bk['ch'], hue=bk['hue'],
                   name=m['name'], app=m['app'], verses=m['verses'],
                   src=m['src'], bible=m['bible'], desc=m['desc'],
                   chword=m['chword'], author=m['author'], abbr=m['abbr'],
                   short=m['short'],
                   sw='./sw.js')

    out = (shell
           .replace('__APPNAME__',   m['app'])
           .replace('__SHORTNAME__', m['short'])
           .replace('__DESC__',    m['desc'])
           .replace('__HUE__',     bk['hue'])
           .replace('__HOME__',    './' + dict(LANGS_FILE)[lang])
           .replace('__BOOK__',    json.dumps(runtime, ensure_ascii=False, separators=(',', ':')))
           .replace('__DATA__',    data)
           .replace('__APP__',     app))

    for ph in ('__APPNAME__', '__SHORTNAME__', '__DESC__', '__HUE__', '__HOME__',
               '__BOOK__', '__DATA__', '__APP__'):
        assert ph not in out, f'{lang}：佔位 {ph} 未被取代'
    return out


LANGS_FILE = [(k, f) for k, f, _ in LANGS]


def render_sw(digest):
    tpl = open(os.path.join(SRC, 'sw.js.tpl'), encoding='utf-8').read()
    shell = ['./'] + ['./' + f for _, f, _ in LANGS] + ['./icon-512.png']
    return (tpl.replace('__VERSION__', digest)
               .replace('__SHELL__', json.dumps(shell, ensure_ascii=False)))


def do_build():
    bk = book()
    pages = {}
    for lang, fname, _ in LANGS:
        pages[fname] = render(bk, lang)

    digest = sha(''.join(pages[f] for _, f, _ in LANGS))
    for fname, html in pages.items():
        open(os.path.join(BASE, fname), 'w', encoding='utf-8').write(html)
        print(f'  ✓ {fname}　{len(html)/1024/1024:.2f} MB')

    open(os.path.join(BASE, 'sw.js'), 'w', encoding='utf-8').write(render_sw(digest))
    print(f'  ✓ sw.js　版本 {digest}')
    print('\n組建完成。直接把整個資料夾推上 GitHub，開啟 Pages 即可。')


# ── 資料健檢 ────────────────────────────────────────────
def do_check():
    bk = book()
    LAYERS = ('lit', 'key', 'gram', 'exp')
    ok = True
    print(f'═══ {bk["tc"]["name"]}（{bk["id"]}）═══')
    for lang, _, _ in LANGS:
        m = bk[lang]
        D = json.load(open(os.path.join(DATA, lang, 'data.json'), encoding='utf-8'))
        verses = sum(len(v) for v in D['txt'].values())
        blocks = sum(len(v) for v in D['blk'].values())
        sermons = sum(1 for v in D.get('serm', {}).values() if v.get('blocks'))
        print(f'  【{m["name"]}】經節 {verses}　解經段 {blocks}　講章 {sermons}/{bk["ch"]}')

        # 逐節覆蓋
        gaps = []
        for c in sorted(D['blk'], key=int):
            need = set(range(1, len(D['txt'][c]) + 1))
            got = set()
            for b in D['blk'][c]:
                got |= set(range(b['a'], b['z'] + 1))
            if need - got:
                gaps.append(f'{c}章缺 {sorted(need - got)}')
        print('    逐節覆蓋：' + ('完整 ✓' if not gaps else '✗ ' + '；'.join(gaps)))
        ok &= not gaps

        # 六層缺漏
        miss = {f: sum(1 for c in D['blk'] for b in D['blk'][c] if not b.get(f)) for f in LAYERS}
        miss = {k: v for k, v in miss.items() if v}
        print('    六層缺漏：' + ('無 ✓' if not miss else f'✗ {miss}'))
        ok &= not miss

    print('\n' + ('全部正常 ✓' if ok else '有問題，請看上面 ✗'))
    return 0 if ok else 1


if __name__ == '__main__':
    if '--check' in sys.argv:
        sys.exit(do_check())
    do_build()
