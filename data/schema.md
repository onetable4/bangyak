# 데이터 스키마 정의서

## 1. formulas.json — 처방 데이터

```json
{
  "formula_id": "string",        // 고유 ID (예: "SHL_001")
  "name_kr": "string",           // 한글명 (예: "마황탕")
  "name_cn": "string",           // 한자명 (예: "麻黃湯")
  "source": "string",            // 출전 (예: "상한론")
  "source_clause": "string",     // 출전 조문 번호 (예: "제35조")
  
  "composition": [               // 구성 본초 배열
    {
      "herb_id": "string",       // 본초 ID (herbs.json 참조)
      "name_kr": "string",       // 본초 한글명 (편의용)
      "role": "enum",            // 군(君) | 신(臣) | 좌(佐) | 사(使)
      "dose_g": "number",        // 용량 (g 기준, 원전 환산)
      "dose_original": "string"  // 원전 표기 (예: "三兩")
    }
  ],
  
  "total_dose_g": "number",      // 총 용량 (자동 계산 가능)
  
  "indications": {               // 적응증
    "syndromes": ["string"],     // 대응 변증 ID 배열
    "symptoms": ["string"],      // 개별 증상 목록
    "tongue": "string",          // 설진 (선택)
    "pulse": "string"            // 맥진 (선택)
  },
  
  "contraindications": ["string"], // 금기사항
  
  "notes": "string",             // 비고 (연구자 메모)
  
  // === 추후 확장 필드 (addon) ===
  "pharmacology": {              // 약리학적 근거
    "mechanisms": ["string"],    // 작용 기전
    "evidence_level": "enum",    // traditional | in_vitro | in_vivo | rct | meta_analysis
    "references": ["string"]     // 참고 문헌
  }
}
```

## 2. herbs.json — 본초 데이터

```json
{
  "herb_id": "string",           // 고유 ID (예: "H_001")
  "name_kr": "string",           // 한글명 (예: "마황")
  "name_cn": "string",           // 한자명 (예: "麻黃")
  "name_latin": "string",        // 학명 (예: "Ephedrae Herba")
  "name_common": "string",       // 기원식물 (예: "Ephedra sinica")
  
  "category": "string",          // 본초학적 분류 (예: "해표약-발산풍한약")
  
  "properties": {                // 성미귀경
    "nature": "string",          // 성 (예: "온(溫)")
    "flavors": ["string"],       // 미 (예: ["신(辛)", "미고(微苦)"])
    "meridians": ["string"]      // 귀경 (예: ["폐(肺)", "방광(膀胱)"])
  },
  
  "functions": ["string"],       // 효능 (예: ["발한해표", "선폐평천", "이수소종"])
  
  "typical_dose": {              // 상용량
    "min_g": "number",
    "max_g": "number"
  },
  
  "interactions": {              // 배합 관계
    "incompatible": ["string"],  // 상반(相反) - 십팔반
    "antagonistic": ["string"],  // 상오(相畏) - 십구외
    "synergistic": ["string"]    // 상수(相須)/상사(相使)
  },
  
  "cautions": ["string"],        // 주의사항
  
  // === 추후 확장 필드 (addon) ===
  "pharmacology": {
    "active_compounds": [
      {
        "compound": "string",     // 성분명 (예: "ephedrine")
        "actions": ["string"],    // 약리작용
        "pathways": ["string"],   // 작용경로
        "evidence_level": "enum"
      }
    ]
  }
}
```

## 3. syndromes.json — 변증/증상 데이터

```json
{
  "syndrome_id": "string",       // 고유 ID (예: "SYN_001")
  "name_kr": "string",           // 한글명 (예: "태양병 상한증")
  "name_cn": "string",           // 한자명 (예: "太陽病 傷寒證")
  "system": "string",            // 변증 체계 (예: "육경변증")
  
  "symptoms": {
    "required": [                // 필수 증상 (반드시 있어야 해당 변증)
      {
        "symptom_id": "string",
        "name_kr": "string",
        "weight": "number"       // 가중치 (1.0 = 표준, >1 = 핵심)
      }
    ],
    "optional": [                // 부수 증상 (있을 수 있음)
      {
        "symptom_id": "string",
        "name_kr": "string",
        "weight": "number"
      }
    ]
  },
  
  "tongue": "string",            // 설진 특징
  "pulse": "string",             // 맥진 특징
  
  "primary_formulas": ["string"],   // 1차 대응 처방 ID
  "secondary_formulas": ["string"], // 2차 대응 처방 ID
  
  "differential": ["string"],    // 감별 변증 ID (비슷하지만 다른 변증)
  
  "notes": "string"
}
```

## 4. 벡터화 규칙

### Formula-Herb 행렬 (F)
- 행: 처방 (formula_id)
- 열: 본초 (herb_id)  
- 값: dose_g / total_dose_g (비율, 0~1)
- 해당 본초 미포함 시: 0

### Formula-Symptom 행렬 (S)
- 행: 처방 (formula_id)
- 열: 증상 (symptom_id, 전체 증상의 합집합)
- 값: 해당 처방의 적응증에 포함된 증상의 가중치, 미포함 시 0
- 가중치 산출: syndromes.json의 weight 값 사용
  - 처방의 primary_formula인 변증의 required 증상: weight × 1.0
  - 처방의 primary_formula인 변증의 optional 증상: weight × 0.5
  - 처방의 secondary_formula인 경우: weight × 0.3

### 환자 증상 벡터 (q)
- 동일한 증상 차원 사용
- 환자가 호소하는 증상: 1.0 (또는 심한 정도에 따라 0.5~1.5)
- 미호소 증상: 0
