---
name: hwp-fill
description: 한글 서식(.hwp, .hwpx)에 내용을 채웁니다. "서식 채우기", "hwp 작성", "한글 파일 채우기" 요청시 사용합니다.
---

# 한글 파일 채우기

## 입력
$ARGUMENTS

---

## ⚠️ 가장 먼저 읽을 것 — 글자 겹침의 진짜 원인

hwpx의 모든 `<hp:p>`에는 `<hp:linesegarray>`가 붙어 있다. **각 줄을 세로 몇 번째 좌표에 그릴지 적어둔 레이아웃 캐시**다.

문단을 복제해서 내용을 채우면 이 캐시까지 복사된다. 그러면 새로 만든 10줄이 전부 `vertpos=1000` 같은 **똑같은 좌표**를 갖게 되고, 한글은 그 값을 그대로 믿고 **한 자리에 전부 포개서 그린다.** 화면에는 글자가 뭉개져 보인다.

한 줄짜리 텍스트도 칸이 좁아 두 줄로 접혀야 하는데 캐시에 줄 정보가 1개뿐이면 같은 증상이 난다.

**한글은 이 캐시를 자동으로 재계산하지 않는다.** 파일을 열었다가 `save_as`로 다시 저장해도 안 고쳐진다.

### 해결책 — 저장 직전에 linesegarray를 전부 제거한다

```python
HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
for p in root.iter(HP + 'p'):
    for ls in p.findall(HP + 'linesegarray'):
        p.remove(ls)
```

캐시가 없으면 한글이 열 때 처음부터 다시 계산한다. 아래 `hwpx_edit` 모듈의 `save()`가 이걸 자동으로 한다.

> **하지 말 것**: "한 문단을 35자 이하로 쪼개서 한 줄에 맞춘다"는 식의 대응. 증상만 가리는 틀린 처방이고, 문장이 부자연스럽게 끊기며 칸 폭이 조금만 달라져도 다시 깨진다.

---

## 권장 절차 — `hwpx_edit` 모듈 사용

이 스킬 폴더에 검증된 헬퍼가 들어 있다: `hwpx_edit.py`

스킬이 실행되면 **Base directory**가 안내된다. 그 경로를 `sys.path`에 넣고 import한다.
(플러그인 설치 시 `~/.claude/plugins/.../skills/hwp-fill/`, 수동 설치 시 `~/.claude/skills/hwp-fill/`)

```python
import sys
sys.path.insert(0, SKILL_DIR)   # 스킬 Base directory
from hwpx_edit import HwpxDoc

doc = HwpxDoc.open(r'서식.hwpx')
s0 = doc.section(0)
s1 = doc.section(1)                    # 섹션이 여러 개인 서식도 있다

# 셀 채우기 — (표index, col, row, 줄목록)
s0.set_cell(0, 1, 0, ['AI 기반 의료영상 진단 시스템 개발'])
s0.set_cell(0, 2, 1, ['① 첫 줄', '② 둘째 줄', '③ 셋째 줄'])

# 안내문은 남기고 뒤에 덧붙이기
s1.append_cell(1, 0, 1, ['', '■ 연구 배경', ' - 내용...'])

# 표에 행 추가 (일정표 등)
s1.clone_rows(9, src_row=2, n=9)

doc.save(r'중간산출.hwpx')                        # linesegarray 자동 제거 + 재압축
HwpxDoc.verify(r'중간산출.hwpx', r'최종.hwpx')     # 한글로 열고 재저장(레이아웃 재계산)
print(HwpxDoc.check_layout(r'최종.hwpx'))          # []가 나와야 정상
doc.close()
```

### 주요 API

| 메서드 | 용도 |
|--------|------|
| `HwpxDoc.open(경로)` | 압축 해제 후 편집 세션 시작 |
| `.section(i)` | i번째 섹션 편집기 |
| `.save(경로)` | linesegarray 제거 + mimetype 무압축 선두 배치로 재압축 |
| `.close()` | 임시 디렉토리 정리 |
| `HwpxDoc.verify(src, dst)` | 한글로 열고 재저장 → 파싱 성공 확인 + 레이아웃 재생성 |
| `HwpxDoc.check_layout(경로)` | 글자 겹침 검사. 빈 리스트면 정상 |
| `sec.set_cell(t, c, r, lines)` | 셀 내용 교체 |
| `sec.append_cell(t, c, r, lines)` | 셀 끝에 문단 추가 |
| `sec.cell_text(t, c, r)` | 셀 전체 텍스트 읽기 |
| `sec.clone_rows(t, src_row, n)` | 표 행 복제 추가 |
| `sec.set_para(i, text)` / `.sub_para(i, 정규식, 치환)` / `.append_para(i, text)` | 표 밖 본문 문단 편집 |
| `sec.check_boxes(키워드)` | 체크박스 채우기 |
| `sec.replace_text(old, new)` | 전역 텍스트 치환 |

---

## 반드시 지킬 규칙

### 1. 셀은 좌표(`cellAddr`)로 찾는다

`<hp:tc>` 안의 `<hp:cellAddr colAddr="2" rowAddr="0"/>`가 진짜 주소다. 몇 번째 `<hp:tc>`인지로 세면 **병합셀 때문에 어긋난다**. 병합된 칸은 시작 좌표에만 셀이 존재하고 나머지 좌표는 아예 없다.

반복 컬럼이 있는 표(분기별 일정표 등)는 채운 뒤 **행 단위로 덤프해서 정렬을 눈으로 확인**할 것. 사람이 세는 "3분기"와 `colAddr`가 한 칸씩 어긋나기 쉽다.

### 2. 텍스트를 읽을 때 `.tail`까지 이어붙인다

라벨에 `<hp:fwSpace/>`(균등분할 공백)가 섞여 있으면 `t.text`만 읽을 때 **첫 글자만** 나온다.

```xml
<hp:t>매<hp:fwSpace/><hp:fwSpace/>출<hp:fwSpace/>원가(-)</hp:t>
```
→ `t.text`는 `'매'`뿐. 자식 요소의 `.tail`을 모아야 `'매출원가(-)'`가 된다. `hwpx_edit.node_text()`가 처리해 준다.

### 3. 서식은 기존 문단을 복제해서 보존한다

새 `<hp:p>`를 맨손으로 만들면 폰트/정렬/들여쓰기가 다 깨진다. 그 칸에 이미 있는 빈 문단을 deepcopy해서 `<hp:t>`만 갈아끼운다.

run이 여러 개면 **마지막 run**을 남긴다. 안내문 문단은 보통 `[들여쓰기용 작은 run, 본문 run]` 구조라 마지막 run이 본문 글자 스타일을 갖고 있다.

### 4. 재압축 시 `mimetype`은 맨 앞 + 무압축

```python
zf.write(mimetype_path, 'mimetype', zipfile.ZIP_STORED)   # 먼저
# 나머지 파일은 ZIP_DEFLATED
```

### 5. 네임스페이스 접두사를 유지한다

파싱 전에 원본의 `xmlns:` 선언을 모두 `ET.register_namespace()`로 등록해야 한글이 읽는다. 안 하면 `ns0:` 같은 접두사로 바뀐다.

### 6. 체크박스 문자

| 상황 | 빈 칸 | 채운 칸 |
|------|-------|---------|
| 일반 텍스트 | `□` U+25A1 | `■` U+25A0 |
| 한글 기호 폰트 | `\uf06f` | `\uf06e` |

동의서처럼 같은 문구가 여러 번 나오면, **표를 품은 상위 문단은 건너뛰고** 말단 문단만 처리해야 중복 치환이 안 난다. 텍스트 노드가 쪼개져 있을 수 있으니 문단 전체 텍스트로 판정할 것.

---

## 검증 절차 (생략 금지)

텍스트 대조만으로는 **겹침을 절대 못 잡는다.** 내용은 다 들어가 있는데 화면만 깨지기 때문이다.

1. `doc.save()` → `HwpxDoc.verify()`로 한글에서 열리는지 확인
2. `HwpxDoc.check_layout()`이 빈 리스트인지 확인 ← **이걸 꼭 해야 한다**
3. 재저장본을 다시 풀어 셀 단위로 내용 대조
4. 사용자에게 "직접 열어서 확인해 달라"고 안내

`check_layout`은 한 칸 안에서 **연속한 두 줄의 `vertpos`가 같은지**를 본다. 값이 줄어드는 건 쪽이 넘어가며 좌표가 리셋된 정상 케이스라 단순 중복 집계로는 오탐이 난다.

파일 크기도 신호다. 캐시를 제거하면 줄었다가, 한글이 재저장하면서 다시 커지면 재계산이 일어난 것.

---

## pyhwpx 직접 사용 (누름틀 필드가 있는 서식)

서식에 "누름틀" 필드가 정의돼 있으면 XML을 건드릴 필요 없이 간단하다.

```python
from pyhwpx import Hwp
hwp = Hwp(visible=False, new=False)
hwp.open("서식.hwp")                    # .hwp, .hwpx 모두 지원
print(hwp.get_field_list())             # 필드가 비어 있으면 XML 방식으로 전환
hwp.put_field_text("연구과제명", "AI 기반 진단 시스템")
hwp.save_as("결과.hwp")
hwp.quit()
```

**요구 환경**: Windows + 한컴오피스 한글 설치 + `pip install pyhwpx`. (검증 환경: 한글 2022, pyhwpx 1.7.2 + pywin32)

첫 실행 시 pyhwpx가 보안모듈 `FilePathCheckerModule.dll`을 `HKCU\SOFTWARE\HNC\HwpAutomation\Modules`에 자동 등록한다. 이게 없으면 파일을 열 때마다 보안 승인 팝업이 떠서 자동화가 멈춘다.

macOS/Linux에는 한글 프로그램이 없어 pyhwpx를 쓸 수 없다 → XML 편집 방식만 사용 가능(`.hwpx` 한정). 이때는 `verify()`를 건너뛰게 되는데, `save()`가 linesegarray를 제거해 두므로 사용자가 한글에서 처음 열 때 레이아웃이 계산된다.

`.hwp`(구형 바이너리)는 XML 편집이 불가능하므로 pyhwpx 경로만 쓸 수 있다.

### pyhwpx로 백지 문서에 본문을 새로 쓸 때 (Windows에서 검증된 함정)

| 증상 | 원인 | 대응 |
|------|------|------|
| 문단이 전부 한 줄로 붙음 | `BreakPara()`가 `False`를 반환하며 동작 안 함 | `insert_text(chr(13)+chr(10))`로 줄바꿈 삽입 |
| 실행이 멈춤 (보이지 않는 창) | `set_style("바탕글")`이 "스타일로 덮어쓸까요?" 모달 창을 띄움 | `set_style` 쓰지 말고 `set_para`/`set_font`만 사용 |
| 표 내용이 첫 칸에 몰림 | `table_from_data`가 데이터를 한 셀에 덤프 | `create_table(rows, cols)` 후 `goto_addr("A1")` 식으로 칸마다 `insert_text` |
| 제목행 색이 마지막 칸에도 칠해짐 | 셀을 채운 뒤 `cell_fill`하면 캐럿 위치가 어긋남 | 표 생성 직후(캐럿이 A1일 때) 제목행 `TableCellBlockRow` → `cell_fill` 먼저 |

### 표 좌우 여백 규칙 (필수)

표를 만들 때마다 **열 너비 비율을 바꾼 직후 반드시 `hwp.set_table_width()`를 호출**한다. 인수 없이 부르면 표 전체가 본문 폭(용지 − 좌우 여백)에 맞춰져 왼쪽·오른쪽 여백이 같아진다. 이걸 빼먹으면 `set_col_width([1, 3])` 같은 비율 지정 뒤 표가 오른쪽 여백을 넘어간다.

```python
hwp.create_table(rows, cols, treat_as_char=True, header=True)
hwp.TableCellBlock(); hwp.TableCellBlockRow(); hwp.cell_fill((225, 232, 245)); hwp.Cancel()
hwp.goto_addr("A1")
if ratios:
    hwp.set_col_width(list(ratios))
hwp.set_table_width()          # ← 모든 표에 반드시. 좌우 여백 동일하게
for r in range(rows):
    for c in range(cols):
        hwp.goto_addr(f"{chr(65 + c)}{r + 1}")
        hwp.insert_text(str(data[r][c]))
hwp.MoveDocEnd()
```

2열짜리 표에서 비율 지정이 자꾸 넘치면 비율을 빼고 균등 폭으로 둔다. 만든 뒤에는 PDF로 저장해 페이지를 이미지로 렌더링하고 **표가 오른쪽 여백 안에 들어왔는지 눈으로 확인**한다.

---

## 수정 요청 시 기준 파일 (필수)

**사용자가 마지막으로 저장한 파일이 항상 기준이다.** 생성 스크립트를 다시 돌려 처음부터 새로 만들면 사용자가 한글에서 직접 고친 내용이 전부 사라진다.

- 수정 요청이 오면 **디스크에 있는 현재 파일을 열어** 요청한 부분만 고치고 같은 파일에 저장한다.
- 생성 스크립트(build_report.py 등)는 **최초 1회 생성용**이다. 한 번이라도 사용자에게 파일을 넘긴 뒤에는 다시 돌리지 않는다. 구조를 크게 바꿔야 하면 사용자에게 먼저 말하고 동의 후 진행한다.
- 수정 전에 파일 수정 시각을 확인하고, 내가 마지막으로 저장한 시각보다 나중이면 사용자가 손댄 것이므로 **그 상태를 그대로 보존**한 채 부분 수정한다.
- 수정 전에 한글에서 그 파일이 열려 있으면 닫아달라고 먼저 요청한다 (열려 있으면 저장이 막힌다).
- **파일 시각 확인만으로는 부족하다.** 사용자가 고쳤지만 저장을 안 했거나 다른 이름으로 저장했을 수 있다. 사용자에게 파일을 넘긴 뒤 다시 수정할 때는 매번 먼저 "한글에서 고친 내용 있으면 저장하고 닫아주세요. 다 됐으면 알려주세요"라고 묻고, **사용자가 확인한 뒤에만** 수정한다. 사용자가 직접 수정을 요청한 같은 메시지 안에서도 이 확인을 건너뛰지 않는다.
- 부분 수정 방법: pyhwpx로 열어 `find`/`goto_addr`로 위치를 찾아 고치거나, `hwpx_edit`로 XML의 해당 셀/문단만 바꾼다.

---

## 내용 매칭

MD 등에서 필드-값을 뽑을 때 이름이 정확히 안 맞아도 유연하게 매칭한다 (`과제명`→`연구과제명`, 띄어쓰기 무시). 다만 후보가 여럿이거나 의미가 달라질 수 있으면 임의로 고르지 말고 확인할 것.

사용자가 직접 채워야 하는 개인정보(휴대폰, 생년월일 등)는 **공란으로 두고 작업 끝에 한 번에 모아서 알려준다.** 중간에 멈춰 묻지 않는다.

---

## 출력

- 기본 파일명: `{원본}_filled.hwpx`, 사용자가 지정하면 그 이름
- 원본 서식은 수정하지 않는다. 단, 한 번 만든 `_filled` 파일은 이후 수정 요청 때 **그 파일 자체를** 고친다 (위 "수정 요청 시 기준 파일" 참고)
- 보고 시: 채운 항목 / 못 채운 항목 / **생성된 파일의 전체 경로**를 명시
