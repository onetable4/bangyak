# KM-Vector: Claude Code 프로젝트 가이드

## 프로젝트 개요
한의학 처방을 벡터화하여 증상-처방 매칭, 처방 분석, 처방 비교를 수행하는 오프라인 시스템.
LLM 실시간 호출 없이 행렬 연산만으로 MVP를 구현한다.

## 핵심 원리
- 처방 = 본초 공간에서의 벡터 (각 차원은 본초, 값은 정규화된 용량 비율)
- 변증/증상 = 증상 공간에서의 벡터 (각 차원은 증상, 값은 가중치)
- 처방 추천 = 환자 증상 벡터와 처방별 적응증 벡터의 코사인 유사도
- 처방 비교 = 두 처방 벡터의 코사인 유사도 + 공통/차이 본초 분석

## 기술 스택
- Python 3.10+
- pandas: 데이터 로드 및 조작
- numpy: 행렬 연산
- scikit-learn: 코사인 유사도, 클러스터링, 차원 축소
- matplotlib / plotly: 시각화
- streamlit: UI (Phase 1 이후)
- jupyter: 탐색 및 개발

## 데이터 구조
data/ 폴더의 JSON 파일들이 핵심 데이터.
schema.md에 각 필드의 정의가 있음.
시드 데이터로 상한론 경방 10개가 입력되어 있음.

## 개발 순서 (Phase 0 → Phase 1)

### Phase 0: 데이터 + 행렬 구축
1. `src/load_data.py` - JSON 데이터를 pandas DataFrame으로 로드
2. `src/build_matrices.py` - Formula-Herb 행렬(F)과 Formula-Symptom 행렬(S) 생성
3. `notebooks/01_explore.ipynb` - 데이터 탐색, 행렬 시각화, 유사도 테스트

### Phase 1: 핵심 기능 구현
4. `src/engine.py` - 코사인 유사도 기반 추천/분석 엔진
   - recommend(symptoms) → top-k 처방 + 유사도 점수
   - decompose(formula_id) → 본초별 역할, 비중 분석
   - compare(formula_id_a, formula_id_b) → 유사도, 공통/차이 본초
5. `src/app.py` - Streamlit UI

## 용량 정규화 방식
- 벡터 값 = 해당 본초의 용량 / 처방 총 용량 (비율)
- 예: 마황탕 = 마황 9/(9+6+6+3) = 0.375, 계지 0.25, 행인 0.25, 감초 0.125
- 원본 절대 용량은 별도 필드로 보존

## 주의사항
- 모든 출력은 "참고용"임을 명시
- 데이터에 없는 처방/본초에 대해서는 "데이터 없음" 반환
- 시드 데이터는 연구자가 검증해야 함 (LLM 생성 데이터의 한계)
