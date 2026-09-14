---
name: hwp-analyze
description: 한글 파일(.hwp, .hwpx)의 구조를 분석합니다. "hwp 분석", "서식 분석", "한글 파일 구조" 요청시 사용합니다.
---

# 한글 파일 분석

## 입력
$ARGUMENTS

---

## 권장 절차 — 구조 덤프 스크립트

이 스킬 폴더의 `dump_structure.py`가 표 좌표까지 한 번에 뽑아준다.
스킬 실행 시 안내되는 **Base directory** 아래에 있다.

```bash
python "<스킬폴더>/dump_structure.py" 서식.hwpx 구조.txt --paras
```

`--paras`를 붙이면 표 밖의 최상위 문단 목록도 같이 나온다 (날짜·서명란처럼 표가 아닌 자리를 채워야 할 때 필요).

**출력을 반드시 파일로 받을 것.** Windows 콘솔 기본 인코딩이 cp949라 한글을 직접 출력하면 깨진다.

### 출력 읽는 법

```
=== TABLE 1 (index=0, rows=15) ===
  R0  | (0,0)[cs2 rs1]'창업아이템명' | (2,0)[cs7 rs1]''
  R7  | (1,7)'연락처' | (2,7)'휴대폰' | (3,7)[cs2 rs1]'' | (5,7)[cs2 rs1]'이메일' | (7,7)[cs2 rs1]''
```

| 표기 | 의미 |
|------|------|
| `index=0` | `/hwp-fill`에서 쓸 표 번호 (0부터) |
| `(2,0)` | `colAddr=2, rowAddr=0` — 이게 셀의 진짜 주소 |
| `[cs2 rs1]` | 가로 2칸 병합 |
| `{3p}` | 문단이 3개 (여러 줄이 들어 있는 칸) |
| `''` | 빈 칸 = 채워야 할 자리 |

위 예에서 휴대폰 값은 `(3,7)`, 이메일 값은 `(7,7)`에 넣는다 → `set_cell(0, 3, 7, ['010-...'])`

---

## 반드시 알아야 할 함정

### 1. 셀 위치는 `cellAddr`로만 판단한다

몇 번째 `<hp:tc>`인지로 세면 **병합셀 때문에 어긋난다.** 병합된 칸은 시작 좌표에만 셀이 존재하고 나머지 좌표는 아예 없다. 위 R7을 보면 col 4, 6이 없다.

### 2. 텍스트를 읽을 때 `.tail`까지 이어붙인다

라벨에 `<hp:fwSpace/>`(균등분할 공백)가 섞여 있으면 `t.text`만 읽을 때 **첫 글자만** 나온다.

```xml
<hp:t>매<hp:fwSpace/><hp:fwSpace/>출<hp:fwSpace/>원가(-)</hp:t>
```
→ `t.text`는 `'매'`뿐. `dump_structure.node_text()`가 처리해 준다. 직접 파싱할 때 `'매'`, `'판'`, `'특'` 같은 한 글자 라벨이 나오면 이 함정에 빠진 것이다.

### 3. 중첩표에 주의

`root.iter()`로 `<hp:tbl>`을 모으면 **표 안의 표까지** 순서대로 들어온다. 동의서처럼 바깥 표가 안쪽 표들을 감싼 구조가 흔하다. 바깥 표의 셀 텍스트를 읽으면 안쪽 표 내용이 전부 딸려 나온다.

### 4. 섹션이 여러 개일 수 있다

`Contents/section0.xml`만 보면 절반을 놓친다. 긴 서식은 `section1.xml`에 본문이 들어 있는 경우가 많다.

---

## 파일 구조

```
hwpx(=ZIP)/
├── mimetype              # 무압축·맨 앞에 있어야 함
├── Contents/
│   ├── header.xml        # 글자모양(charPr)·문단모양(paraPr)·글꼴 정의
│   ├── section0.xml      # 본문
│   └── section1.xml      # 추가 섹션
├── META-INF/
├── settings.xml
└── Preview/PrvText.txt   # 텍스트 미리보기(빠른 확인용)
```

### 주요 태그

| 태그 | 의미 |
|------|------|
| `<hp:tbl>` | 표 (`rowCnt`, `colCnt` 속성) |
| `<hp:tr>` / `<hp:tc>` | 행 / 셀 |
| `<hp:cellAddr>` | 셀 좌표 (`colAddr`, `rowAddr`) |
| `<hp:cellSpan>` | 병합 (`colSpan`, `rowSpan`) |
| `<hp:subList>` | 셀 안의 문단 컨테이너 |
| `<hp:p>` | 문단 (`paraPrIDRef`) |
| `<hp:run>` | 글자 속성 구간 (`charPrIDRef`) |
| `<hp:t>` | 텍스트 |
| `<hp:linesegarray>` | **레이아웃 캐시** — 편집 시 반드시 제거 (`/hwp-fill` 참고) |

네임스페이스: `hp` = `http://www.hancom.co.kr/hwpml/2011/paragraph`, `hh` = `.../2011/head`

---

## 글꼴 확인 (기호 문자가 이상할 때)

`\uf06f` 같은 사용자 영역(PUA) 문자가 보이면 `header.xml`에서 해당 `charPr`의 `fontRef`를 따라가 글꼴을 확인한다. 한글 기호 체크박스는 `\uf06f`(빈 칸) / `\uf06e`(채운 칸) 쌍이다.

---

## Windows: pyhwpx로 누름틀 필드 확인

```python
from pyhwpx import Hwp
hwp = Hwp(visible=False, new=False)
hwp.open("서식.hwp")          # .hwp, .hwpx 모두 지원
fields = hwp.get_field_list()
print(fields)                  # 비어 있으면 XML 방식으로 분석해야 함
hwp.quit()
```

누름틀이 있으면 `/hwp-fill`에서 `put_field_text()`로 간단히 채울 수 있다. 대부분의 관공서 서식은 누름틀이 없어서 표 셀을 직접 다뤄야 한다.

`.hwp`(구형 바이너리)는 ZIP이 아니라 XML 분석이 불가능하다 → pyhwpx만 사용 가능.

---

## 사용자에게 알려줄 것

- 섹션 수, 표 개수
- 채워야 할 빈 칸 목록 (표 index + 좌표로)
- 행 추가가 필요한 표 (예: 일정표에 데이터 행이 1개뿐)
- 연도·기간처럼 **수정**해야 하는 기존 값 (예: `2020년도` → 실제 연도)
- 다음 단계: `/hwp-fill`로 채우기
