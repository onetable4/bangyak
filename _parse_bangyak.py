"""
bangyak.txt → formulas_bangyak.json 변환 스크립트

처리 규칙:
- 인코딩: utf-16 (원본 파일)
- 上統/中統/下統 전체 처방 파싱
- 용량 단위: g
- 비단위 약재 (용량 < 2 또는 단위 포함) 무시
- 범위 용량 (예: 12~80) → 최솟값
- 주치 증상: 첫 문장 추출 후 증상 사전으로 현대어 변환
- 증상 표기: 괄호 안 보충 설명 제거 (예: '도한(식은땀)' → '도한')
- 가감/활용법: notes 필드 보존
"""

import re
import json
from pathlib import Path


def strip_paren(s: str) -> str:
    """괄호 안 보충 설명 제거. 예: '도한(식은땀)' → '도한'"""
    return re.sub(r'\([^)]*\)', '', s).strip()


# ── 증상 번역 사전 ──────────────────────────────────────────
# 원문에서 추출된 주요 병증 용어 → 현대 한국어 (괄호 없이)
SYMPTOM_MAP = {
    # 신경/정신 — 풍증
    "語音蹇吃": "언어장애",
    "腎臟風": "신장풍",
    "中風": "중풍",
    "半身不遂": "반신불수",
    "手足風": "수족풍비",
    "小兒麻痺": "소아마비",
    "手足無力": "수족무력",
    "麻痺": "마비",
    "風虛諸證": "풍허제증",
    "祛風": "거풍",
    "風痰": "풍담",
    "破傷風": "파상풍",
    "口眼喎斜": "구안와사",
    "風寒濕": "풍한습비",
    "痙攣": "경련",
    "癲癎": "전간",
    # 신경/정신 — 심신
    "怔忡": "정충",
    "노이로제": "신경증",
    "두렵고 겁나": "공포불안증",
    "혼자 누워있지 못": "불안불면",
    "心과 膽이 虛": "심담허",
    "心膽虛": "심담허",
    "心, 脾, 腎 三經의 虛損": "심비신허손",
    "不眠": "불면",
    "健忘": "건망",
    "驚悸": "경계",
    "癲狂": "전광",
    # 소화기
    "太陰腹痛": "태음복통",
    "自利不渴": "자리불갈",
    "腹滿": "복부팽만",
    "腹痛": "복통",
    "小便不利": "소변불리",
    "下痢": "설사",
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
    "體瘦": "수척",
    "面黃": "황달색 안색",
    "비위를 고르": "비위조화",
    "비위를 건강": "비위허약",
    "胃氣를 收斂": "위기허약",
    "胃虛": "위허",
    "脾와 腎이 함께 虛": "비신양허",
    "脾와 腎의 虛": "비신양허",
    "痞滿": "비만",
    "噯氣": "애기",
    "呑酸": "탄산",
    "積聚": "적취",
    "痰飮": "담음",
    "水腫": "수종",
    "黃疸": "황달",
    "便秘": "변비",
    # 기혈허
    "氣血不足": "기혈부족",
    "氣와 血이 다 虛": "기혈양허",
    "氣血이 크게 虛": "기혈양허",
    "氣와 血이 함께 손상": "기혈양상",
    "氣血을 평균하게 補": "기혈양허",
    "氣와 精과 血이 虛": "기정혈허",
    "血氣가 衰弱": "기혈허약",
    "氣乏": "기허 피로",
    "自汗": "자한",
    "저절로 땀": "자한",
    "盜汗": "도한",
    "氣短": "기단",
    "少氣": "소기",
    "虛勞": "허로",
    "勞損": "노손",
    "勞役": "과로손상",
    "寒熱": "한열왕래",
    "潮熱": "조열",
    "內傷": "내상",
    "血脫": "혈탈",
    "大病 후": "대병후 원기허",
    "대병후": "대병후 원기허",
    "出血": "출혈",
    "吐血": "토혈",
    "衄血": "뉵혈",
    "血崩": "혈붕",
    # 신허/보허
    "腎水不足": "신수부족",
    "腎虛有熱": "신허유열",
    "腎臟이 쇠약": "신장허약",
    "精氣大虧": "정기대허",
    "精氣가 大虧": "정기대허",
    "眞陰이 虧損": "진음휴손",
    "水火不濟": "수화불제",
    "遺精": "유정",
    "赤濁": "적탁",
    "命門陽虛": "명문양허",
    "陰虛火動": "음허화동",
    "陰陽兩虛": "음양양허",
    "陰陽 兩虛": "음양양허",
    "陰虛": "음허",
    "陽虛": "양허",
    "陽이 衰弱": "양허",
    "虛損": "허손",
    "諸虛": "제허",
    "원기를 돕": "원기허약",
    "정신을 기르": "정신허약",
    "선천적으로 허약": "선천허약",
    "脈이 虛": "맥허",
    "脈虛": "맥허",
    "腰痛": "요통",
    "腰膝酸軟": "요슬산연",
    "耳鳴": "이명",
    "耳聾": "이농",
    "目眩": "현기증",
    "頭眩": "현기증",
    # 근골/운동
    "筋骨痺痛": "근골비통",
    "筋骨과 心腹의 疼痛": "근골심복동통",
    "鶴膝風": "학슬풍",
    "痺痛": "비통",
    "身痛": "신체통",
    "四肢厥冷": "사지궐냉",
    "手足厥冷": "수족궐냉",
    "裏急": "이급",
    "속이 차고": "위한",
    "입을 다물어 벌리지 못": "개구장애",
    "몸이 뻣뻣": "신체강직",
    "말을 못함": "언어불능",
    "발을 못씀": "하지마비",
    "關節": "관절통",
    "筋攣": "근련",
    # 외감/상한
    "傷寒": "상한",
    "傷風": "상풍",
    "發表": "발표",
    "解表": "해표",
    "惡寒": "오한",
    "發熱": "발열",
    "頭痛": "두통",
    "項强": "항강",
    "無汗": "무한",
    "有汗": "유한",
    "表虛": "표허",
    "表實": "표실",
    # 서습/외감
    "瘧疾": "학질",
    "더위를 먹어": "서증",
    "긴 여름철": "서습증",
    "四肢困": "사지피로",
    "身熱": "발열",
    "몸에 열이 나": "발열",
    "煩渴": "번갈",
    "습기많은 땅": "습비",
    "몸이 무겁고": "신체중감",
    "다리가 약해지고": "하지무력",
    "暑熱": "서열",
    "濕熱": "습열",
    "濕痺": "습비",
    # 부인과
    "月經遲延": "월경지연",
    "月經不調": "월경불조",
    "崩漏": "붕루",
    "帶下": "대하",
    "産後": "산후",
    "不妊": "불임",
    # 기타
    "大便秘結": "변비",
    "咳嗽": "기침",
    "기침": "기침",
    "痰喘": "담천",
    "喘息": "천식",
    "血少": "혈허",
    "肌熱": "기육발열",
    "大渴": "심한 갈증",
    "內傷熱中": "내상열중",
    "夢遺": "몽유",
    "咽乾": "인건",
    "房事後": "방사후 원기손상",
    "瘡瘍": "창양",
    "癰腫": "옹종",
    "皮膚": "피부병",
    "疥癬": "개선",
    "淋疾": "임질",
    "小便頻數": "빈뇨",
    "消渴": "소갈",
}

# 자동 매핑이 안 되는 케이스 수동 보완
MANUAL_SYMPTOMS = {
    "BY_U_012": ["서열소모증", "기음양허"],   # 생맥산
    "BY_U_037": ["수화불제", "정충", "도한", "유정", "적탁"],  # 구원심신환
}

# ── 파서 ────────────────────────────────────────────────────

def parse_herb_line(line: str) -> list[dict]:
    """
    '生薑80 磁石68 白朮12~20 羊腎1 粳米1撮' 형태 파싱.
    - 비단위(숫자<2 또는 단위 문자 포함) 무시
    - 범위 표기(~) → 최솟값
    """
    herbs = []
    tokens = re.findall(r'[^\s]+', line)
    for token in tokens:
        m = re.match(r'^([가-힣A-Za-z\u4e00-\u9fff]+)\s*(\d+(?:\.\d+)?(?:~\d+(?:\.\d+)?)?)', token)
        if not m:
            continue
        name = m.group(1)
        dose_str = m.group(2)

        if '~' in dose_str:
            dose = float(dose_str.split('~')[0])
        else:
            dose = float(dose_str)

        if dose < 2:
            continue

        herbs.append({"name_cn": name, "dose_g": dose})

    return herbs


def extract_indication(text: str) -> str:
    """첫 번째 문장(마침표 또는 문장 끝)을 주치 텍스트로 추출."""
    text = re.split(r'[①②③④⑤⑥⑦⑧⑨⑩]', text)[0]
    text = re.split(r'\[活套\]|\[用法\]|\[調劑法\]|\[適應症\]', text)[0]
    m = re.split(r'[.。]', text.strip())
    return m[0].strip() if m else text.strip()


def translate_symptoms(indication: str) -> list[str]:
    """주치 텍스트에서 증상 키워드를 추출하여 현대어로 변환 (괄호 제거)."""
    symptoms = []
    for key, val in SYMPTOM_MAP.items():
        if key in indication:
            symptoms.append(strip_paren(val))
    seen = set()
    result = []
    for s in symptoms:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result if result else [indication[:40]]


# 통 구분자 → ID 접두어
SECTION_PREFIX = {
    "上統": "BY_U_",
    "中統": "BY_M_",
    "下統": "BY_L_",
}
SECTION_SOURCE = {
    "上統": "방약합편 상통",
    "中統": "방약합편 중통",
    "下統": "방약합편 하통",
}


def parse_bangyak(filepath: str) -> list[dict]:
    with open(filepath, encoding='utf-16') as f:
        content = f.read()

    # 처방 블록 분리: '上統/中統/下統 N 처방명(漢字名)' 으로 시작하는 줄
    blocks = re.split(r'\n(?=(?:上統|中統|下統)\s+\d+)', content)

    formulas = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split('\n')

        # ── 헤더 파싱
        header_m = re.match(r'(上統|中統|下統)\s+(\d+)\s+([가-힣]+)\(([^)]+)\)', lines[0])
        if not header_m:
            continue
        section = header_m.group(1)
        num = int(header_m.group(2))
        name_kr = header_m.group(3)
        name_cn = header_m.group(4)

        prefix = SECTION_PREFIX.get(section, "BY_")
        formula_id = f"{prefix}{num:03d}"

        # ── 본초 파싱
        herb_lines = []
        i = 1
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped:
                i += 1
                break
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

        # ── 주치/가감 텍스트
        remaining = '\n'.join(lines[i:]).strip()
        indication_raw = extract_indication(remaining)

        manual = MANUAL_SYMPTOMS.get(formula_id)
        if manual:
            symptoms = [strip_paren(s) for s in manual]
        else:
            symptoms = translate_symptoms(indication_raw)

        formulas.append({
            "formula_id": formula_id,
            "name_kr": name_kr,
            "name_cn": name_cn,
            "source": SECTION_SOURCE.get(section, "방약합편"),
            "source_clause": f"{section} {num}",
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
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    base = Path(__file__).parent
    formulas = parse_bangyak(base / "bangyak.txt")

    out_path = base / "data" / "formulas_bangyak.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(formulas, f, ensure_ascii=False, indent=2)

    print(f"총 {len(formulas)}개 처방 파싱 완료 → {out_path}")
    print()
    for fo in formulas:
        herbs_str = ', '.join(f'{h["name_cn"]} {h["dose_g"]}g' for h in fo['composition'])
        print(f"[{fo['formula_id']}] {fo['name_kr']} ({fo['name_cn']})")
        print(f"  본초({len(fo['composition'])}종): {herbs_str}")
        print(f"  총량: {fo['total_dose_g']}g")
        print(f"  주치(원문): {fo['indications']['raw']}")
        print(f"  증상키워드: {fo['indications']['symptoms']}")
        print()
