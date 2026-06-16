---
name: hwp-fill
description: 한글 서식(.hwp, .hwpx)에 내용을 채웁니다. "서식 채우기", "hwp 작성", "한글 파일 채우기" 요청시 사용합니다.
---

# 한글 파일 채우기

## 입력
$ARGUMENTS

## OS별 처리 방법

### Windows: pyhwpx 사용 (권장)

Windows + 한글 프로그램이 설치된 환경에서는 pyhwpx를 사용합니다.

```python
from pyhwpx import Hwp

hwp = Hwp()
hwp.open("서식.hwp")  # .hwp, .hwpx 모두 지원

# 필드에 값 채우기
hwp.put_field_text("연구과제명", "AI 기반 진단 시스템")
hwp.put_field_text("연구책임자", "홍길동")

# 저장
hwp.save_as("결과.hwp")
hwp.quit()
```

**pyhwpx 설치**: `pip install pyhwpx`

**참고**: pyhwpx는 한글 문서의 "누름틀" 필드를 사용합니다. 서식에 누름틀이 없으면 표 셀을 직접 찾아서 수정해야 합니다.

### macOS/Linux: XML 직접 수정 (.hwpx만 지원)

#### 처리 절차

##### 1. HWPX 압축 해제

```bash
mkdir -p {임시디렉토리}
unzip -o {서식}.hwpx -d {임시디렉토리}/
```

##### 2. 서식 파일 분석

`{임시디렉토리}/Contents/section0.xml` 파일을 읽어서:
- 표(`<hp:tbl>`) 찾기
- 각 행의 첫 번째 셀에서 필드명 추출
- 두 번째 셀이 비어있으면 채워야 할 항목

##### 3. 내용 파악

MD 파일 또는 사용자 제공 내용에서 필드-값 추출:
```markdown
# 연구과제명
AI 기반 진단 시스템

## 연구책임자
홍길동
```
→ `{"연구과제명": "AI 기반 진단 시스템", "연구책임자": "홍길동"}`

##### 4. 스마트 매칭

필드명이 정확히 일치하지 않아도 **유연하게 매칭**:
- `과제명` → `연구과제명` (부분 포함)
- `책임자` → `연구책임자` (유사어)
- `연구 기간` → `연구기간` (띄어쓰기 무시)

**애매하면 반드시 사용자에게 확인**:
- 여러 후보가 있을 때
- 의미가 다를 수 있을 때
- 매칭할 필드를 못 찾았을 때

##### 5. 매칭 결과 확인

사용자에게 매칭 결과를 보여주고 확인 받기:
```
매칭 결과:
- 연구과제명 ← "AI 기반 진단 시스템"
- 연구책임자 ← "홍길동"
- 연구기간 ← (내용 없음)

진행하시겠습니까?
```

##### 6. XML 수정

Edit 도구를 사용하여 `section0.xml`의 해당 셀 내용을 수정:

**수정 전**:
```xml
<hp:tc><hp:p><hp:t></hp:t></hp:p></hp:tc>
```

**수정 후**:
```xml
<hp:tc><hp:p><hp:t>홍길동</hp:t></hp:p></hp:tc>
```

주의: 빈 `<hp:t>` 태그나 `<hp:t/>` 를 찾아서 값을 채웁니다.

##### 7. 재압축

```bash
cd {임시디렉토리}
zip -r {출력파일}.hwpx *
```

**중요**: 압축 시 반드시 임시디렉토리 안에서 실행해야 합니다.

##### 8. 정리

```bash
rm -rf {임시디렉토리}
```

---

## 새 단락 삽입 (텍스트 추가 / 답안 작성)

표 셀이 아닌 **본문에 새 단락을 삽입**할 때의 절차입니다.

### 6-A. 글자 색상(charPr) 추가

`header.xml`의 `hh:charProperties`에 새 charPr을 추가합니다.

```xml
<!-- itemCnt 를 기존값+1 로 변경 -->
<hh:charProperties itemCnt="9">
  ...기존 charPr들...
  <!-- 파란색(#0000FF) 추가: 기존 최대 id+1 사용 -->
  <hh:charPr id="8" height="1000" textColor="#0000FF" shadeColor="none"
    useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="2">
    <hh:fontRef hangul="1" latin="1" hanja="1" japanese="1" other="1" symbol="1" user="1"/>
    <hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>
    <hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>
    <hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>
    <hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>
    <hh:underline type="NONE" shape="SOLID" color="#000000"/>
    <hh:strikeout shape="NONE" color="#000000"/>
    <hh:outline type="NONE"/>
    <hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/>
  </hh:charPr>
</hh:charProperties>
```

### 6-B. 단락 XML 구조

삽입할 단락의 기본 구조:

```xml
<hp:p id="2147483648" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="8">
    <hp:t>여기에 텍스트</hp:t>
  </hp:run>
  <hp:linesegarray>
    <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000"
      baseline="850" spacing="600" horzpos="0" horzsize="42520" flags="393216"/>
  </hp:linesegarray>
</hp:p>
```

### 6-C. ⚠️ lineseg 오버플로우 방지 — 반드시 준수

`linesegarray`는 단락 내 각 **시각적 줄(line)**의 레이아웃 정보를 담습니다.
삽입 시 lineseg를 **1개만** 사용하므로, 텍스트가 한 줄을 넘으면 한글 프로그램이 렌더링을 실패해 **글자가 깨집니다**.

**규칙: 단락 하나에 한 줄에 들어오는 분량만 넣는다.**

| 문자 종류 | 단락당 최대 글자 수 |
|-----------|---------------------|
| 한글 위주 | 35자 이하 |
| 영문/숫자 위주 | 70자 이하 |
| 한글+영문 혼합 | 40자 이하 |

긴 문장은 반드시 여러 개의 `<hp:p>` 단락으로 분리합니다:

```
# 잘못된 예 (한 단락에 긴 문장 → 글자 깨짐)
"이유: 무선 링크는 잡음, 페이딩, 간섭으로 비트 오류가 자주 발생한다. 상위 계층(TCP)의 재전송에만 의존하면 왕복 지연(RTT)이 크므로, PHY 레벨에서 FEC 등을 이용해 즉시 오류를 정정하는 것이 효율적이다."

# 올바른 예 (35자 이하 단락으로 분리)
"이유: 무선 링크는 잡음, 페이딩, 간섭으로"
"오류가 자주 발생."
"TCP 재전송만 의존 시 RTT 지연 큼."
"PHY에서 FEC로 즉시 정정(local recovery)."
```

### 6-D. 삽입 위치 찾기 (PowerShell 예시)

```powershell
function Make-ColoredP {
    param([string]$text, [int]$charPrId = 8)
    return "<hp:p id=""2147483648"" paraPrIDRef=""0"" styleIDRef=""0"" pageBreak=""0"" columnBreak=""0"" merged=""0""><hp:run charPrIDRef=""$charPrId""><hp:t>$text</hp:t></hp:run><hp:linesegarray><hp:lineseg textpos=""0"" vertpos=""0"" vertsize=""1000"" textheight=""1000"" baseline=""850"" spacing=""600"" horzpos=""0"" horzsize=""42520"" flags=""393216""/></hp:linesegarray></hp:p>"
}

function Insert-After {
    param([ref]$xmlRef, [string]$anchor, [string[]]$lines, [int]$charPrId = 8)
    $idx = $xmlRef.Value.IndexOf("<hp:t>$anchor</hp:t>")
    if ($idx -lt 0) { Write-Host "WARNING: 앵커 없음 -> $anchor"; return }
    $closeIdx = $xmlRef.Value.IndexOf("</hp:p>", $idx) + "</hp:p>".Length
    $insert = ($lines | ForEach-Object { Make-ColoredP $_ $charPrId }) -join ""
    $xmlRef.Value = $xmlRef.Value.Substring(0, $closeIdx) + $insert + $xmlRef.Value.Substring($closeIdx)
}

# 사용 예: 앵커 텍스트 뒤에 파란색 단락 삽입
# ※ 각 문자열은 반드시 35자(한글) / 70자(영문) 이하로 작성
$xml = [System.IO.File]::ReadAllText($sectionPath, [System.Text.Encoding]::UTF8)
Insert-After ([ref]$xml) "앵커 텍스트" @(
    "짧은 줄 1 (35자 이하)",
    "짧은 줄 2 (35자 이하)",
    "짧은 줄 3"
)
$utf8NoBom = New-Object System.Text.UTF8Encoding $False
[System.IO.File]::WriteAllText($sectionPath, $xml, $utf8NoBom)
```

---

## 출력

- 기본 파일명: `{원본}_filled.hwpx` (또는 `.hwp`)
- 사용자가 출력 파일명을 지정하면 해당 이름 사용
- 채워진 필드, 못 채운 필드 알려주기

## 주의사항

- macOS/Linux에서 `.hwp`는 지원 안 됨 → 한글에서 `.hwpx`로 다시 저장하라고 안내
- Windows에서는 pyhwpx로 `.hwp`, `.hwpx` 모두 지원
- XML 특수문자 이스케이프: `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`
- **단락 삽입 시 한 단락 = 한 줄 분량** (lineseg 오버플로우 방지, 6-C 참고)
- 원본 파일은 수정하지 않음 (새 파일 생성)
