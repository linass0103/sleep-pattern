
from pathlib import Path
import re

import mne
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ----------------------------
# 기본 설정
# ----------------------------
st.set_page_config(
    page_title="나의 수면 리듬 분석실",
    page_icon="🌙",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_FILE = Path(__file__).parent / "SC4001EC-Hypnogram.edf"

# ----------------------------
# 몽환적인 밤하늘 디자인
# ----------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&display=swap');

:root {
    --navy: #101b4b;
    --panel: rgba(28, 44, 101, 0.82);
    --lavender: #b9b5ff;
    --pink: #f2a8ef;
    --sky: #77c7ff;
    --cream: #ffe3ae;
    --mint: #8fe6db;
}

.stApp {
    background:
        radial-gradient(ellipse at 80% 4%, rgba(180,155,255,.22), transparent 35%),
        radial-gradient(ellipse at 15% 20%, rgba(255,157,190,.14), transparent 30%),
        linear-gradient(160deg, #081333 0%, #18275f 48%, #29245d 76%, #49376d 100%);
    color: #f7f5ff;
    font-family: 'Gowun Dodum', sans-serif;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #101d4e, #192a60 70%, #32265c);
    border-right: 1px solid rgba(190,190,255,.25);
}

[data-testid="stSidebar"] * {
    color: #f7f3ff;
}

h1, h2, h3 {
    color: #fff7ff !important;
    letter-spacing: -0.5px;
}

p, label, [data-testid="stCaptionContainer"] {
    color: #dce4ff;
}

.hero {
    position: relative;
    overflow: hidden;
    padding: 32px 30px 28px;
    margin: 4px 0 22px;
    border-radius: 24px;
    border: 1px solid rgba(221,211,255,.3);
    background:
        radial-gradient(circle at 84% 25%, #fff7df 0%, #f4d9ff 5%,
          #b9b7ff 10%, transparent 11%),
        radial-gradient(ellipse at 82% 28%, rgba(255,192,222,.4), transparent 27%),
        linear-gradient(180deg, #101b49 0%, #414a91 48%, #c77da9 100%);
    box-shadow: 0 12px 35px rgba(3,7,35,.25);
}

.hero:before {
    content: "✦     ·      ✧      ·        ✦      ·     ✧";
    position: absolute;
    top: 13px;
    left: 22px;
    right: 10px;
    color: #fff1c8;
    opacity: .8;
    letter-spacing: 13px;
    pointer-events: none;
}

.hero:after {
    content: "✧   ·     ✦       ·      ✧      ·";
    position: absolute;
    top: 55px;
    right: 15px;
    color: #fff1c8;
    opacity: .7;
    letter-spacing: 8px;
    pointer-events: none;
}

.hero h1 {
    font-size: clamp(28px, 4vw, 43px);
    margin: 10px 0 8px;
    text-shadow: 0 2px 20px rgba(255,221,255,.3);
}

.hero p {
    font-size: 15px;
    max-width: 600px;
    line-height: 1.8;
}

.hero-tag {
    display: inline-block;
    border: 1px solid rgba(255,255,255,.3);
    background: rgba(22,30,78,.4);
    padding: 6px 13px;
    border-radius: 30px;
    font-size: 12px;
}

.panel {
    padding: 20px;
    border-radius: 19px;
    background: linear-gradient(145deg, rgba(39,57,119,.82),
        rgba(23,35,83,.9));
    border: 1px solid rgba(178,186,255,.32);
    box-shadow: 0 8px 24px rgba(4,8,40,.18);
    margin-bottom: 12px;
}

.metric-card {
    padding: 18px;
    min-height: 126px;
    border-radius: 18px;
    background: linear-gradient(140deg, rgba(69,89,162,.62),
        rgba(34,46,105,.88));
    border: 1px solid rgba(201,198,255,.38);
    box-shadow: 0 8px 20px rgba(4,8,40,.15);
}

.metric-label {
    color: #d7ddff;
    font-size: 13px;
}

.metric-value {
    color: white;
    font-size: 27px;
    font-weight: bold;
    margin: 8px 0 3px;
}

.metric-note {
    color: #c5d4ff;
    font-size: 12px;
}

.section-label {
    font-size: 19px;
    font-weight: bold;
    color: #fff6ff;
    margin-bottom: 4px;
}

.small-note {
    font-size: 12px;
    line-height: 1.7;
    color: #c5d2fa;
}

div[data-testid="stPlotlyChart"] {
    border-radius: 16px;
}

.stButton button {
    border-radius: 12px;
    border: 1px solid #aaaaff;
    background: #354a99;
    color: white;
}

hr {
    border-color: rgba(205,205,255,.2);
}

footer {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# 사이드바
# ----------------------------
with st.sidebar:
    st.markdown(
        "<div style='text-align:center;font-size:44px;padding:12px'>🌙</div>",
        unsafe_allow_html=True
    )
    st.markdown("## 수면 리듬 분석실")
    page = st.radio(
        "메뉴",
        ["홈", "수면 단계 분석", "통계 및 비교", "데이터 정보"],
        label_visibility="collapsed"
    )
    st.divider()
    st.markdown("### ✨ 오늘도 좋은 꿈")
    st.caption("공개 연구 데이터를 통해 수면의 구조를 살펴봅니다.")

# ----------------------------
# 데이터 불러오기
# ----------------------------
@st.cache_data
def load_data(path, modified):
    annotations = mne.read_annotations(path)
    rows = []

    for ann in annotations:
        description = str(ann["description"])
        match = re.search(
            r"Sleep stage\s+([W1234R?])",
            description,
            flags=re.IGNORECASE
        )

        if not match:
            continue

        code = match.group(1).upper()
        mapping = {
            "W": "깨어 있음",
            "1": "얕은 수면",
            "2": "얕은 수면",
            "3": "깊은 수면",
            "4": "깊은 수면",
            "R": "REM 수면",
            "?": "미분류"
        }

        duration = float(ann["duration"])
        if duration <= 0:
            continue

        rows.append({
            "시작(초)": float(ann["onset"]),
            "지속시간(초)": duration,
            "수면 단계": mapping[code],
            "원본 판정": description
        })

    if not rows:
        raise ValueError(
            "수면 단계 기록을 찾을 수 없습니다. "
            "확인된 파일이 올바른 Hypnogram EDF인지 확인해 주세요."
        )

    df = pd.DataFrame(rows).sort_values("시작(초)")
    df["종료(초)"] = df["시작(초)"] + df["지속시간(초)"]
    df["시작(시간)"] = df["시작(초)"] / 3600
    df["종료(시간)"] = df["종료(초)"] / 3600
    df["시간(분)"] = df["지속시간(초)"] / 60
    return df


# ----------------------------
# 공통 그래프 스타일
# ----------------------------
COLORS = {
    "깨어 있음": "#FFE0A3",
    "REM 수면": "#E78AF2",
    "얕은 수면": "#75C7FF",
    "깊은 수면": "#7777F5",
    "미분류": "#B7BDD7"
}

STAGE_ORDER = ["깊은 수면", "얕은 수면", "REM 수면", "깨어 있음", "미분류"]
STAGE_Y = {
    "깊은 수면": 0,
    "얕은 수면": 1,
    "REM 수면": 2,
    "깨어 있음": 3,
    "미분류": -1
}

def style_chart(fig, height=350):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,25,70,.25)",
        font=dict(color="#F4F3FF", family="Arial", size=12),
        margin=dict(l=15, r=15, t=55, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),
        title=dict(font=dict(size=17, color="#FFF4FF")),
        xaxis=dict(
            gridcolor="rgba(202,210,255,.13)",
            zerolinecolor="rgba(202,210,255,.15)"
        ),
        yaxis=dict(
            gridcolor="rgba(202,210,255,.13)",
            zerolinecolor="rgba(202,210,255,.15)"
        )
    )
    return fig


def make_hypnogram(df):
    fig = go.Figure()

    # 각 판정 구간을 굵은 수평선으로 표현
    for stage in STAGE_ORDER:
        part = df[df["수면 단계"] == stage]
        if part.empty:
            continue

        xs, ys = [], []
        for _, row in part.iterrows():
            xs.extend([row["시작(시간)"], row["종료(초)"] / 3600, None])
            ys.extend([STAGE_Y[stage], STAGE_Y[stage], None])

        fig.add_trace(go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            name=stage,
            line=dict(color=COLORS[stage], width=13),
            hoverinfo="skip"
        ))

    # 구간별 자세한 정보는 별도 점으로 표시
    fig.add_trace(go.Scatter(
        x=(df["시작(초)"] + df["지속시간(초)"] / 2) / 3600,
        y=df["수면 단계"].map(STAGE_Y),
        mode="markers",
        marker=dict(size=5, color="rgba(255,255,255,.01)"),
        customdata=df[["수면 단계", "시간(분)", "원본 판정"]].values,
        hovertemplate=(
            "경과 시간: %{x:.2f}시간<br>"
            "단계: %{customdata[0]}<br>"
            "지속 시간: %{customdata[1]:.1f}분<br>"
            "원본: %{customdata[2]}<extra></extra>"
        ),
        showlegend=False
    ))

    fig.update_yaxes(
        tickmode="array",
        tickvals=[-1, 0, 1, 2, 3],
        ticktext=["미분류", "깊은 수면", "얕은 수면", "REM 수면", "깨어 있음"],
        range=[-0.5, 3.5],
        title=""
    )
    fig.update_xaxes(title="기록 시작 후 경과 시간 (시간)")
    fig.update_layout(title="🌌 밤사이 수면 단계 변화")
    return style_chart(fig, 390)


# ----------------------------
# 페이지 상단 디자인
# ----------------------------
st.markdown("""
<div class="hero">
    <div class="hero-tag">✦ SLEEP-EDF RESEARCH DATA ✦</div>
    <h1>🌙 나의 수면 리듬 분석실</h1>
    <p>
        밤하늘 아래 펼쳐지는 수면의 흐름을 따라가 보세요.<br>
        실제 공개 수면 연구 데이터로 수면 단계와 분포를 분석합니다.
    </p>
</div>
""", unsafe_allow_html=True)

if not DATA_FILE.exists():
    st.error(
        f"'{DATA_FILE.name}' 파일을 찾지 못했습니다. "
        "main.py와 EDF 파일이 GitHub 저장소의 같은 폴더에 있는지 확인하세요."
    )
    st.stop()

try:
    df = load_data(str(DATA_FILE), DATA_FILE.stat().st_mtime)
except Exception as error:
    st.error("EDF 파일을 읽는 중 오류가 발생했습니다.")
    st.code(str(error))
    st.info(
        "requirements.txt에 mne가 포함되어 있는지, "
        "GitHub의 데이터 파일이 정상적으로 업로드되었는지 확인해 주세요."
    )
    st.stop()

# ----------------------------
# 통계 계산
# ----------------------------
summary = (
    df.groupby("수면 단계", as_index=False)["시간(분)"]
    .sum()
)
summary["비율(%)"] = summary["시간(분)"] / summary["시간(분)"].sum() * 100

def stage_minutes(stage):
    found = summary.loc[summary["수면 단계"] == stage, "시간(분)"]
    return float(found.iloc[0]) if not found.empty else 0.0

wake = stage_minutes("깨어 있음")
light = stage_minutes("얕은 수면")
deep = stage_minutes("깊은 수면")
rem = stage_minutes("REM 수면")
unknown = stage_minutes("미분류")
sleep_total = light + deep + rem
record_total = df["시간(분)"].sum()
sleep_efficiency = sleep_total / record_total * 100 if record_total else 0

# ----------------------------
# 상단 요약 카드
# ----------------------------
metrics = st.columns(4)
cards = [
    ("🕰️", "분석 기록 길이", f"{record_total / 60:.2f}시간", f"약 {record_total:.0f}분"),
    ("🛏️", "수면 단계 기록", f"{sleep_total / 60:.2f}시간", f"약 {sleep_total:.0f}분"),
    ("✨", "깨어 있음", f"{wake:.0f}분", "각성으로 판정된 구간"),
    ("🌙", "수면 구간 비율", f"{sleep_efficiency:.1f}%", "전체 기록 중 수면 단계")
]

for col, (emoji, label, value, note) in zip(metrics, cards):
    with col:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size:23px">{emoji}</div>
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """, unsafe_allow_html=True)

st.write("")

# ----------------------------
# 메뉴별 화면
# ----------------------------
if page in ["홈", "수면 단계 분석"]:
    left, right = st.columns([1.6, 1])

    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">✦ 1. 밤사이 수면 단계 변화</div>', unsafe_allow_html=True)
        st.caption("시간에 따라 각 수면 단계가 어떻게 변하는지 살펴봅니다.")
        st.plotly_chart(make_hypnogram(df), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">✧ 2. 수면 단계별 비율</div>', unsafe_allow_html=True)
        pie_df = summary[summary["수면 단계"] != "미분류"]
        fig_pie = px.pie(
            pie_df,
            names="수면 단계",
            values="시간(분)",
            hole=0.56,
            color="수면 단계",
            color_discrete_map=COLORS
        )
        fig_pie.update_traces(
            textposition="inside",
            textinfo="percent",
            marker=dict(line=dict(color="#1A2458", width=2)),
            hovertemplate="%{label}<br>%{value:.1f}분<br>%{percent}<extra></extra>"
        )
        fig_pie.update_layout(
            title="🌸 단계별 기록 분포",
            annotations=[dict(
                text=f"{sleep_total / 60:.1f}시간",
                x=0.5, y=0.5,
                font=dict(size=20, color="white"),
                showarrow=False
            )]
        )
        style_chart(fig_pie, 350)
        st.plotly_chart(fig_pie, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">🌙 3. 전반부와 후반부 비교</div>', unsafe_allow_html=True)
    st.caption("기록 전체를 시간상 절반으로 나누어 각 단계의 기록 시간을 비교합니다.")

    start = df["시작(초)"].min()
    end = df["종료(초)"].max()
    midpoint = (start + end) / 2

    # 중간 경계를 지나는 구간은 경계에서 분할하여 정확히 집계
    first_rows = []
    second_rows = []

    for _, row in df.iterrows():
        s = row["시작(초)"]
        e = row["종료(초)"]
        if s < midpoint:
            first_rows.append({
                "수면 단계": row["수면 단계"],
                "시간(분)": (min(e, midpoint) - s) / 60,
                "구간": "전반부"
            })
        if e > midpoint:
            second_rows.append({
                "수면 단계": row["수면 단계"],
                "시간(분)": (e - max(s, midpoint)) / 60,
                "구간": "후반부"
            })

    compare_df = pd.DataFrame(first_rows + second_rows)
    if not compare_df.empty:
        compare_df = compare_df.groupby(
            ["구간", "수면 단계"], as_index=False
        )["시간(분)"].sum()

        compare_fig = px.bar(
            compare_df,
            x="수면 단계",
            y="시간(분)",
            color="수면 단계",
            facet_col="구간",
            color_discrete_map=COLORS,
            category_orders={"수면 단계": STAGE_ORDER}
        )
        compare_fig.update_layout(
            title="🌷 전반부 · 후반부 수면 단계 기록",
            showlegend=False
        )
        compare_fig.update_xaxes(title="")
        style_chart(compare_fig, 340)
        st.plotly_chart(compare_fig, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">💫 4. 데이터에서 발견한 패턴</div>', unsafe_allow_html=True)

    st.markdown(
        f"- 얕은 수면은 **{light:.1f}분**, 깊은 수면은 **{deep:.1f}분**, "
        f"REM 수면은 **{rem:.1f}분**으로 기록되었습니다."
    )
    if sleep_total > 0:
        st.markdown(
            f"- 수면 단계로 판정된 시간 중 깊은 수면은 "
            f"**{deep / sleep_total * 100:.1f}%**, REM 수면은 "
            f"**{rem / sleep_total * 100:.1f}%**입니다."
        )
    st.markdown(
        "- 전반부와 후반부의 막대 높이를 비교하면 수면 단계별 기록 시간이 "
        "어떻게 달라지는지 확인할 수 있습니다."
    )
    st.info(
        "이 결과는 공개 연구 데이터의 한 기록을 요약한 것입니다. "
        "모든 사람에게 같은 수면 패턴이 나타난다는 뜻은 아닙니다."
    )
    st.markdown('</div>', unsafe_allow_html=True)

elif page == "통계 및 비교":
    st.subheader("📊 수면 단계 통계")
    display = summary.copy()
    display["시간(분)"] = display["시간(분)"].round(2)
    display["비율(%)"] = display["비율(%)"].round(2)
    st.dataframe(display, use_container_width=True, hide_index=True)

    fig = px.bar(
        summary,
        x="수면 단계",
        y="시간(분)",
        color="수면 단계",
        color_discrete_map=COLORS,
        title="단계별 기록 시간"
    )
    st.plotly_chart(style_chart(fig), use_container_width=True)

    st.download_button(
        "📥 분석 결과 CSV 다운로드",
        data=summary.to_csv(index=False).encode("utf-8-sig"),
        file_name="sleep_stage_summary.csv",
        mime="text/csv"
    )

elif page == "데이터 정보":
    st.subheader("📚 데이터와 분석 방법")
    st.markdown("""
    **데이터 출처:** Sleep-EDF Expanded 공개 수면 연구 데이터셋

    **분석 대상:** GitHub에 업로드한 `SC4001EC-Hypnogram.edf`

    **단계 분류**
    - W: 깨어 있음
    - 1·2: 얕은 수면으로 묶어 표시
    - 3·4: 깊은 수면으로 묶어 표시
    - R: REM 수면
    - 그 외 판정 불가 구간: 미분류

    **분석 방법**
    1. EDF 파일에서 전문가가 기록한 수면 단계 주석을 읽습니다.
    2. 각 단계의 지속시간을 합산합니다.
    3. 시간에 따른 변화, 단계별 비율, 전반부와 후반부를 비교합니다.

    이 프로그램은 원본 뇌파를 이용해 수면 단계를 새로 판별하지 않습니다.
    이미 판정된 수면 단계 주석을 분석합니다.
    """)

st.divider()
st.markdown(
    "<div style='text-align:center;color:#c7c9ed;font-size:12px'>"
    "🌙 나의 수면 리듬 분석실 · Sleep-EDF Research Data"
    "</div>",
    unsafe_allow_html=True
)
