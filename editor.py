"""
방약합편 처방 편집기 — 로컬 전용 Streamlit 앱
실행: streamlit run editor.py --server.address=127.0.0.1
"""

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

BASE      = Path(__file__).parent
DATA_PATH = BASE / 'data' / 'formulas_bangyak.json'


def load_raw():
    with open(DATA_PATH, encoding='utf-8') as f:
        return json.load(f)

def save_raw(data):
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def detect_issues(raw_data, chk_no_herb, chk_no_sym, chk_low_dose, chk_high_dose):
    issues = []
    for fo in raw_data:
        fid   = fo['formula_id']
        comp  = fo['composition']
        syms  = fo['indications']['symptoms']
        raw   = fo['indications']['raw']
        total = fo['total_dose_g']
        flags = []

        if chk_no_herb and len(comp) == 0:
            flags.append('약재 없음')
        if chk_no_sym and syms and syms[0] == raw[:40]:
            flags.append('증상 미매핑')
        if chk_low_dose and 0 < total < 10:
            flags.append(f'총량 {total}g 낮음')
        if chk_high_dose and total > 500:
            flags.append(f'총량 {total}g 높음')

        if flags:
            section_map = {'U': '上統', 'M': '中統', 'L': '下統'}
            sec = section_map.get(fid.split('_')[1], '?')
            issues.append({
                'formula_id': fid,
                '처방명': fo['name_kr'],
                '통': sec,
                '약재수': len(comp),
                '총량(g)': total,
                '증상': ', '.join(syms[:3]),
                '주치원문': raw[:60],
                '이슈': ' / '.join(flags),
            })
    return issues


# ── 페이지 설정
st.set_page_config(page_title='처방 편집기 (로컬)', layout='wide')
st.title('방약합편 처방 편집기')
st.caption('로컬 전용 — formulas_bangyak.json 직접 수정')

tab1, tab2 = st.tabs(['⚠️ 이상 처방 탐지', '✏️ 처방 편집'])


# ─────────────────────────────────────────────
# Tab 1: 이상 처방 탐지
# ─────────────────────────────────────────────
with tab1:
    st.subheader('이상 처방 탐지')

    c1, c2, c3, c4 = st.columns(4)
    chk_no_herb   = c1.checkbox('약재 없음 (0종)', value=True)
    chk_no_sym    = c2.checkbox('증상 미매핑', value=True)
    chk_low_dose  = c3.checkbox('총량 < 10g', value=True)
    chk_high_dose = c4.checkbox('총량 > 500g', value=True)

    if st.button('탐지', key='detect_btn', type='primary'):
        raw_data = load_raw()
        issues = detect_issues(raw_data, chk_no_herb, chk_no_sym, chk_low_dose, chk_high_dose)

        if issues:
            issue_df = pd.DataFrame(issues)
            st.warning(f'총 {len(issue_df)}개 처방에서 이슈 발견')
            st.dataframe(issue_df, use_container_width=True, hide_index=True,
                         height=35 * (len(issue_df) + 1) + 10)
            # 이슈 처방 ID를 세션에 저장 → 편집 탭에서 활용
            st.session_state['issue_ids'] = [r['formula_id'] for r in issues]
        else:
            st.success('이슈 없음')
            st.session_state['issue_ids'] = []


# ─────────────────────────────────────────────
# Tab 2: 처방 편집기
# ─────────────────────────────────────────────
with tab2:
    st.subheader('처방 편집기')

    raw_data  = load_raw()
    name_map  = {fo['formula_id']: fo['name_kr'] for fo in raw_data}
    id_map    = {v: k for k, v in name_map.items()}
    all_names = sorted(name_map.values())

    # 이슈 처방만 보기 토글
    issue_ids = st.session_state.get('issue_ids', [])
    use_issue = st.toggle(
        f'이상 처방만 보기 ({len(issue_ids)}개)',
        value=False,
        disabled=(len(issue_ids) == 0),
        help='이상 처방 탐지 탭에서 먼저 탐지를 실행하세요.',
    )

    if use_issue and issue_ids:
        filtered_names = sorted(name_map[fid] for fid in issue_ids if fid in name_map)
    else:
        filtered_names = all_names

    edit_name = st.selectbox('편집할 처방 선택', filtered_names, key='edit_select')
    edit_id   = id_map.get(edit_name)

    if edit_id:
        fo = next((x for x in raw_data if x['formula_id'] == edit_id), None)

    if edit_id and fo:
        st.divider()
        col_info, col_edit = st.columns([1, 2])

        with col_info:
            st.markdown(f"**{fo['name_kr']} ({fo['name_cn']})**")
            st.caption(fo.get('source_clause', ''))
            st.markdown('**현재 약재 구성**')
            if fo['composition']:
                for h in fo['composition']:
                    st.text(f"  {h['name_cn']}  {h['dose_g']}g  (비율 {h.get('dose_ratio', 0):.3f})")
            else:
                st.caption('(없음)')
            st.markdown('**주치 원문**')
            st.caption(fo['indications'].get('raw', ''))

        with col_edit:
            # key에 edit_id 포함 → 처방 변경 시 위젯 값 자동 초기화
            st.markdown('**약재 편집** — 한 줄에 `약재명 용량` (예: `甘草 4`)')
            herb_default = '\n'.join(
                f"{h['name_cn']} {h['dose_g']}"
                for h in fo['composition']
            )
            herb_input = st.text_area('약재 목록', value=herb_default,
                                      height=220, key=f'herb_{edit_id}')

            st.markdown('**증상 키워드** — 쉼표로 구분')
            sym_default = ', '.join(fo['indications'].get('symptoms', []))
            sym_input   = st.text_input('증상 키워드', value=sym_default,
                                        key=f'sym_{edit_id}')

            st.markdown('**주치 원문 수정**')
            raw_input = st.text_input('주치 원문',
                                      value=fo['indications'].get('raw', ''),
                                      key=f'raw_{edit_id}')

            if st.button('저장', key='edit_save', type='primary'):
                new_comp = []
                for line in herb_input.strip().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.rsplit(' ', 1)
                    if len(parts) == 2:
                        try:
                            dose = float(parts[1].replace('g', ''))
                            new_comp.append({'name_cn': parts[0].strip(), 'dose_g': dose})
                        except ValueError:
                            st.warning(f'용량 파싱 실패: {line}')

                total = sum(h['dose_g'] for h in new_comp)
                for h in new_comp:
                    h['dose_ratio'] = round(h['dose_g'] / total, 4) if total > 0 else 0

                new_syms = [s.strip() for s in sym_input.split(',') if s.strip()]

                for fo_item in raw_data:
                    if fo_item['formula_id'] == edit_id:
                        fo_item['composition']             = new_comp
                        fo_item['total_dose_g']            = round(total, 1)
                        fo_item['indications']['symptoms'] = new_syms
                        fo_item['indications']['raw']      = raw_input
                        break

                save_raw(raw_data)
                st.success(f'저장 완료 — {edit_name} / 약재 {len(new_comp)}종 / 총량 {round(total, 1)}g')
                st.rerun()
