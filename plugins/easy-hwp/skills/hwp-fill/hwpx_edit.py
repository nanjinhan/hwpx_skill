# -*- coding: utf-8 -*-
"""
hwpx_edit — HWPX 서식을 안전하게 편집하기 위한 헬퍼.

핵심 원칙:
  1. 빈 셀의 기존 <hp:p>를 템플릿으로 복제 → 원본 서식(폰트/정렬) 보존
  2. 저장 직전 <hp:linesegarray>를 전부 제거 → 한글이 레이아웃을 재계산
     (이걸 안 하면 모든 줄이 같은 좌표에 겹쳐 그려짐)
  3. mimetype은 ZIP_STORED로 맨 앞에 넣어 재압축

사용 예:
    from hwpx_edit import HwpxDoc

    doc = HwpxDoc.open(r'form.hwpx')
    s = doc.section(0)
    s.set_cell(0, 1, 0, ['AI 기반 의료영상 진단'])   # (표index, col, row, 줄목록)
    s.append_cell(1, 0, 1, ['', '■ 연구 배경', ' - ...'])
    s.clone_rows(9, src_row=2, n=9)                # 표에 행 9개 추가
    doc.save(r'out.hwpx')
    HwpxDoc.verify(r'out.hwpx', r'final.hwpx')     # 한글로 열고 재저장 + 검증
"""
import copy
import io
import os
import re
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET

HPU = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
HP = '{%s}' % HPU


# --------------------------------------------------------------------------
# 텍스트 추출 — <hp:fwSpace/> 같은 자식 요소가 섞이면 .text만 읽으면 첫 글자만
# 나온다. 반드시 자식의 .tail 까지 이어붙여야 전체 텍스트가 나온다.
# --------------------------------------------------------------------------
def node_text(el):
    buf = []
    for t in el.iter(HP + 't'):
        if t.text:
            buf.append(t.text)
        for kid in t:
            if kid.tail:
                buf.append(kid.tail)
    return ''.join(buf)


def replace_text(scope, old, new, limit=None):
    """scope 안의 hp:t 텍스트(및 자식 tail)에서 old를 new로 치환. 치환 횟수 반환."""
    n = 0
    for t in scope.iter(HP + 't'):
        if limit is not None and n >= limit:
            break
        if t.text and old in t.text:
            t.text = t.text.replace(old, new, 1)
            n += 1
            continue
        for kid in t:
            if kid.tail and old in kid.tail:
                kid.tail = kid.tail.replace(old, new, 1)
                n += 1
                break
    return n


class SectionEditor(object):
    def __init__(self, root, path, decl):
        self.root = root
        self.path = path
        self.decl = decl

    # ---------- 조회 ----------
    @property
    def tables(self):
        """문서 순서대로의 <hp:tbl> 목록 (중첩표 포함)."""
        return [e for e in self.root.iter() if e.tag == HP + 'tbl']

    def table(self, idx):
        return self.tables[idx]

    def cell(self, tbl_idx, col, row):
        """cellAddr(colAddr,rowAddr)로 셀을 찾는다. 병합셀은 시작 좌표만 존재."""
        for tr in self.table(tbl_idx).findall(HP + 'tr'):
            for tc in tr.findall(HP + 'tc'):
                a = tc.find(HP + 'cellAddr')
                if a.get('colAddr') == str(col) and a.get('rowAddr') == str(row):
                    return tc
        raise KeyError('table %d: cell (%s,%s) 없음' % (tbl_idx, col, row))

    def cell_text(self, tbl_idx, col, row):
        return node_text(self.cell(tbl_idx, col, row))

    def top_paragraphs(self):
        """표 밖의 최상위 본문 문단."""
        return [p for p in self.root if p.tag == HP + 'p']

    # ---------- 문단 생성 ----------
    @staticmethod
    def _make_para(template, text):
        """템플릿 문단을 복제해 text를 담은 문단을 만든다.

        마지막 run을 남기는 이유: 안내문 문단은 보통 [들여쓰기용 작은 run, 본문 run]
        구조라서 마지막 run이 본문 글자 스타일을 갖고 있다.
        """
        p = copy.deepcopy(template)
        runs = p.findall(HP + 'run')
        for r in runs[:-1]:
            p.remove(r)
        r = p.findall(HP + 'run')[-1]
        for t in r.findall(HP + 't'):
            r.remove(t)
        if text:
            t = ET.Element(HP + 't')
            t.text = text
            r.insert(0, t)
        return p

    # ---------- 편집 ----------
    def set_cell(self, tbl_idx, col, row, lines, tmpl_idx=0):
        """셀 내용을 lines로 교체. lines의 각 원소가 한 문단이 된다."""
        sl = self.cell(tbl_idx, col, row).find(HP + 'subList')
        ps = sl.findall(HP + 'p')
        tmpl = copy.deepcopy(ps[min(tmpl_idx, len(ps) - 1)])
        for p in ps:
            sl.remove(p)
        for line in lines:
            sl.append(self._make_para(tmpl, line))

    def append_cell(self, tbl_idx, col, row, lines, tmpl_idx=0):
        """기존 내용(안내문 등)은 두고 뒤에 문단을 덧붙인다."""
        sl = self.cell(tbl_idx, col, row).find(HP + 'subList')
        ps = sl.findall(HP + 'p')
        tmpl = copy.deepcopy(ps[min(tmpl_idx, len(ps) - 1)])
        for line in lines:
            sl.append(self._make_para(tmpl, line))

    def set_para(self, idx, newtext):
        """최상위 문단 하나를 단일 run + 단일 텍스트로 재작성."""
        p = self.top_paragraphs()[idx]
        runs = p.findall(HP + 'run')
        for r in runs[:-1]:
            p.remove(r)
        r = p.findall(HP + 'run')[-1]
        for kid in list(r):
            r.remove(kid)
        t = ET.Element(HP + 't')
        t.text = newtext
        r.append(t)

    def sub_para(self, idx, pattern, repl):
        """최상위 문단에 정규식 치환. 공백 개수를 못 믿을 때 쓴다(\\s* 활용)."""
        p = self.top_paragraphs()[idx]
        cur = node_text(p)
        new = re.sub(pattern, repl, cur)
        if new == cur:
            return False
        self.set_para(idx, new)
        return True

    def append_para(self, idx, text):
        """최상위 문단 끝에 텍스트만 덧붙인다(기존 서식/fwSpace 보존)."""
        p = self.top_paragraphs()[idx]
        r = p.findall(HP + 'run')[-1]
        t = ET.Element(HP + 't')
        t.text = text
        r.append(t)

    def replace_text(self, old, new, limit=None, scope=None):
        return replace_text(scope if scope is not None else self.root, old, new, limit)

    def check_boxes(self, keyword, empty=u'□', filled=u'■', limit=1):
        """'동의하십니까' 같은 키워드가 있는 문단마다 첫 체크박스를 채운다.

        표를 품은 상위 문단은 건너뛴다(중복 치환 방지).
        한글 기호 폰트 체크박스는 empty='\\uf06f', filled='\\uf06e' 를 쓸 것.
        """
        n = 0
        for p in self.root.iter(HP + 'p'):
            if p.find('.//' + HP + 'tbl') is not None:
                continue
            txt = node_text(p)
            if keyword in txt and empty in txt:
                if replace_text(p, empty, filled, limit):
                    n += 1
        return n

    def clone_rows(self, tbl_idx, src_row, n):
        """표에 행을 n개 추가한다. src_row 행을 복제하고 rowAddr / rowCnt / 표 높이 보정."""
        tbl = self.table(tbl_idx)
        trs = tbl.findall(HP + 'tr')
        src = trs[src_row]
        anchor = list(tbl).index(src)
        row_h = None
        for tc in src.findall(HP + 'tc'):
            cs = tc.find(HP + 'cellSz')
            if cs is not None:
                row_h = int(cs.get('height'))
                break
        for k in range(n):
            new = copy.deepcopy(src)
            for a in new.iter(HP + 'cellAddr'):
                a.set('rowAddr', str(src_row + 1 + k))
            tbl.insert(anchor + 1 + k, new)
        tbl.set('rowCnt', str(len(tbl.findall(HP + 'tr'))))
        sz = tbl.find(HP + 'sz')
        if sz is not None and row_h:
            sz.set('height', str(int(sz.get('height')) + row_h * n))

    # ---------- 저장 ----------
    def strip_linesegs(self):
        """★ 레이아웃 캐시 제거. 이걸 빼먹으면 글자가 겹쳐 나온다."""
        n = 0
        for p in self.root.iter(HP + 'p'):
            for ls in p.findall(HP + 'linesegarray'):
                p.remove(ls)
                n += 1
        return n

    def write(self):
        body = ET.tostring(self.root, encoding='unicode')
        io.open(self.path, 'w', encoding='utf-8').write(self.decl + body)


class HwpxDoc(object):
    def __init__(self, work, names):
        self.work = work
        self.names = names
        self._sections = {}

    # ---------- 열기 ----------
    @classmethod
    def open(cls, src, work=None):
        if work is None:
            work = tempfile.mkdtemp(prefix='hwpx_')
        elif os.path.isdir(work):
            shutil.rmtree(work)
            os.makedirs(work)
        else:
            os.makedirs(work)
        with zipfile.ZipFile(src) as z:
            names = z.namelist()
            z.extractall(work)
        return cls(work, names)

    def section(self, i):
        if i not in self._sections:
            path = os.path.join(self.work, 'Contents', 'section%d.xml' % i)
            raw = io.open(path, encoding='utf-8').read()
            # 원본 네임스페이스 접두사를 유지해야 한글이 읽는다
            for pre, uri in re.findall(r'xmlns:([A-Za-z0-9_]+)="([^"]+)"', raw[:6000]):
                ET.register_namespace(pre, uri)
            decl = raw[:raw.index('?>') + 2] if raw.startswith('<?xml') \
                else '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            self._sections[i] = SectionEditor(ET.fromstring(raw), path, decl)
        return self._sections[i]

    def section_count(self):
        return len([n for n in self.names
                    if re.match(r'Contents/section\d+\.xml$', n)])

    # ---------- 저장 ----------
    def save(self, dst, strip_layout=True):
        stripped = 0
        for ed in self._sections.values():
            if strip_layout:
                stripped += ed.strip_linesegs()
            ed.write()
        if os.path.exists(dst):
            os.remove(dst)
        zf = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
        try:
            # mimetype은 반드시 맨 앞 + 무압축
            if 'mimetype' in self.names:
                zf.write(os.path.join(self.work, 'mimetype'), 'mimetype',
                         zipfile.ZIP_STORED)
            for n in self.names:
                if n == 'mimetype':
                    continue
                p = os.path.join(self.work, n.replace('/', os.sep))
                if os.path.isfile(p):
                    zf.write(p, n)
        finally:
            zf.close()
        return stripped

    def close(self):
        shutil.rmtree(self.work, ignore_errors=True)

    # ---------- 검증 ----------
    @staticmethod
    def verify(src, dst):
        """한글로 열었다가 재저장 → 파싱 성공 확인 + 레이아웃 재생성.
        Windows + 한컴오피스 + pyhwpx 필요. (pages, bytes) 반환."""
        from pyhwpx import Hwp
        hwp = Hwp(visible=False, new=False)
        hwp.open(os.path.abspath(src))
        pages = hwp.PageCount
        hwp.save_as(os.path.abspath(dst))
        hwp.quit()
        return pages, os.path.getsize(dst)

    @staticmethod
    def check_layout(path, max_report=20):
        """겹침 검사: 한 셀/문단 흐름 안에서 vertpos가 중복되면 글자가 겹친 것.
        문제가 있는 위치 목록을 반환(비어 있으면 정상)."""
        work = tempfile.mkdtemp(prefix='hwpxchk_')
        bad = []
        try:
            with zipfile.ZipFile(path) as z:
                z.extractall(work)
            cdir = os.path.join(work, 'Contents')
            secs = sorted(f for f in os.listdir(cdir)
                          if re.match(r'section\d+\.xml$', f))
            for sec in secs:
                root = ET.parse(os.path.join(cdir, sec)).getroot()
                # 표 셀(subList)만 검사한다. 최상위 본문은 쪽이 바뀔 때
                # vertpos가 0부터 다시 시작해서 중복이 정상적으로 생긴다.
                for box in root.iter(HP + 'subList'):
                    seq = []
                    # 직속 문단의 '자기' linesegarray만 본다.
                    # p.iter()를 쓰면 중첩표 안쪽 셀까지 긁어와 오탐이 난다.
                    for p in box.findall(HP + 'p'):
                        for lsa in p.findall(HP + 'linesegarray'):
                            for ls in lsa.findall(HP + 'lineseg'):
                                seq.append(int(ls.get('vertpos') or 0))
                    # 판정 기준: '연속한' 두 줄의 vertpos가 같으면 포개져 그려진 것.
                    # 값이 줄어드는 건 쪽이 넘어가며 좌표가 리셋된 정상 케이스라
                    # 단순 중복 집계로는 오탐이 난다.
                    hits = sum(1 for a, b in zip(seq, seq[1:]) if a == b)
                    if hits:
                        bad.append('%s 겹친줄=%d/%d 내용=%r'
                                   % (sec, hits, len(seq), node_text(box)[:50]))
                        if len(bad) >= max_report:
                            return bad
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return bad
