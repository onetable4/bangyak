"""
방약합편 처방 편집기 — 로컬 전용 Streamlit 앱
실행: streamlit run editor.py --server.address=127.0.0.1

기능:
  1. 이상 처방 탐지 — 약재 없음 / 증상 미매핑 / 총량 이상치
  2. 처방 편집기    — 약재 구성·증상 키워드 수정 후 JSON 저장
"""

import json
import os
from pathlib import Path

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import streamlit as st


# ── 한글 폰트
def _set_korean_font():
    linux_candidates = [
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf',
    ]
    for path in linux_candidates:
        if os.path.exists(path):
            fm.fontManager.addfont(path)
            matplotlib.rc('font', family=fm.FontProperties(fname=path).get_name())
            return
    for _fname in fm.findSystemFonts():
        if any(k in _fname for k in ['Malgun', 'malgun', 'NanumGothic', 'Nanum', 'AppleGothic']):
            fm.fontManager.addfont(_fname)
            matplotlib.rc('font', family=fm.FontProperties(fname=_fname).get_name())
            return

_set_korean_font()
matplotlib.rcParams['axes.unicode_minus'] = False

BASE      = Path(__file__).parent
DATA_PATH = BASE / 'data' / 'formulas_bangyak.json'


def load_raw():
    with open(DATA_PATH, encoding='utf-8') as f:
        return json.load(f)

def save_raw(data):
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
    st.caption('약재 누락, 증상 미매핑, 용량 이상치 등 보완이 필요한 처방을 필터링합니다.')

    raw_data = load_raw()
    df = pd.DataFrame(raw_data).set_index('formula_id')
    section_map = {'U': '上統', 'M': '中統', 'L': '下統'}
    df['section'] = df.index.map(lambda x: section_map.get(x.split('_')[1], '?'))

    c1, c2, c3, c4 = st.columns(4)
    chk_no_herb   = c1.checkbox('약재 없음 (0종)', value=True)
    chk_no_sym    = c2.checkbox('증상 미매핑 (원문 그대로)', value=True)
    chk_low_dose  = c3.checkbox('총량 이상 (< 10g)', value=True)
    chk_high_dose = c4.checkbox('총량 이상 (> 500g)', value=True)

    issues = []
    for fid, row in df.iterrows():
        flags = []
        comp  = row['composition']
        syms  = row['indications']['symptoms']
        raw   = row['indications']['raw']
        total = row['total_dose_g']

        if chk_no_herb and len(comp) == 0:
            flags.append('약재 없음')
        if chk_no_sym and syms and syms[0] == raw[:40]:
            flags.append('증상 미매핑')
        if chk_low_dose and 0 < total < 10:
            flags.append(f'총량 {total}g (낮음)')
        if chk_high_dose and total > 500:
            flags.append(f'총량 {total}g (높음)')

        if flags:
            issues.append({
                'formula_id': fid,
                '처방명': row['name_kr'],
                '통': row['section'],
                '약재수': len(comp),
                '총량(g)': total,
                '증상': ', '.join(syms[:3]),
                '주치원문': raw[:60],
                '이슈': ' / '.join(flags),
            })

    if issues:
        issue_df = pd.DataFrame(issues)
        st.warning(f'총 {len(issue_df)}개 처방에서 이슈 발견')
        st.dataframe(issue_df, use_container_width=True, hide_index=True,
                     height=35 * (len(issue_df) + 1) + 10)

        fig, ax = plt.subplots(figsize=(5, 3))
        issue_df['통'].value_counts().plot.bar(ax=ax, color='tomato', edgecolor='white')
        ax.set_title('통별 이슈 처방 수')
        ax.set_xlabel('')
        ax.set_ylabel('처방 수')
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
    else:
        st.success('이슈 없음')


# ─────────────────────────────────────────────
# Tab 2: 처방 편집기
# ─────────────────────────────────────────────
with tab2:
    st.subheader('처방 편집기')

    raw_data = load_raw()
    name_map  = {fo['formula_id']: fo['name_kr'] for fo in raw_data}
    id_map    = {v: k for k, v in name_map.items()}
    all_names = sorted(name_map.values())

    edit_name = st.selectbox('편집할 처방 선택', all_names, key='edit_select')
    edit_id   = id_map.get(edit_name)

    if edit_id:
        fo = next((x for x in raw_data if x['formula_id'] == edit_id), {})

        st.divider()
        col_info, col_edit = st.columns([1, 2])

        with col_info:
            st.markdown(f"**{fo.get('name_kr')} ({fo.get('name_cn')})**")
            st.caption(fo.get('source_clause', ''))
            st.markdown('**현재 약재 구성**')
            for h in fo.get('composition', []):
                st.text(f"  {h['name_cn']}  {h['dose_g']}g  (비율 {h.get('dose_ratio', 0):.3f})")
            st.markdown('**주치 원문**')
            st.caption(fo.get('indications', {}).get('raw', ''))

        with col_edit:
            st.markdown('**약재 편집** — 한 줄에 `약재명 용량` (예: `甘草 4`)')
            herb_default = '\n'.join(
                f"{h['name_cn']} {h['dose_g']}"
                for h in fo.get('composition', [])
            )
            herb_input = st.text_area('약재 목록', value=herb_default,
                                      height=220, key='edit_herbs')

            st.markdown('**증상 키워드** — 쉼표로 구분')
            sym_default = ', '.join(fo.get('indications', {}).get('symptoms', []))
            sym_input   = st.text_input('증상 키워드', value=sym_default, key='edit_syms')

            st.markdown('**주치 원문 수정**')
            raw_default = fo.get('indications', {}).get('raw', '')
            raw_input   = st.text_input('주치 원문', value=raw_default, key='edit_raw')

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
