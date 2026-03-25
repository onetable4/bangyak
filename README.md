# KM-Vector: 한의학 처방 벡터 분석 시스템
# Claude Code 스타터 킷

## 이 파일들을 어떻게 사용하나요?

1. 로컬에 프로젝트 폴더를 만드세요: `mkdir km-vector && cd km-vector`
2. 이 zip의 내용물을 해당 폴더에 풀어넣으세요
3. Claude Code에서 `claude` 명령으로 시작하면 됩니다
4. Claude Code에게 "CLAUDE_CODE_GUIDE.md를 읽고 프로젝트를 세팅해줘"라고 말하세요

## 파일 구조

```
km-vector/
├── CLAUDE_CODE_GUIDE.md     ← Claude Code가 읽을 프로젝트 가이드
├── README.md                ← 이 파일
├── data/
│   ├── schema.md            ← 데이터 스키마 정의서
│   ├── formulas.json        ← 처방 데이터 (시드: 상한론 경방 10개)
│   ├── herbs.json           ← 본초 데이터 (시드: 경방 구성 본초)
│   └── syndromes.json       ← 변증/증상 데이터 (시드: 육경변증)
├── src/
│   └── (Claude Code가 여기에 코드 생성)
├── notebooks/
│   └── (탐색용 Jupyter 노트북)
└── requirements.txt         ← Python 의존성
```
