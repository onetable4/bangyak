"""
방약합편 처방 편집기 — 로컬 전용 Streamlit 앱
실행: streamlit run editor.py --server.address=127.0.0.1
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

BASE      = Path(__file__).parent
DATA_PATH = BASE / 'data' / 'formulas_bangyak.json'
SECTION_MAP = {'U': '上統', 'M': '中統', 'L': '下統'}


def load_raw():
    with open(DATA_PATH, encoding='utf-8') as f:
        return json.load(f)

def save_raw(data):
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_section(fid):
    return SECTION_MAP.get(fid.split('_')[1], '?')

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
            issues.append({
                'formula_id': fid,
                '처방명': fo['name_kr'],
                '약재수': len(comp),
                '총량(g)': total,
                '증상': ', '.join(syms[:3]),
                '주치원문': raw[:60],
                '이슈': ' / '.join(flags),
            })
    return issues


# ── 페이지 설정
st.set_page_config(page_title='처방 편집기 (로컬)', layout='wide')

st.markdown("""
<style>
.info-name  { font-size: 18px; font-weight: 700; color: #111; margin-bottom: 2px; }
.info-meta  { font-size: 12px; color: #888; margin-bottom: 12px; }
.info-label { font-size: 11px; font-weight: 600; color: #555;
              text-transform: uppercase; letter-spacing: 0.05em;
              margin-top: 14px; margin-bottom: 4px; }
.info-value { font-size: 13px; color: #222; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

st.title('방약합편 처방 편집기')
st.caption('로컬 전용 — formulas_bangyak.json 직접 수정')

tab1, tab2 = st.tabs(['⚠️ 이상 처방 탐지', '✏️ 처방 편집'])


# ─────────────────────────────────────────────
# Tab 1: 이상 처방 탐지
# ─────────────────────────────────────────────
with tab1:
    st.subheader('이상 처방 탐지')

    c1, c2, c3, c4 = st.columns(4)
    t1_no_herb   = c1.checkbox('약재 없음 (0종)', value=True, key='t1_herb')
    t1_no_sym    = c2.checkbox('증상 미매핑', value=True, key='t1_sym')
    t1_low_dose  = c3.checkbox('총량 < 10g', value=True, key='t1_low')
    t1_high_dose = c4.checkbox('총량 > 500g', value=True, key='t1_high')

    if st.button('탐지', key='detect_btn', type='primary'):
        raw_data = load_raw()
        issues = detect_issues(raw_data, t1_no_herb, t1_no_sym, t1_low_dose, t1_high_dose)
        if issues:
            issue_df = pd.DataFrame(issues)
            st.warning(f'총 {len(issue_df)}개 처방에서 이슈 발견')
            st.dataframe(issue_df, width='stretch', hide_index=True,
                         height=35 * (len(issue_df) + 1) + 10)
            st.session_state['issue_ids'] = [r['formula_id'] for r in issues]
        else:
            st.success('이슈 없음')
            st.session_state['issue_ids'] = []


# ─────────────────────────────────────────────
# Tab 2: 처방 편집기
# ─────────────────────────────────────────────
with tab2:
    raw_data   = load_raw()
    name_map   = {fo['formula_id']: fo['name_kr'] for fo in raw_data}
    cn_map     = {fo['formula_id']: fo['name_cn'] for fo in raw_data}
    clause_map = {fo['formula_id']: fo.get('source_clause', '') for fo in raw_data}

    # ── 탐지 조건
    with st.expander('탐지 조건', expanded=False):
        cc1, cc2, cc3, cc4 = st.columns(4)
        t2_no_herb   = cc1.checkbox('약재 없음 (0종)', value=True, key='t2_herb')
        t2_no_sym    = cc2.checkbox('증상 미매핑', value=True, key='t2_sym')
        t2_low_dose  = cc3.checkbox('총량 < 10g', value=True, key='t2_low')
        t2_high_dose = cc4.checkbox('총량 > 500g', value=True, key='t2_high')
        if st.button('탐지 실행', key='detect_btn2', type='secondary'):
            issues2 = detect_issues(raw_data, t2_no_herb, t2_no_sym, t2_low_dose, t2_high_dose)
            st.session_state['issue_ids'] = [r['formula_id'] for r in issues2]
            st.success(f'{len(issues2)}개 이슈 처방 탐지 완료')

    issue_ids = st.session_state.get('issue_ids', [])
    use_issue = st.toggle(
        f'이상 처방만 보기 ({len(issue_ids)}개)',
        value=False,
        disabled=(len(issue_ids) == 0),
        help='탐지 조건을 열어 탐지를 먼저 실행하세요.',
    )

    target_ids = [fid for fid in issue_ids if fid in name_map] if (use_issue and issue_ids) \
                 else list(name_map.keys())

    # ── 3단 레이아웃
    col_list, col_info, col_edit = st.columns([1, 1, 2])

    # ── 좌측: selectbox + 필터
    with col_list:
        st.markdown('**처방 선택**')

        sec_sel = st.radio('통', ['전체', '上統', '中統', '下統'],
                           horizontal=True, key='list_sec',
                           label_visibility='collapsed')
        search  = st.text_input('검색', placeholder='처방명 검색...',
                                key='list_search', label_visibility='collapsed')

        filtered = [
            fid for fid in target_ids
            if (sec_sel == '전체' or get_section(fid) == sec_sel)
            and (not search or search in name_map[fid])
        ]

        # 표시 레이블: '교밀탕 (膠蜜湯 · 上統 80)'
        options = [
            f"{name_map[fid]}  ({cn_map[fid]} · {clause_map[fid]})"
            for fid in filtered
        ]
        fid_by_label = dict(zip(options, filtered))

        st.caption(f'{len(filtered)}개')

        if options:
            # 현재 선택된 처방이 목록에 있으면 유지, 없으면 첫 번째로
            cur = st.session_state.get('selected_id')
            cur_label = next((lbl for lbl, fid in fid_by_label.items() if fid == cur), options[0])
            chosen = st.selectbox('처방', options,
                                  index=options.index(cur_label),
                                  key='formula_select',
                                  label_visibility='collapsed')
            st.session_state['selected_id'] = fid_by_label[chosen]
        else:
            st.caption('조건에 맞는 처방이 없습니다.')
            st.session_state['selected_id'] = None

    edit_id = st.session_state.get('selected_id')
    fo = next((x for x in raw_data if x['formula_id'] == edit_id), None) if edit_id else None

    # ── 가운데: 현재 처방 정보
    with col_info:
        if fo:
            st.markdown(
                f'<div class="info-name">{fo["name_kr"]}</div>'
                f'<div class="info-meta">{fo["name_cn"]} &nbsp;·&nbsp; {fo.get("source_clause","")}</div>',
                unsafe_allow_html=True,
            )
            st.divider()

            st.markdown('<div class="info-label">약재 구성</div>', unsafe_allow_html=True)
            if fo['composition']:
                rows = [{'약재': h['name_cn'], '용량(g)': h['dose_g'],
                         '비율': f"{h.get('dose_ratio', 0):.3f}"}
                        for h in fo['composition']]
                st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
            else:
                st.markdown('<div class="info-value">(약재 없음)</div>', unsafe_allow_html=True)

            st.markdown('<div class="info-label">주치 원문</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="info-value">{fo["indications"].get("raw","")}</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="info-label">증상 키워드</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="info-value">{", ".join(fo["indications"].get("symptoms",[])) or "(없음)"}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption('좌측에서 처방을 선택하세요.')

    # ── 우측: 편집 폼
    with col_edit:
        if fo:
            st.markdown('<div class="info-label">약재 목록</div>', unsafe_allow_html=True)
            st.caption('한 줄에 `약재명 용량` 형식 (예: 甘草 4)')
            herb_input = st.text_area('약재 목록',
                                      value='\n'.join(f"{h['name_cn']} {h['dose_g']}"
                                                      for h in fo['composition']),
                                      height=200, key=f'herb_{edit_id}',
                                      label_visibility='collapsed')

            st.markdown('<div class="info-label">증상 키워드</div>', unsafe_allow_html=True)
            st.caption('쉼표로 구분')
            sym_input = st.text_input('증상 키워드',
                                      value=', '.join(fo['indications'].get('symptoms', [])),
                                      key=f'sym_{edit_id}',
                                      label_visibility='collapsed')

            st.markdown('<div class="info-label">주치 원문</div>', unsafe_allow_html=True)
            raw_input = st.text_input('주치 원문',
                                      value=fo['indications'].get('raw', ''),
                                      key=f'raw_{edit_id}',
                                      label_visibility='collapsed')

            st.write('')
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
                st.success(f'저장 완료 — {fo["name_kr"]} / 약재 {len(new_comp)}종 / 총량 {round(total, 1)}g')
                st.rerun()
        else:
            st.caption('좌측에서 처방을 선택하세요.')
