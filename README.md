# easy-hwp

> Claude Code에서 한글 파일(.hwpx)을 자동으로 분석하고 작성하는 스킬

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-blue)](https://github.com/anthropics/claude-code)

## 설치

Claude Code에서:

```
/plugin marketplace add nathankim0/easy-hwp
/plugin install easy-hwp@nathankim0-easy-hwp
```

## 사용법

설치 후 **자연어로 요청**하면 됩니다:

```
연구계획.md 내용을 IRB서식.hwpx에 채워줘
```

```
신청서.hwpx 구조 분석해줘
```

```
보고서.md를 출장신청서.hwpx에 입력해서 결과.hwpx로 저장해줘
```

## 슬래시 명령어

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `/hwp-analyze` | 한글 파일 구조 분석 | `/hwp-analyze 서식.hwpx` |
| `/hwp-fill` | 서식에 내용 채우기 | `/hwp-fill 서식.hwpx 내용.md` |
| `/hwp-template` | 템플릿 저장/관리 | `/hwp-template list` |

## 입력 파일 형식

**MD 파일 (채울 내용):**
```markdown
# 연구과제명
AI 기반 의료 영상 진단 시스템 개발

## 연구책임자
홍길동

## 연구기간
2024.03.01 ~ 2025.02.28
```

**HWPX 파일 (서식):**
- 한글에서 저장한 .hwpx 파일
- 표 안의 빈 칸을 자동으로 인식해서 채움

## 요구 환경

| 항목 | Windows | macOS / Linux |
|------|---------|---------------|
| `.hwpx` 채우기 | O | O |
| `.hwp` 채우기 | O (한글 + pyhwpx 필요) | X |
| 레이아웃 검증 (`verify`) | O | X (한글 프로그램 없음) |

Windows에서 `.hwp`를 다루거나 결과를 검증하려면: 한컴오피스 한글 설치 + `pip install pyhwpx`

## 작동 방식

```
HWPX 서식 ──▶ 구조 분석 ──▶ MD 내용 매칭 ──▶ 새 HWPX 생성
```

## 문제 해결

| 문제 | 해결 |
|------|------|
| **글자가 겹쳐서 나옴** | v1.1.0에서 해결. 원인은 레이아웃 캐시(`linesegarray`)이며 `hwpx_edit.save()`가 자동 제거한다. 아래 참고 |
| .hwp 지원 안됨 | 한글에서 .hwpx로 다시 저장 (Windows + 한글 설치 시에는 pyhwpx로 .hwp도 처리 가능) |
| 잘못된 위치에 채워짐 | `/hwp-analyze`로 셀 좌표(`cellAddr`) 확인 |
| 표 라벨이 한 글자만 읽힘 | `<hp:fwSpace/>` 때문. 텍스트 추출 시 자식 요소의 `.tail`까지 이어붙여야 한다 |

### 글자 겹침에 대하여

hwpx의 모든 문단에는 `<hp:linesegarray>`(각 줄을 세로 몇 번째 좌표에 그릴지 적어둔 레이아웃 캐시)가 붙어 있다.
문단을 복제해서 내용을 채우면 이 캐시까지 복사되어 **여러 줄이 같은 좌표를 갖게 되고, 한글이 한 자리에 전부 포개서 그린다.**

한글은 이 캐시를 자동으로 재계산하지 않는다 — 파일을 열었다 다시 저장해도 고쳐지지 않는다.
**저장 직전에 `linesegarray`를 전부 제거**하면 한글이 열 때 처음부터 다시 계산한다.

> v1.0.0에 있던 "단락을 35자 이하로 쪼개라"는 지침은 증상만 가리는 잘못된 처방이라 제거했다.

`HwpxDoc.check_layout()`으로 겹침 여부를 자동 검사할 수 있다 (한 칸 안에서 연속한 두 줄의 `vertpos`가 같은지 확인).

## 라이선스

MIT License
