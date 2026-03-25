"""
load_data.py
JSON 데이터를 pandas DataFrame으로 로드하는 모듈.
"""

import json
import pandas as pd
from pathlib import Path

# 기본 데이터 경로
DATA_DIR = Path(__file__).parent.parent / "data"


def load_formulas(path: Path = DATA_DIR / "formulas.json") -> pd.DataFrame:
    """
    formulas.json → DataFrame (처방 목록).

    반환 컬럼:
        formula_id, name_kr, name_cn, source, source_clause,
        total_dose_g, notes, composition(list), indications(dict)
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df = df.set_index("formula_id")
    return df


def load_herbs(path: Path = DATA_DIR / "herbs.json") -> pd.DataFrame:
    """
    herbs.json → DataFrame (본초 목록).

    반환 컬럼:
        herb_id, name_kr, name_cn, name_latin, category, properties,
        functions, typical_dose, interactions, cautions
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df = df.set_index("herb_id")
    return df


def load_syndromes(path: Path = DATA_DIR / "syndromes.json") -> pd.DataFrame:
    """
    syndromes.json → DataFrame (변증 목록).

    반환 컬럼:
        syndrome_id, name_kr, name_cn, system, symptoms(dict),
        tongue, pulse, primary_formulas, secondary_formulas
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df = df.set_index("syndrome_id")
    return df


def load_all(data_dir: Path = DATA_DIR) -> dict:
    """세 데이터셋을 한 번에 로드하여 dict로 반환."""
    return {
        "formulas": load_formulas(data_dir / "formulas.json"),
        "herbs": load_herbs(data_dir / "herbs.json"),
        "syndromes": load_syndromes(data_dir / "syndromes.json"),
    }


# ──────────────────────────────────────────────
# 편의 함수: composition 정규화
# ──────────────────────────────────────────────

def expand_composition(formulas_df: pd.DataFrame) -> pd.DataFrame:
    """
    formulas_df 의 composition 컬럼(list of dicts)을 펼쳐서
    처방-본초 단위의 긴 형식(long form) DataFrame 반환.

    반환 컬럼:
        formula_id, herb_id, name_kr, role, dose_g, dose_ratio
    """
    rows = []
    for formula_id, row in formulas_df.iterrows():
        total = row["total_dose_g"]
        for item in row["composition"]:
            rows.append({
                "formula_id": formula_id,
                "herb_id": item["herb_id"],
                "name_kr": item["name_kr"],
                "role": item["role"],
                "dose_g": item["dose_g"],
                "dose_ratio": round(item["dose_g"] / total, 4),
            })
    return pd.DataFrame(rows)


def expand_symptoms(syndromes_df: pd.DataFrame) -> pd.DataFrame:
    """
    syndromes_df 의 symptoms 컬럼을 펼쳐서
    변증-증상 단위의 긴 형식 DataFrame 반환.

    반환 컬럼:
        syndrome_id, symptom_id, name_kr, weight, symptom_type (required/optional)
    """
    rows = []
    for syndrome_id, row in syndromes_df.iterrows():
        for stype in ("required", "optional"):
            for s in row["symptoms"].get(stype, []):
                rows.append({
                    "syndrome_id": syndrome_id,
                    "symptom_id": s["symptom_id"],
                    "name_kr": s["name_kr"],
                    "weight": s["weight"],
                    "symptom_type": stype,
                })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
# 간단한 자가 테스트
# ──────────────────────────────────────────────

if __name__ == "__main__":
    data = load_all()
    print("=== 처방 ===")
    print(data["formulas"][["name_kr", "total_dose_g"]].to_string())

    print("\n=== 본초 ===")
    print(data["herbs"][["name_kr", "category"]].to_string())

    print("\n=== 변증 ===")
    print(data["syndromes"][["name_kr", "system"]].to_string())

    comp = expand_composition(data["formulas"])
    print("\n=== composition (long form) ===")
    print(comp.to_string(index=False))

    symp = expand_symptoms(data["syndromes"])
    print("\n=== symptoms (long form) ===")
    print(symp.to_string(index=False))
