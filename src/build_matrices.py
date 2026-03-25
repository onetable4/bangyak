"""
build_matrices.py
처방-본초 행렬(F)과 처방-증상 행렬(S)을 생성하는 모듈.

F[i, j] = 처방 i에서 본초 j의 용량 비율 (dose_g / total_dose_g)
S[i, k] = 처방 i에 대한 증상 k의 가중치

가중치 규칙 (대화 기록 §5.3):
  - primary 처방의 required 증상: weight × 1.0
  - primary 처방의 optional 증상: weight × 0.5
  - secondary 처방인 경우:       weight × 0.3
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import normalize

from load_data import load_all, expand_composition, expand_symptoms


# ──────────────────────────────────────────────
# Formula-Herb 행렬 (F)
# ──────────────────────────────────────────────

def build_formula_herb_matrix(formulas_df: pd.DataFrame) -> pd.DataFrame:
    """
    처방-본초 행렬 F를 반환.

    반환: DataFrame, index=formula_id, columns=herb_id
    값: 용량 비율 (0~1)
    """
    comp = expand_composition(formulas_df)

    # 전체 본초 목록 (등장 순서 유지를 위해 정렬)
    all_herbs = sorted(comp["herb_id"].unique())
    all_formulas = list(formulas_df.index)

    F = pd.DataFrame(0.0, index=all_formulas, columns=all_herbs)

    for _, row in comp.iterrows():
        F.loc[row["formula_id"], row["herb_id"]] = row["dose_ratio"]

    F.index.name = "formula_id"
    F.columns.name = "herb_id"
    return F


# ──────────────────────────────────────────────
# Formula-Symptom 행렬 (S)
# ──────────────────────────────────────────────

def build_formula_symptom_matrix(
    formulas_df: pd.DataFrame,
    syndromes_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    처방-증상 행렬 S를 반환.

    반환: DataFrame, index=formula_id, columns=symptom_id
    값: 가중치 (가중치 규칙 적용 후 누적 합산, 중복 시 최댓값 사용)
    """
    symp = expand_symptoms(syndromes_df)

    # 전체 증상 목록
    all_symptoms = sorted(symp["symptom_id"].unique())
    all_formulas = list(formulas_df.index)

    S = pd.DataFrame(0.0, index=all_formulas, columns=all_symptoms)

    for syndrome_id, syn_row in syndromes_df.iterrows():
        primary = syn_row.get("primary_formulas", []) or []
        secondary = syn_row.get("secondary_formulas", []) or []

        # 증상별 가중치 적용
        for stype in ("required", "optional"):
            multiplier_base = 1.0 if stype == "required" else 0.5
            for s in syn_row["symptoms"].get(stype, []):
                sid = s["symptom_id"]
                base_w = s["weight"]

                # primary 처방
                for fid in primary:
                    if fid in S.index and sid in S.columns:
                        val = base_w * multiplier_base
                        S.loc[fid, sid] = max(S.loc[fid, sid], val)

                # secondary 처방
                for fid in secondary:
                    if fid in S.index and sid in S.columns:
                        val = base_w * 0.3
                        S.loc[fid, sid] = max(S.loc[fid, sid], val)

    S.index.name = "formula_id"
    S.columns.name = "symptom_id"
    return S


# ──────────────────────────────────────────────
# 코사인 유사도 유틸리티
# ──────────────────────────────────────────────

def cosine_similarity_matrix(matrix: pd.DataFrame) -> pd.DataFrame:
    """
    행렬 내 행 벡터 간 코사인 유사도 행렬 반환.
    반환: DataFrame, index=columns=matrix.index
    """
    normed = normalize(matrix.values, norm="l2")
    sim = normed @ normed.T
    return pd.DataFrame(sim, index=matrix.index, columns=matrix.index)


def query_similarity(
    query_vector: pd.Series,
    matrix: pd.DataFrame,
) -> pd.Series:
    """
    query_vector와 matrix 각 행의 코사인 유사도를 계산.

    Parameters
    ----------
    query_vector : pd.Series, index=matrix.columns (예: symptom_id)
    matrix       : pd.DataFrame, index=formula_id, columns=증상/본초

    반환: pd.Series, index=formula_id, 내림차순 정렬
    """
    # 공통 컬럼 정렬
    common = matrix.columns.intersection(query_vector.index)
    q = query_vector.reindex(common).fillna(0).values.astype(float)
    M = matrix[common].values.astype(float)

    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return pd.Series(0.0, index=matrix.index)

    M_norms = np.linalg.norm(M, axis=1)
    M_norms[M_norms == 0] = 1e-10  # 0 나눔 방지

    scores = (M @ q) / (M_norms * q_norm)
    return pd.Series(scores, index=matrix.index).sort_values(ascending=False)


# ──────────────────────────────────────────────
# 헬퍼: 증상명 → symptom_id 역인덱스
# ──────────────────────────────────────────────

def build_symptom_name_index(syndromes_df: pd.DataFrame) -> dict:
    """
    {'증상 이름': 'SX_xxx'} 형태의 역인덱스 반환.
    동일 이름이 여러 ID를 가질 경우 첫 번째 ID 사용.
    """
    symp = expand_symptoms(syndromes_df)
    index = {}
    for _, row in symp.drop_duplicates("name_kr").iterrows():
        index[row["name_kr"]] = row["symptom_id"]
    return index


# ──────────────────────────────────────────────
# 자가 테스트
# ──────────────────────────────────────────────

if __name__ == "__main__":
    data = load_all()
    formulas_df = data["formulas"]
    syndromes_df = data["syndromes"]
    herbs_df = data["herbs"]

    # ── F 행렬
    F = build_formula_herb_matrix(formulas_df)
    print("=== Formula-Herb 행렬 F (shape:", F.shape, ") ===")
    # 본초 이름으로 컬럼 레이블 교체 (표시용)
    herb_names = herbs_df["name_kr"].to_dict()
    F_display = F.rename(columns=herb_names)
    formula_names = formulas_df["name_kr"].to_dict()
    F_display = F_display.rename(index=formula_names)
    print(F_display.round(3).to_string())

    # ── S 행렬
    S = build_formula_symptom_matrix(formulas_df, syndromes_df)
    print("\n=== Formula-Symptom 행렬 S (shape:", S.shape, ") ===")
    print(S.rename(index=formula_names).to_string())

    # ── F 기반 처방 간 유사도
    sim_F = cosine_similarity_matrix(F)
    sim_F_display = sim_F.rename(index=formula_names, columns=formula_names)
    print("\n=== 처방 간 코사인 유사도 (본초 기반) ===")
    print(sim_F_display.round(3).to_string())

    # ── S 기반 처방 간 유사도
    sim_S = cosine_similarity_matrix(S)
    sim_S_display = sim_S.rename(index=formula_names, columns=formula_names)
    print("\n=== 처방 간 코사인 유사도 (증상 기반) ===")
    print(sim_S_display.round(3).to_string())

    # ── 예시 쿼리: 오한 + 발열 + 무한 + 두통
    name_idx = build_symptom_name_index(syndromes_df)
    query_symptoms = ["오한", "발열", "무한", "두통"]
    q = pd.Series({name_idx[s]: 1.0 for s in query_symptoms if s in name_idx})
    result = query_similarity(q, S)
    print("\n=== 쿼리 [오한, 발열, 무한, 두통] 추천 결과 ===")
    for fid, score in result.items():
        fname = formulas_df.loc[fid, "name_kr"]
        print(f"  {fname:20s} {score:.4f}")
