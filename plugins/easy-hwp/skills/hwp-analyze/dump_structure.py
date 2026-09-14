# -*- coding: utf-8 -*-
"""
hwpx 서식의 표/문단 구조를 덤프한다. 채우기 전 좌표를 파악하는 용도.

사용법:
    python dump_structure.py 서식.hwpx 출력.txt [--paras]

출력 예:
    === SECTION 0 · TABLE 1 (rows=15) ===
      R0  | (0,0)[cs2 rs1]'창업아이템명' | (2,0)[cs7 rs1]''
    → set_cell(0, 2, 0, ['값'])  로 (col=2, row=0) 칸을 채우면 된다.

주의: 콘솔이 cp949라 한글 출력이 깨지므로 반드시 파일로 받는다.
"""
import io
import os
import re
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'


def node_text(el):
    """<hp:fwSpace/> 같은 자식이 섞여도 전체 텍스트를 얻는다.
    t.text만 읽으면 첫 글자만 나오므로 자식의 .tail까지 모은다."""
    buf = []
    for t in el.iter(HP + 't'):
        if t.text:
            buf.append(t.text)
        for kid in t:
            if kid.tail:
                buf.append(kid.tail)
    return ''.join(buf)


def dump(src, dst, with_paras=False):
    work = tempfile.mkdtemp(prefix='hwpxdump_')
    try:
        with zipfile.ZipFile(src) as z:
            z.extractall(work)
        cdir = os.path.join(work, 'Contents')
        secs = sorted(f for f in os.listdir(cdir)
                      if re.match(r'section\d+\.xml$', f))
        out = io.open(dst, 'w', encoding='utf-8')
        out.write('파일: %s\n섹션 %d개\n' % (os.path.basename(src), len(secs)))

        for si, sec in enumerate(secs):
            root = ET.parse(os.path.join(cdir, sec)).getroot()

            if with_paras:
                out.write('\n\n########## SECTION %d · 최상위 문단 ##########\n' % si)
                idx = 0
                for p in root:
                    if p.tag != HP + 'p':
                        continue
                    has_tbl = p.find('.//' + HP + 'tbl') is not None
                    out.write('[%03d]%s %r\n'
                              % (idx, ' <TBL>' if has_tbl else '',
                                 node_text(p)[:150]))
                    idx += 1

            tbls = [e for e in root.iter() if e.tag == HP + 'tbl']
            out.write('\n\n########## SECTION %d · 표 %d개 ##########\n'
                      % (si, len(tbls)))
            for ti, tbl in enumerate(tbls):
                rows = tbl.findall(HP + 'tr')
                out.write('\n=== TABLE %d (index=%d, rows=%d) ===\n'
                          % (ti + 1, ti, len(rows)))
                for ri, tr in enumerate(rows):
                    parts = []
                    for tc in tr.findall(HP + 'tc'):
                        a = tc.find(HP + 'cellAddr')
                        addr = '(%s,%s)' % (a.get('colAddr'), a.get('rowAddr'))
                        sp = ''
                        s = tc.find(HP + 'cellSpan')
                        if s is not None:
                            cs, rs = s.get('colSpan'), s.get('rowSpan')
                            if cs != '1' or rs != '1':
                                sp = '[cs%s rs%s]' % (cs, rs)
                        np_ = len(tc.find(HP + 'subList').findall(HP + 'p'))
                        txt = node_text(tc).strip()
                        parts.append('%s%s%s%r'
                                     % (addr, sp,
                                        ('{%dp}' % np_) if np_ > 1 else '',
                                        txt[:60]))
                    out.write('  R%-2d | %s\n' % (ri, ' | '.join(parts)))
        out.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return dst


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    dump(src, dst, '--paras' in sys.argv)
    print('WROTE %s' % dst)
