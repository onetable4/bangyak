"""
방약합편 처방 탐색기 — Streamlit 앱
실행: streamlit run app.py --server.address=127.0.0.1
"""

import json
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from sklearn.preprocessing import normalize
import streamlit as st

# ── 한글 폰트
import os

def _set_korean_font():
    # 1) Linux apt 설치 경로 직접 탐색
    linux_candidates = [
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    ]
    for path in linux_candidates:
        if os.path.exists(path):
            fm.fontManager.addfont(path)
            prop = fm.FontProperties(fname=path)
            matplotlib.rc('font', family=prop.get_name())
            return

    # 2) Windows / macOS — 시스템 폰트 검색
    for _fname in fm.findSystemFonts():
        if any(k in _fname for k in ['Malgun', 'malgun', 'NanumGothic', 'Nanum', 'AppleGothic']):
            fm.fontManager.addfont(_fname)
            prop = fm.FontProperties(fname=_fname)
            matplotlib.rc('font', family=prop.get_name())
            return

_set_korean_font()
matplotlib.rcParams['axes.unicode_minus'] = False

BASE = Path(__file__).parent

@st.cache_data(hash_funcs={pd.DataFrame: lambda _: None})
def load_data():
    with open(BASE / 'data' / 'formulas_bangyak.json', encoding='utf-8') as f:
        raw = json.load(f)
    df = pd.DataFrame(raw).set_index('formula_id')
    section_map = {'U': '上統', 'M': '中統', 'L': '下統'}
    df['section'] = df.index.map(lambda x: section_map.get(x.split('_')[1], '?'))
    df['herb_count'] = df['composition'].apply(len)
    return df

@st.cache_data
def build_F(df):
    rows = []
    for fid, row in df.iterrows():
        for herb in row['composition']:
            rows.append({'formula_id': fid, 'herb': herb['name_cn'], 'ratio': herb['dose_ratio']})
    if not rows:
        return pd.DataFrame()
    long = pd.DataFrame(rows)
    F = long.pivot_table(index='formula_id', columns='herb', values='ratio', fill_value=0)
    return F

@st.cache_data
def build_sim(F_values, F_index):
    normed = normalize(F_values, norm='l2')
    sim = normed @ normed.T
    return pd.DataFrame(sim, index=F_index, columns=F_index)

@st.cache_data
def build_symptom_matrix(df):
    """증상 키워드 기반 처방-증상 이진 행렬"""
    all_syms = sorted({s for syms in df['indications'].apply(lambda x: x['symptoms']) for s in syms})
    rows = {}
    for fid, row in df.iterrows():
        vec = {s: 1.0 for s in row['indications']['symptoms']}
        rows[fid] = vec
    S = pd.DataFrame(rows, index=all_syms).T.fillna(0)
    return S

# ── 데이터 초기화
df = load_data()
F_all = build_F(df)
sim_all = build_sim(F_all.values, list(F_all.index))
S_all = build_symptom_matrix(df)
# 증상 행렬은 F에 있는 처방만
S_valid = S_all.loc[S_all.index.isin(sim_all.index)]
sim_symp = build_sim(S_valid.values, list(S_valid.index))

name_map = df['name_kr'].to_dict()
id_map = {v: k for k, v in name_map.items()}
valid_ids = set(sim_all.index)
all_names = sorted(name_map.values())

# ── 페이지 설정
st.set_page_config(page_title='방약합편 처방 탐색기', layout='wide')
st.title('방약합편 처방 탐색기')
st.caption(
    f'上統 {(df.section=="上統").sum()} / '
    f'中統 {(df.section=="中統").sum()} / '
    f'下統 {(df.section=="下統").sum()} — 총 {len(df)}개 처방'
)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    '🔍 유사 처방 검색', '⚖️ 처방 비교', '🗺️ 히트맵', '🏆 유사도 TOP 쌍',
    '⚠️ 이상 처방 탐지', '✏️ 처방 편집',
])


# ─────────────────────────────────────────────
# Tab 1: 유사 처방 검색
# ─────────────────────────────────────────────
with tab1:
    st.subheader('유사 처방 검색')
    col1, col2 = st.columns([3, 1])
    with col1:
        query_name = st.selectbox('처방 선택', all_names, key='tab1_select')
    with col2:
        top_n = st.slider('결과 수', 3, 30, 10, key='tab1_topn')

    # 선택 처방 미리보기
    _qid = id_map.get(query_name)
    if _qid and _qid in df.index:
        _qrow = df.loc[_qid]
        _herbs_str = ', '.join(f"{h['name_cn']} {h['dose_g']}g" for h in _qrow['composition'])
        with st.container(border=True):
            st.markdown(f"**{_qrow['name_kr']} ({_qrow['name_cn']})** — {_qrow['source_clause']}")
            st.caption(f"구성: {_herbs_str}")
            st.caption(f"증상: {', '.join(_qrow['indications']['symptoms'])}")

    if st.button('검색', key='tab1_btn', type='primary'):
        query_id = id_map.get(query_name)
        if query_id and query_id in sim_all.index:
            scores_herb = sim_all.loc[query_id].drop(query_id).sort_values(ascending=False).head(top_n)
            scores_symp = (
                sim_symp.loc[query_id].drop(query_id).sort_values(ascending=False).head(top_n)
                if query_id in sim_symp.index else pd.Series(dtype=float)
            )
            qrow = df.loc[query_id]
            st.divider()

            q_herbs = {h['name_cn'] for h in qrow['composition']}
            rows = []
            for fid, score in scores_herb.items():
                row = df.loc[fid]
                t_herbs = {h['name_cn'] for h in row['composition']}
                common = q_herbs & t_herbs
                rows.append({
                    '처방명': row['name_kr'],
                    '통': row['section'],
                    '약재 유사도': round(score, 3),
                    '증상 유사도': round(scores_symp.get(fid, 0), 3),
                    '공통약재수': len(common),
                    '공통약재': ', '.join(sorted(common)),
                    '증상': ', '.join(row['indications']['symptoms'][:3]),
                })
            st.dataframe(
                pd.DataFrame(rows),
                width='stretch',
                hide_index=True,
                height=35 * (len(rows) + 1) + 10,  # 스크롤 없이 전체 표시
            )

            # 두 차트 병렬 (데스크탑 1×2)
            ch1, ch2 = st.columns(2)
            with ch1:
                fig, ax = plt.subplots(figsize=(5, max(3, top_n * 0.28)))
                scores_herb.rename(index=name_map)[::-1].plot.barh(ax=ax, color='steelblue')
                ax.set_xlim(0, 1)
                ax.set_title('약재 구성 유사도')
                ax.set_xlabel('코사인 유사도')
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()
            with ch2:
                if not scores_symp.empty:
                    fig2, ax2 = plt.subplots(figsize=(5, max(3, top_n * 0.28)))
                    scores_symp.rename(index=name_map)[::-1].plot.barh(ax=ax2, color='coral')
                    ax2.set_xlim(0, 1)
                    ax2.set_title('증상 키워드 유사도')
                    ax2.set_xlabel('코사인 유사도')
                    plt.tight_layout()
                    st.pyplot(fig2)
                    plt.close()
                else:
                    st.info('증상 유사도 데이터 없음')
        else:
            st.warning('해당 처방의 약재 데이터가 없습니다.')


# ─────────────────────────────────────────────
# Tab 2: 처방 비교
# ─────────────────────────────────────────────
with tab2:
    st.subheader('처방 비교')
    _default_a = all_names.index('향사평위산') if '향사평위산' in all_names else 0
    _default_b = all_names.index('불환금정기산') if '불환금정기산' in all_names else 1
    col1, col2 = st.columns(2)
    with col1:
        name_a = st.selectbox('처방 A', all_names, index=_default_a, key='tab2_a')
        _id_a = id_map.get(name_a)
        if _id_a and _id_a in df.index:
            _ra = df.loc[_id_a]
            with st.container(border=True):
                st.markdown(f"**{_ra['name_kr']} ({_ra['name_cn']})** — {_ra['source_clause']}")
                st.caption(', '.join(f"{h['name_cn']} {h['dose_g']}g" for h in _ra['composition']))
                st.caption(f"증상: {', '.join(_ra['indications']['symptoms'])}")
    with col2:
        name_b = st.selectbox('처방 B', all_names, index=_default_b, key='tab2_b')
        _id_b = id_map.get(name_b)
        if _id_b and _id_b in df.index:
            _rb = df.loc[_id_b]
            with st.container(border=True):
                st.markdown(f"**{_rb['name_kr']} ({_rb['name_cn']})** — {_rb['source_clause']}")
                st.caption(', '.join(f"{h['name_cn']} {h['dose_g']}g" for h in _rb['composition']))
                st.caption(f"증상: {', '.join(_rb['indications']['symptoms'])}")

    if st.button('비교', key='tab2_btn', type='primary'):
        id_a, id_b = id_map.get(name_a), id_map.get(name_b)
        if id_a and id_b and id_a in sim_all.index and id_b in sim_all.index:
            score = sim_all.loc[id_a, id_b]
            st.metric('코사인 유사도', f'{score:.4f}')

            row_a, row_b = df.loc[id_a], df.loc[id_b]
            herbs_a = {h['name_cn']: h['dose_ratio'] for h in row_a['composition']}
            herbs_b = {h['name_cn']: h['dose_ratio'] for h in row_b['composition']}
            all_herbs = sorted(set(herbs_a) | set(herbs_b))
            common = set(herbs_a) & set(herbs_b)
            only_a = set(herbs_a) - set(herbs_b)
            only_b = set(herbs_b) - set(herbs_a)

            c1, c2, c3 = st.columns(3)
            c1.metric('공통 약재', len(common))
            c2.metric(f'{name_a} 고유', len(only_a))
            c3.metric(f'{name_b} 고유', len(only_b))

            cmp_rows = []
            for h in all_herbs:
                tag = '공통' if h in common else ('A만' if h in only_a else 'B만')
                cmp_rows.append({
                    '약재': h,
                    f'{name_a} 비율': round(herbs_a.get(h, 0), 4),
                    f'{name_b} 비율': round(herbs_b.get(h, 0), 4),
                    '구분': tag,
                })
            cmp_df = pd.DataFrame(cmp_rows).sort_values('구분')
            st.dataframe(
                cmp_df, width='stretch', hide_index=True,
                height=35 * (len(cmp_df) + 1) + 10,
            )

            # 바 차트 + 레이더 차트 병렬 (데스크탑 1×2)
            ch1, ch2 = st.columns(2)
            with ch1:
                fig, ax = plt.subplots(figsize=(5, max(4, len(all_herbs) * 0.28)))
                y = np.arange(len(all_herbs))
                ax.barh(y - 0.2, [herbs_a.get(h, 0) for h in all_herbs], height=0.4, label=name_a, color='steelblue', alpha=0.8)
                ax.barh(y + 0.2, [herbs_b.get(h, 0) for h in all_herbs], height=0.4, label=name_b, color='coral', alpha=0.8)
                ax.set_yticks(y); ax.set_yticklabels(all_herbs, fontsize=8)
                ax.set_xlabel('용량 비율')
                ax.set_title('약재 용량 비율 비교')
                ax.legend()
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()

            with ch2:
                radar_herbs = sorted(
                    set(herbs_a) | set(herbs_b),
                    key=lambda h: max(herbs_a.get(h, 0), herbs_b.get(h, 0)),
                    reverse=True,
                )[:20]
                N = len(radar_herbs)
                if N >= 3:
                    angles = [2 * np.pi * i / N for i in range(N)] + [0]
                    vals_a_r = [herbs_a.get(h, 0) for h in radar_herbs] + [herbs_a.get(radar_herbs[0], 0)]
                    vals_b_r = [herbs_b.get(h, 0) for h in radar_herbs] + [herbs_b.get(radar_herbs[0], 0)]
                    fig_r, ax_r = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
                    ax_r.plot(angles, vals_a_r, 'o-', color='steelblue', linewidth=1.5, label=name_a)
                    ax_r.fill(angles, vals_a_r, alpha=0.2, color='steelblue')
                    ax_r.plot(angles, vals_b_r, 'o-', color='coral', linewidth=1.5, label=name_b)
                    ax_r.fill(angles, vals_b_r, alpha=0.2, color='coral')
                    ax_r.set_xticks(angles[:-1])
                    ax_r.set_xticklabels(radar_herbs, fontsize=8)
                    ax_r.set_title(f'레이더 차트 (상위 {N}개 약재)', pad=20)
                    ax_r.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
                    plt.tight_layout()
                    st.pyplot(fig_r)
                    plt.close()

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**{name_a}** 증상")
                st.write(', '.join(row_a['indications']['symptoms']))
            with c2:
                st.markdown(f"**{name_b}** 증상")
                st.write(', '.join(row_b['indications']['symptoms']))
        else:
            st.warning('선택한 처방 중 약재 데이터가 없는 처방이 있습니다.')


# ─────────────────────────────────────────────
# Tab 3: 히트맵
# ─────────────────────────────────────────────
with tab3:
    st.subheader('처방 선택 히트맵')

    mode = st.radio('처방 선택 방식', ['통 전체', '직접 선택'], horizontal=True)

    if mode == '통 전체':
        sec = st.selectbox('통 선택', ['上統', '中統', '下統'])
        max_show = st.slider('최대 표시 처방 수', 10, 60, 40)
        selected_ids = [i for i in df[df['section'] == sec].index if i in valid_ids][:max_show]
    else:
        selected_names = st.multiselect(
            '처방 검색 후 추가',
            options=all_names,
            default=[],
            placeholder='처방명을 입력해 검색...',
        )
        selected_ids = [id_map[n] for n in selected_names if n in id_map and id_map[n] in valid_ids]
        if selected_ids:
            st.caption(f'선택됨 {len(selected_ids)}개: {", ".join(name_map[i] for i in selected_ids)}')

    heatmap_type = st.radio('히트맵 종류', ['처방 간 유사도', '처방-약재 행렬'], horizontal=True)

    run_heatmap = st.button('히트맵 그리기', key='tab3_btn', type='primary')

    if run_heatmap:
        if len(selected_ids) < 2:
            st.info('처방을 2개 이상 선택하세요.')
        elif heatmap_type == '처방 간 유사도':
            sub_sim = sim_all.loc[selected_ids, selected_ids]
            labels = [name_map.get(i, i) for i in selected_ids]
            n = len(selected_ids)
            fig, ax = plt.subplots(figsize=(max(8, n * 0.28), max(7, n * 0.28)))
            im = ax.imshow(sub_sim.values, cmap='RdYlGn', vmin=0, vmax=1, aspect='auto')
            ax.set_xticks(range(n)); ax.set_xticklabels(labels, rotation=90, fontsize=7)
            ax.set_yticks(range(n)); ax.set_yticklabels(labels, fontsize=7)
            plt.colorbar(im, ax=ax, label='코사인 유사도')
            ax.set_title('처방 간 코사인 유사도')
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()

            # 수치표 + 쌍별 표 병렬
            pair_rows = []
            for i in range(n):
                for j in range(i + 1, n):
                    pair_rows.append({
                        '처방 A': labels[i],
                        '처방 B': labels[j],
                        '코사인 유사도': round(sub_sim.values[i, j], 4),
                    })
            pair_rows.sort(key=lambda x: x['코사인 유사도'], reverse=True)
            pair_df = pd.DataFrame(pair_rows)

            tc1, tc2 = st.columns(2)
            with tc1:
                # 동명 처방 대비 고유 레이블 (처방명 중복 시 ID 병기)
                seen = {}
                unique_labels = []
                for fid, lbl in zip(selected_ids, labels):
                    if labels.count(lbl) > 1:
                        unique_labels.append(f"{lbl}({fid})")
                    else:
                        unique_labels.append(lbl)
                sim_display = sub_sim.copy()
                sim_display.index = unique_labels
                sim_display.columns = unique_labels
                sim_display = sim_display.round(3)
                st.markdown('**유사도 수치표**')
                st.dataframe(sim_display, width='stretch',
                             height=35 * (n + 1) + 10)
            with tc2:
                st.markdown('**쌍별 유사도 (내림차순)**')
                st.dataframe(pair_df, width='stretch', hide_index=True,
                             height=35 * (len(pair_df) + 1) + 10)
        else:
            sub_F = F_all.loc[[i for i in selected_ids if i in F_all.index]]
            active_cols = sub_F.columns[(sub_F > 0).any()]
            sub_F = sub_F[active_cols]
            labels_r = [name_map.get(i, i) for i in sub_F.index]
            nr, nc = sub_F.shape
            fig, ax = plt.subplots(figsize=(max(10, nc * 0.3), max(6, nr * 0.3)))
            im = ax.imshow(sub_F.values, cmap='YlOrRd', aspect='auto', vmin=0, vmax=0.5)
            ax.set_xticks(range(nc)); ax.set_xticklabels(sub_F.columns, rotation=90, fontsize=7)
            ax.set_yticks(range(nr)); ax.set_yticklabels(labels_r, fontsize=7)
            plt.colorbar(im, ax=ax, label='용량 비율')
            ax.set_title('처방-약재 행렬')
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()


# ─────────────────────────────────────────────
# Tab 4: 유사도 TOP 쌍
# ─────────────────────────────────────────────
with tab4:
    st.subheader('유사도 TOP 처방 쌍')

    col1, col2 = st.columns([1, 2])
    with col1:
        top_k = st.slider('TOP K 쌍', 10, 100, 30)
        sec_filter = st.multiselect('통 필터 (비우면 전체)', ['上統', '中統', '下統'])

    run_top = st.button('분석', key='tab4_btn', type='primary')

    if run_top:
        filtered_ids = [
            i for i in (df[df['section'].isin(sec_filter)].index if sec_filter else df.index)
            if i in valid_ids
        ]
        sub_sim = sim_all.loc[filtered_ids, filtered_ids]
        arr = sub_sim.values
        idx_list = list(sub_sim.index)

        pairs = []
        for i in range(len(idx_list)):
            for j in range(i + 1, len(idx_list)):
                pairs.append((arr[i, j], idx_list[i], idx_list[j]))
        pairs.sort(reverse=True)
        top_pairs = pairs[:top_k]

        pair_rows = []
        for score, id_a, id_b in top_pairs:
            ra, rb = df.loc[id_a], df.loc[id_b]
            herbs_a = {h['name_cn'] for h in ra['composition']}
            herbs_b = {h['name_cn'] for h in rb['composition']}
            common = herbs_a & herbs_b
            pair_rows.append({
                '유사도': round(score, 4),
                '처방 A': ra['name_kr'],
                '통 A': ra['section'],
                '처방 B': rb['name_kr'],
                '통 B': rb['section'],
                '공통약재수': len(common),
                '공통약재': ', '.join(sorted(common)[:5]) + ('…' if len(common) > 5 else ''),
            })

        st.dataframe(pd.DataFrame(pair_rows), width='stretch', hide_index=True)

        with col2:
            all_scores = [p[0] for p in pairs]
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.hist(all_scores, bins=50, color='steelblue', edgecolor='white')
            ax.axvline(top_pairs[-1][0], color='red', linestyle='--', label=f'TOP {top_k} 기준')
            ax.set_xlabel('코사인 유사도')
            ax.set_ylabel('처방 쌍 수')
            ax.set_title('처방 쌍 유사도 분포')
            ax.legend()
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()


# ─────────────────────────────────────────────
# Tab 5: 이상 처방 탐지
# ─────────────────────────────────────────────
with tab5:
    st.subheader('이상 처방 탐지')
    st.caption('약재 누락, 증상 미매핑, 용량 이상치 등 보완이 필요한 처방을 필터링합니다.')

    # 탐지 기준 선택
    c1, c2, c3, c4 = st.columns(4)
    chk_no_herb   = c1.checkbox('약재 없음 (0종)', value=True)
    chk_no_sym    = c2.checkbox('증상 미매핑 (원문 그대로)', value=True)
    chk_low_dose  = c3.checkbox('총량 이상 (< 10g)', value=True)
    chk_high_dose = c4.checkbox('총량 이상 (> 500g)', value=True)

    issues = []
    for fid, row in df.iterrows():
        flags = []
        comp = row['composition']
        syms = row['indications']['symptoms']
        raw  = row['indications']['raw']
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

        # 통별 이슈 분포
        fig, ax = plt.subplots(figsize=(6, 3))
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
# Tab 6: 처방 편집기
# ─────────────────────────────────────────────
with tab6:
    st.subheader('처방 편집기')
    st.caption('처방을 선택해 약재 구성·증상 키워드를 수정하고 JSON에 저장합니다.')

    DATA_PATH = BASE / 'data' / 'formulas_bangyak.json'

    # 편집할 처방 선택
    edit_name = st.selectbox('편집할 처방 선택', all_names, key='edit_select')
    edit_id   = id_map.get(edit_name)

    if edit_id:
        # 최신 JSON 직접 읽기 (캐시 우회)
        with open(DATA_PATH, encoding='utf-8') as f:
            raw_data = json.load(f)
        formula_list = {fo['formula_id']: fo for fo in raw_data}
        fo = formula_list.get(edit_id, {})

        st.divider()
        col_info, col_edit = st.columns([1, 2])

        with col_info:
            st.markdown(f"**{fo.get('name_kr')} ({fo.get('name_cn')})**")
            st.caption(fo.get('source_clause', ''))
            st.markdown('**현재 약재 구성**')
            for h in fo.get('composition', []):
                st.text(f"  {h['name_cn']}  {h['dose_g']}g  (비율 {h.get('dose_ratio', 0):.3f})")
            st.markdown('**현재 주치 원문**')
            st.caption(fo.get('indications', {}).get('raw', ''))

        with col_edit:
            st.markdown('**약재 편집** (한 줄에 `약재명 용량g`, 예: `甘草 4`)')
            herb_text_default = '\n'.join(
                f"{h['name_cn']} {h['dose_g']}"
                for h in fo.get('composition', [])
            )
            herb_input = st.text_area('약재 목록', value=herb_text_default,
                                      height=200, key='edit_herbs')

            st.markdown('**증상 키워드 편집** (쉼표로 구분)')
            sym_default = ', '.join(fo.get('indications', {}).get('symptoms', []))
            sym_input = st.text_input('증상 키워드', value=sym_default, key='edit_syms')

            if st.button('저장', key='edit_save', type='primary'):
                # 약재 파싱
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
                            continue

                total = sum(h['dose_g'] for h in new_comp)
                for h in new_comp:
                    h['dose_ratio'] = round(h['dose_g'] / total, 4) if total > 0 else 0

                # 증상 파싱
                new_syms = [s.strip() for s in sym_input.split(',') if s.strip()]

                # JSON 업데이트
                for fo_item in raw_data:
                    if fo_item['formula_id'] == edit_id:
                        fo_item['composition']          = new_comp
                        fo_item['total_dose_g']         = round(total, 1)
                        fo_item['indications']['symptoms'] = new_syms
                        break

                with open(DATA_PATH, 'w', encoding='utf-8') as f:
                    json.dump(raw_data, f, ensure_ascii=False, indent=2)

                st.success(f'{edit_name} 저장 완료 — 약재 {len(new_comp)}종, 총량 {round(total,1)}g')
                st.cache_data.clear()  # 캐시 초기화해서 다음 분석에 반영
