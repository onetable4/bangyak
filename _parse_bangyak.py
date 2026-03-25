"""
bangyak_top50.txt → formulas_bangyak.json 변환 스크립트

처리 규칙:
- 용량 단위: g
- 비단위 약재 (용량 < 2 또는 단위 포함) 무시
- 범위 용량 (예: 12~80) → 최솟값
- 주치 증상: 첫 문장 추출
- 가감/활용법: notes 필드 보존
"""

import re
import json
from pathlib import Path

# ── 증상 번역 사전 ──────────────────────────────────────────
# 원문에서 추출된 주요 병증 용어 → 현대 한국어
SYMPTOM_MAP = {
    # 신경/정신 — 풍증
    "語音蹇吃": "언어장애(말 더듬)",
    "腎臟風": "신장풍(신허로 인한 풍증)",
    "中風": "중풍(뇌졸중)",
    "半身不遂": "반신불수",
    "手足風": "수족풍비",
    "小兒麻痺": "소아마비",
    "手足無力": "수족무력",
    "麻痺": "마비",
    "風虛諸證": "풍허제증(풍+허 복합증)",
    "祛風": "거풍(풍사 제거)",
    # 신경/정신 — 심신
    "怔忡": "심계항진(두근거림)",
    "노이로제": "신경증(노이로제)",
    "두렵고 겁나": "공포불안증",
    "혼자 누워있지 못": "불안불면",
    "心과 膽이 虛": "심담허(심담허증)",
    "心膽虛": "심담허(심담허증)",
    "心, 脾, 腎 三經의 虛損": "심비신허손",
    # 소화기
    "太陰腹痛": "태음복통",
    "自利不渴": "자리불갈(설사하나 갈증 없음)",
    "腹滿": "복부팽만",
    "腹痛": "복통",
    "小便不利": "소변불리",
    "下痢": "설사(이질)",
    "嘔吐": "구토",
    "구역": "오심구역",
    "脾胃虛損": "비위허손",
    "脾胃虛弱": "비위허약",
    "脾胃가 虛弱": "비위허약",
    "不思飮食": "식욕부진",
    "飮食不進": "식욕부진",
    "음식생각이 없는": "식욕부진",
    "식욕이 감퇴": "식욕부진",
    "음식을 소화": "소화불량",
    "倒飽": "식후 포만감",
    "泄瀉": "설사",
    "體瘦": "수척(체중감소)",
    "面黃": "황달색 안색",
    "비위를 고르": "비위조화",
    "비위를 건강": "비위허약",
    "胃氣를 收斂": "위기허약",
    "胃虛": "위허(위장허약)",
    "脾와 腎이 함께 虛": "비신양허",
    "脾와 腎의 虛": "비신양허",
    # 기혈허
    "氣血不足": "기혈부족",
    "氣와 血이 다 虛": "기혈양허",
    "氣血이 크게 虛": "기혈양허",
    "氣와 血이 함께 손상": "기혈양상",
    "氣血을 평균하게 補": "기혈양허",
    "氣와 精과 血이 虛": "기정혈허",
    "血氣가 衰弱": "기혈허약",
    "氣乏": "기허 피로",
    "自汗": "자한(저절로 나는 땀)",
    "저절로 땀": "자한(저절로 나는 땀)",
    "盜汗": "도한(식은땀)",
    "氣短": "기단(호흡곤란)",
    "少氣": "소기(기운 없음)",
    "虛勞": "허로(만성피로)",
    "勞損": "노손(과로손상)",
    "勞役": "과로손상",
    "寒熱": "한열왕래",
    "潮熱": "조열(오후 발열)",
    "內傷": "내상(내부 손상)",
    "血脫": "혈탈(과출혈)",
    "大病 후": "대병후 원기허",
    "대병후": "대병후 원기허",
    # 신허/보허
    "腎水不足": "신수부족",
    "腎虛有熱": "신허유열",
    "腎臟이 쇠약": "신장허약",
    "精氣大虧": "정기대허",
    "精氣가 大虧": "정기대허",
    "眞陰이 虧損": "진음휴손",
    "水火不濟": "수화불제(심신불교)",
    "遺精": "유정(몽정)",
    "赤濁": "적탁(혈뇨·탁뇨)",
    "命門陽虛": "명문양허",
    "陰虛火動": "음허화동",
    "陰陽兩虛": "음양양허",
    "陰陽 兩虛": "음양양허",
    "陰虛": "음허",
    "陽虛": "양허",
    "陽이 衰弱": "양허",
    "虛損": "허손(허약·쇠약)",
    "諸虛": "제허(여러 허증)",
    "원기를 돕": "원기허약",
    "정신을 기르": "정신허약",
    "선천적으로 허약": "선천허약",
    "脈이 虛": "맥허",
    "脈虛": "맥허",
    # 근골/운동
    "筋骨痺痛": "근골비통(근육관절통)",
    "筋骨과 心腹의 疼痛": "근골심복동통",
    "鶴膝風": "학슬풍(슬관절종통)",
    "痺痛": "비통(저리고 아픔)",
    "身痛": "신체통",
    "四肢厥冷": "사지궐냉",
    "手足厥冷": "수족궐냉",
    "裏急": "이급(복부 긴장감)",
    "속이 차고": "위한(위장냉증)",
    "입을 다물어 벌리지 못": "개구장애",
    "몸이 뻣뻣": "신체강직",
    "말을 못함": "언어불능",
    "발을 못씀": "하지마비",
    # 서습/외감
    "瘧疾": "말라리아(학질)",
    "더위를 먹어": "서증(더위먹음)",
    "긴 여름철": "서습증",
    "四肢困": "사지피로",
    "身熱": "발열",
    "몸에 열이 나": "발열",
    "煩渴": "번갈(번열+갈증)",
    "습기많은 땅": "습비(습사)",
    "몸이 무겁고": "신체중감",
    "다리가 약해지고": "하지무력",
    # 기타
    "大便秘結": "변비",
    "咳嗽": "기침",
    "기침": "기침",
    "痰喘": "담천(담으로 인한 천식)",
    "喘息": "천식",
    "月經遲延": "월경지연",
    "血少": "혈허",
    "肌熱": "기육발열",
    "大渴": "심한 갈증",
    "內傷熱中": "내상열중",
    "夢遺": "몽유(몽정)",
    "咽乾": "인건(인후건조)",
    "房事後": "방사후 원기손상",
}

# 자동 매핑이 안 되는 케이스 수동 보완
MANUAL_SYMPTOMS = {
    "BY_012": ["서열소모증(여름철 기진맥진)", "기음양허"],   # 생맥산: 더운 여름 상복 → 서열로 인한 기음소모
    "BY_037": ["수화불제(심신불교)", "심계항진(두근거림)", "도한(식은땀)", "유정(몽정)", "적탁(혈뇨·탁뇨)"],  # 구원심신환
}

# ── 파서 ────────────────────────────────────────────────────

def parse_herb_line(line: str) -> list[dict]:
    """
    '生薑80 磁石68 白朮12~20 羊腎1 粳米1撮' 형태 파싱.
    - 비단위(숫자<2 또는 단위 문자 포함) 무시
    - 범위 표기(~) → 최솟값
    """
    herbs = []
    # 토큰 분리
    tokens = re.findall(r'[^\s]+', line)
    for token in tokens:
        # 한자/한글 약재명 + 숫자(범위 포함) 패턴
        m = re.match(r'^([가-힣A-Za-z\u4e00-\u9fff]+)\s*(\d+(?:\.\d+)?(?:~\d+(?:\.\d+)?)?)', token)
        if not m:
            continue
        name = m.group(1)
        dose_str = m.group(2)

        # 범위 → 최솟값
        if '~' in dose_str:
            dose = float(dose_str.split('~')[0])
        else:
            dose = float(dose_str)

        # 소량/비단위 무시 (용량 < 2)
        if dose < 2:
            continue

        herbs.append({"name_cn": name, "dose_g": dose})

    return herbs


def extract_indication(text: str) -> str:
    """첫 번째 문장(마침표 또는 문장 끝)을 주치 텍스트로 추출."""
    # ①②③ 등 번호 이후 내용 제거
    text = re.split(r'[①②③④⑤⑥⑦⑧⑨⑩]', text)[0]
    # [活套][用法][適應症] 이후 제거
    text = re.split(r'\[活套\]|\[用法\]|\[調劑法\]|\[適應症\]', text)[0]
    # 첫 문장만
    m = re.split(r'[.。]', text.strip())
    return m[0].strip() if m else text.strip()


def translate_symptoms(indication: str) -> list[str]:
    """주치 텍스트에서 증상 키워드를 추출하여 현대어로 변환."""
    symptoms = []
    for key, val in SYMPTOM_MAP.items():
        if key in indication:
            symptoms.append(val)
    # 중복 제거, 순서 유지
    seen = set()
    result = []
    for s in symptoms:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result if result else [indication[:40]]  # 매칭 없으면 원문 앞부분


def parse_bangyak(filepath: str) -> list[dict]:
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    # 처방 블록 분리: '上統 N 처방명(漢字名)' 으로 시작
    blocks = re.split(r'\n(?=上統\s+\d+)', content)

    formulas = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split('\n')

        # ── 헤더 파싱
        header_m = re.match(r'上統\s+(\d+)\s+([가-힣]+)\(([^)]+)\)', lines[0])
        if not header_m:
            continue
        num = int(header_m.group(1))
        name_kr = header_m.group(2)
        name_cn = header_m.group(3)
        formula_id = f"BY_{num:03d}"

        # ── 본초 파싱 (두 번째 줄, 가끔 세 번째 줄까지 이어짐)
        # 한글로 시작하거나 빈 줄이 나올 때까지 본초 행으로 처리
        herb_lines = []
        i = 1
        while i < len(lines):
            stripped = lines[i].strip()
            # 빈 줄이면 종료
            if not stripped:
                i += 1
                break
            # 한글로 시작하면서 약재명 패턴이 아닌 경우 → 주치 텍스트 시작
            if re.match(r'[가-힣]', stripped[:1]) and not re.match(
                r'^[가-힣A-Za-z\u4e00-\u9fff]+\d', stripped
            ):
                break
            herb_lines.append(stripped)
            i += 1
        herb_text = ' '.join(herb_lines)
        composition = parse_herb_line(herb_text)

        total_dose = sum(h['dose_g'] for h in composition)
        for h in composition:
            h['dose_ratio'] = round(h['dose_g'] / total_dose, 4) if total_dose > 0 else 0

        # ── 주치/가감 텍스트 분리
        remaining = '\n'.join(lines[i:]).strip()
        indication_raw = extract_indication(remaining)
        symptoms = MANUAL_SYMPTOMS.get(formula_id) or translate_symptoms(indication_raw)

        formulas.append({
            "formula_id": formula_id,
            "name_kr": name_kr,
            "name_cn": name_cn,
            "source": "방약합편 상통",
            "source_clause": f"上統 {num}",
            "composition": composition,
            "total_dose_g": round(total_dose, 1),
            "indications": {
                "raw": indication_raw,
                "symptoms": symptoms,
            },
            "notes": remaining,
        })

    return formulas


if __name__ == "__main__":
    base = Path(__file__).parent
    formulas = parse_bangyak(base / "bangyak_top50.txt")

    out_path = base / "data" / "formulas_bangyak.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(formulas, f, ensure_ascii=False, indent=2)

    print(f"총 {len(formulas)}개 처방 파싱 완료 → {out_path}")
    print()
    for f in formulas:
        herbs_str = ', '.join(f'{h["name_cn"]} {h["dose_g"]}g' for h in f['composition'])
        print(f"[{f['formula_id']}] {f['name_kr']} ({f['name_cn']})")
        print(f"  본초({len(f['composition'])}종): {herbs_str}")
        print(f"  총량: {f['total_dose_g']}g")
        print(f"  주치(원문): {f['indications']['raw']}")
        print(f"  증상키워드: {f['indications']['symptoms']}")
        print()
