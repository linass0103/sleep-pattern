
from pathlib import Path
import re
from datetime import time

import mne
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="나의 수면 리듬 분석실",
    page_icon="🌙",
    layout="wide"
)

DATA_FILE = Path(__file__).parent / "SC4001EC-Hypnogram.edf"

# ---------- 색상 ----------
COLORS = {
    "깨어 있음": "#FFE0A3",
    "REM 수면": "#E88CF2",
    "얕은 수면": "#78CBFF",
    "깊은 수면": "#8580FA",
    "미분류": "#BBC3DF",
}

STAGE_Y = {
    "깊은 수면": 0,
    "얕은 수면": 1,
    "REM 수면": 2,
    "깨어 있음": 3,
    "미분류": -1,
}

STAGE_ORDER = [
    "깊은 수면", "얕은 수면", "REM 수면", "깨어 있음", "미분류"
]

# ---------- 디자인 ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&display=swap');

.stApp {
    background:
        radial-gradient(ellipse at 82% 3%, rgba(174,151,255,.2), transparent 32%),
        radial-gradient(ellipse at 15% 18%, rgba(255,157,190,.12), transparent 32%),
        linear-gradient(160deg,#091332,#18265b 52%,#30265d 80%,#49366c);
    color: #f8f4ff;
    font-family: 'Gowun Dodum', sans-serif;
}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stSidebar"] {
    background:linear-gradient(180deg,#101b48,#1c2c61,#32265c);
    border-right:1px solid #6877b0;
}
h1,h2,h3 {color:#fff4ff !important;}
p,label {color:#e0e5ff;}
.hero {
    padding:30px;
    border-radius:24px;
    margin:5px 0 22px;
    border:1px solid rgba(220,211,255,.4);
    background:
      radial-gradient(circle at 83% 25%,#fff9e5 0%,#f5dcff 4%,
      #b8b6ff 8%,transparent 9%),
      linear-gradient(180deg,#111b48 0%,#49508d 52%,#d18bae 100%);
    box-shadow:0 12px 35px #080d2c55;
}
.hero h1 {font-size:clamp(27px,4vw,42px);margin:10px 0;}
.hero p {line-height:1.8;}
.panel {
    background:linear-gradient(145deg,#293b79d9,#172451ee);
    border:1px solid #8d9bdd66;
    border-radius:19px;
    padding:20px;
    margin-bottom:15px;
    box-shadow:0 8px 25px #060b2b25;
}
.metric {
    background:linear-gradient(140deg,#4559a5bb,#202e65ed);
    border:1px solid #b9c3ff66;
    border-radius:17px;
    padding:16px;
    min-height:125px;
}
.metric-name {font-size:13px;color:#dbe1ff;}
.metric-value {font-size:25px;font-weight:bold;margin:8px 0;color:white;}
.metric-note {font-size:12px;color:#c5d5ff;}
.stButton button {
    border-radius:12px;
    background:#4556a0;
    color:white;
    border:1px solid #aab6ff;
}
div[data-testid="stDataFrame"] {border-radius:12px;overflow:hidden;}
hr {border-color:#a6b2ff33;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(
        "<div style='text-align:center;font-size:48px'>🌙</div>",
        unsafe_allow_html=True
    )
    st.markdown("## 수면 리듬 분석실")
    page = st.radio(
        "분석 메뉴",
        [
            "전체 대시보드",
            "내 일주일 수면",
            "연구 데이터 심화 분석",
            "데이터와 과학 원리",
        ]
    )
    st.divider()
    st.caption("별빛 아래 살펴보는 나의 수면과 생체 리듬 ✦")

st.markdown("""
<div class="hero">
    <div style="font-size:12px;letter-spacing:2px">
        ✦ SLEEP RHYTHM LAB ✦
    </div>
    <h1>🌙 나의 수면 리듬 분석실</h1>
    <p>
    나의 일주일 수면 습관과 실제 수면 연구 데이터를 함께 분석해요.<br>
    수면 시간뿐 아니라 밤사이 수면 단계의 변화까지 탐구합니다.
    </p>
</div>
""", unsafe_allow_html=True)

# ---------- 내 일주일 수면 기록 ----------
days = ["월", "화", "수", "목", "금", "토", "일"]

if "weekly_sleep" not in st.session_state:
    st.session_state.weekly_sleep = pd.DataFrame({
        "요일": days,
        "취침 시각": [
            time(23, 30), time(23, 30), time(0, 0),
            time(23, 40), time(0, 0), time(1, 0), time(0, 0)
        ],
        "기상 시각": [
            time(7, 0), time(7, 0), time(7, 0),
            time(7, 0), time(7, 0), time(9, 0), time(9, 0)
        ]
    })

st.session_state.weekly_sleep["요일"] = days

def clock_minutes(value):
    return value.hour * 60 + value.minute

def calculate_weekly(df):
    result = df.copy()
    durations = []
    bed_mins = []
    wake_mins = []

    for _, row in result.iterrows():
        bed = clock_minutes(row["취침 시각"])
        wake = clock_minutes(row["기상 시각"])
        duration = (wake - bed) % (24 * 60)
        durations.append(duration / 60)
        bed_mins.append(bed)
        wake_mins.append(wake)

    result["수면 시간"] = durations
    result["취침 분"] = bed_mins
    result["기상 분"] = wake_mins
    return result

# ---------- 연구 데이터 읽기 ----------
@st.cache_data
def load_hypnogram(path, modified):
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
            "?": "미분류",
        }
        duration = float(ann["duration"])
        if duration <= 0:
            continue

        rows.append({
            "시작(초)": float(ann["onset"]),
            "지속시간(초)": duration,
            "수면 단계": mapping[code],
            "원본 판정": description,
        })

    if not rows:
        raise ValueError(
            "인식 가능한 수면 단계가 없습니다. "
            "Hypnogram 파일인지 확인해 주세요."
        )

    df = pd.DataFrame(rows).sort_values("시작(초)")
    df["종료(초)"] = df["시작(초)"] + df["지속시간(초)"]
    df["시간(분)"] = df["지속시간(초)"] / 60
    return df

research_df = None
research_error = None

if DATA_FILE.exists():
    try:
        research_df = load_hypnogram(
            str(DATA_FILE), DATA_FILE.stat().st_mtime
        )
    except Exception as error:
        research_error = str(error)

# ---------- 그래프 공통 스타일 ----------
def style_chart(fig, height=350):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,25,70,.3)",
        font=dict(color="#F4F3FF", family="Arial"),
        margin=dict(l=15, r=15, t=55, b=20),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="left", x=0
        )
    )
    fig.update_xaxes(gridcolor="rgba(202,210,255,.13)")
    fig.update_yaxes(gridcolor="rgba(202,210,255,.13)")
    return fig

def make_hypnogram(df):
    fig = go.Figure()

    for stage in STAGE_ORDER:
        part = df[df["수면 단계"] == stage]
        if part.empty:
            continue

        xs, ys = [], []
        for _, row in part.iterrows():
            xs.extend([
                row["시작(초)"] / 3600,
                row["종료(초)"] / 3600,
                None
            ])
            ys.extend([STAGE_Y[stage], STAGE_Y[stage], None])

        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines", name=stage,
            line=dict(color=COLORS[stage], width=13),
            hoverinfo="skip"
        ))

    fig.add_trace(go.Scatter(
        x=(df["시작(초)"] + df["지속시간(초)"] / 2) / 3600,
        y=df["수면 단계"].map(STAGE_Y),
        mode="markers",
        marker=dict(size=5, color="rgba(255,255,255,.01)"),
        customdata=df[["수면 단계", "시간(분)", "원본 판정"]].values,
        hovertemplate=(
            "경과 시간: %{x:.2f}시간<br>"
            "단계: %{customdata[0]}<br>"
            "지속시간: %{customdata[1]:.1f}분<br>"
            "원본 판정: %{customdata[2]}<extra></extra>"
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

def make_stage_summary(df):
    summary = df.groupby("수면 단계", as_index=False)["시간(분)"].sum()
    total = summary["시간(분)"].sum()
    summary["비율(%)"] = summary["시간(분)"] / total * 100 if total else 0
    return summary

def stage_value(summary, name):
    found = summary.loc[summary["수면 단계"] == name, "시간(분)"]
    return float(found.iloc[0]) if not found.empty else 0.0

# ---------- 내 수면 분석 ----------
if page in ["전체 대시보드", "내 일주일 수면"]:
    st.markdown("## 🛏️ 내 일주일 수면 패턴")
    st.write("각 요일의 실제 취침·기상 시각을 입력한 뒤 분석 버튼을 눌러 줘.")

    edited = st.data_editor(
        st.session_state.weekly_sleep,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=["요일"],
        column_config={
            "요일": st.column_config.TextColumn("요일"),
            "취침 시각": st.column_config.TimeColumn(
                "취침 시각", format="HH:mm", step=300
            ),
            "기상 시각": st.column_config.TimeColumn(
                "기상 시각", format="HH:mm", step=300
            ),
        },
        key="weekly_editor"
    )

    if st.button("🌙 일주일 수면 분석하기", type="primary"):
        st.session_state.weekly_sleep = edited.copy()
        st.session_state.weekly_result = calculate_weekly(edited)

    if "weekly_result" not in st.session_state:
        st.session_state.weekly_result = calculate_weekly(
            st.session_state.weekly_sleep
        )

    weekly = st.session_state.weekly_result.copy()
    average = weekly["수면 시간"].mean()
    weekday = weekly.iloc[:5]["수면 시간"].mean()
    weekend = weekly.iloc[5:]["수면 시간"].mean()
    difference = weekend - weekday
    bedtime_std = weekly["취침 분"].std()

    a, b, c = st.columns(3)
    with a:
        st.markdown(f"""
        <div class="metric">
        <div class="metric-name">🌙 주간 평균 수면</div>
        <div class="metric-value">{average:.1f}시간</div>
        <div class="metric-note">하루 평균 기록 시간</div>
        </div>
        """, unsafe_allow_html=True)
    with b:
        st.markdown(f"""
        <div class="metric">
        <div class="metric-name">🌷 주말-평일 차이</div>
        <div class="metric-value">{difference:+.1f}시간</div>
        <div class="metric-note">주말 평균에서 평일 평균을 뺀 값</div>
        </div>
        """, unsafe_allow_html=True)
    with c:
        st.markdown(f"""
        <div class="metric">
        <div class="metric-name">✨ 취침 시각 변동</div>
        <div class="metric-value">{bedtime_std / 60:.1f}시간</div>
        <div class="metric-note">취침 시각의 표준편차(단순 시각 기준)</div>
        </div>
        """, unsafe_allow_html=True)

    left, right = st.columns([1.5, 1])

    with left:
        fig = px.bar(
            weekly,
            x="요일",
            y="수면 시간",
            color="수면 시간",
            color_continuous_scale=["#7777F5", "#78CBFF", "#E88CF2"],
            title="🌠 요일별 수면 시간"
        )
        fig.add_hline(
            y=8, line_dash="dash", line_color="#FFE0A3",
            annotation_text="8시간 참고선"
        )
        fig.update_yaxes(title="수면 시간 (시간)")
        fig.update_xaxes(title="")
        st.plotly_chart(style_chart(fig), use_container_width=True)

    with right:
        bedtime_chart = weekly.copy()
        bedtime_chart["취침 시각(시)"] = bedtime_chart["취침 분"] / 60
        fig_bed = px.line(
            bedtime_chart,
            x="요일",
            y="취침 시각(시)",
            markers=True,
            title="🌙 취침 시각 변화",
        )
        fig_bed.update_traces(
            line_color="#E88CF2",
            marker=dict(size=10, color="#FFE0A3")
        )
        fig_bed.update_yaxes(
            title="시계 시각 (시간)",
            tickmode="array",
            tickvals=[0, 3, 6, 9, 12, 15, 18, 21, 24],
            ticktext=["00시", "03시", "06시", "09시", "12시",
                      "15시", "18시", "21시", "24시"]
        )
        st.plotly_chart(style_chart(fig_bed), use_container_width=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 🔎 나의 수면 패턴 해석")

    if difference >= 1:
        st.write(
            f"주말에는 평일보다 평균 {difference:.1f}시간 더 오래 자는 것으로 입력했어. "
            "평일과 주말의 수면 시간 차이가 큰지 살펴볼 만해."
        )
    elif difference <= -1:
        st.write(
            f"주말 수면 시간이 평일보다 평균 {abs(difference):.1f}시간 짧아. "
            "주말 활동이나 기상 시각을 다시 확인해 볼 수 있어."
        )
    else:
        st.write(
            f"평일과 주말의 평균 수면 시간 차이는 {abs(difference):.1f}시간이야. "
            "시간 차이 외에도 취침 시각과 기상 시각의 규칙성을 살펴보자."
        )

    if bedtime_std >= 90:
        st.write("취침 시각의 요일별 차이가 큰 편으로 나타나. 일정한 수면 시간대를 유지하는 것이 가능한지 살펴봐.")
    else:
        st.write("입력한 취침 시각은 비교적 비슷한 편이야. 기상 시각도 함께 확인해 보자.")

    st.caption(
        "해석은 네가 입력한 시간만을 바탕으로 해. "
        "이 기록만으로 실제 REM 수면이나 깊은 수면의 시간을 알 수는 없어."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if page == "전체 대시보드":
        st.markdown("### ✦ 연구 데이터와 함께 보기")
        st.write(
            "내 수면 시간 기록과 연구 참여자의 수면 단계 구조를 "
            "서로 다른 자료로 분석해 볼 수 있어."
        )

# ---------- 연구 데이터 심화 분석 ----------
if page in ["전체 대시보드", "연구 데이터 심화 분석"]:
    st.divider()
    st.markdown("## 🔬 공개 연구 데이터 심화 분석")

    if research_df is None:
        st.warning(
            f"연구 데이터 파일을 읽을 수 없어. 저장소에 "
            f"`{DATA_FILE.name}`이 있는지 확인해 줘."
        )
        if research_error:
            st.code(research_error)
    else:
        summary = make_stage_summary(research_df)
        wake = stage_value(summary, "깨어 있음")
        light = stage_value(summary, "얕은 수면")
        deep = stage_value(summary, "깊은 수면")
        rem = stage_value(summary, "REM 수면")
        sleep_total = light + deep + rem
        record_total = research_df["시간(분)"].sum()

        st.success("Hypnogram 파일을 읽었습니다.")

        a, b, c = st.columns(3)
        a.metric("연구 기록 길이", f"{record_total / 60:.2f}시간")
        b.metric("수면 단계 판정 시간", f"{sleep_total:.0f}분")
        c.metric("REM 수면 기록", f"{rem:.0f}분")

        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### 🌌 1. 밤사이 수면 단계 변화")
        st.plotly_chart(
            make_hypnogram(research_df),
            use_container_width=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

        left, right = st.columns(2)
        with left:
            st.markdown('<div class="panel">', unsafe_allow_html=True)
            st.markdown("### 🌸 2. 수면 단계별 비율")
            pie_df = summary[summary["수면 단계"] != "미분류"]
            fig = px.pie(
                pie_df,
                names="수면 단계",
                values="시간(분)",
                hole=0.45,
                color="수면 단계",
                color_discrete_map=COLORS
            )
            fig.update_traces(
                textposition="inside",
                textinfo="percent+label"
            )
            st.plotly_chart(style_chart(fig, 330), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with right:
            st.markdown('<div class="panel">', unsafe_allow_html=True)
            st.markdown("### ✨ 3. 전반부와 후반부 비교")

            start = research_df["시작(초)"].min()
            end = research_df["종료(초)"].max()
            midpoint = (start + end) / 2
            parts = []

            # 중간 경계를 지나는 구간을 나누어 정확히 집계
            for _, row in research_df.iterrows():
                s = row["시작(초)"]
                e = row["종료(초)"]
                if s < midpoint:
                    parts.append({
                        "구간": "전반부",
                        "수면 단계": row["수면 단계"],
                        "시간(분)": (min(e, midpoint) - s) / 60
                    })
                if e > midpoint:
                    parts.append({
                        "구간": "후반부",
                        "수면 단계": row["수면 단계"],
                        "시간(분)": (e - max(s, midpoint)) / 60
                    })

            comp = pd.DataFrame(parts)
            comp = comp.groupby(
                ["구간", "수면 단계"], as_index=False
            )["시간(분)"].sum()

            fig = px.bar(
                comp,
                x="수면 단계",
                y="시간(분)",
                color="수면 단계",
                facet_col="구간",
                color_discrete_map=COLORS,
                category_orders={"수면 단계": STAGE_ORDER}
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(style_chart(fig, 330), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### 🧠 4. 과학적 해석")

        if sleep_total > 0:
            st.write(
                f"- 판정된 수면 단계 중 깊은 수면은 "
                f"{deep / sleep_total * 100:.1f}%, REM 수면은 "
                f"{rem / sleep_total * 100:.1f}%를 차지해."
            )
        st.write(
            "- 전반부와 후반부의 막대 높이를 비교하면 "
            "시간대에 따른 수면 구조의 차이를 확인할 수 있어."
        )
        st.write(
            "- 이 결과는 한 연구 기록에 대한 분석이므로, "
            "다른 사람이나 모든 수면에 그대로 적용할 수는 없어."
        )
        st.info(
            "내 일주일 수면 기록은 취침·기상 시각을 분석하고, "
            "연구 데이터는 전문가가 판정한 수면 단계를 분석해. "
            "두 자료는 측정 대상과 방법이 다르므로 내 실제 수면 단계로 "
            "해석하면 안 돼."
        )

        display = summary.copy()
        display["시간(분)"] = display["시간(분)"].round(1)
        display["비율(%)"] = display["비율(%)"].round(1)
        st.dataframe(display, hide_index=True, use_container_width=True)

        st.download_button(
            "📥 연구 데이터 통계 CSV 다운로드",
            data=display.to_csv(index=False).encode("utf-8-sig"),
            file_name="sleep_stage_analysis.csv",
            mime="text/csv"
        )
        st.markdown('</div>', unsafe_allow_html=True)

# ---------- 데이터 정보 ----------
if page == "데이터와 과학 원리":
    st.markdown("## 📚 데이터와 과학 원리")
    st.markdown("""
    <div class="panel">
    <h3>🌙 두 종류의 자료를 분석하는 이유</h3>
    <p><b>내 일주일 기록</b>은 취침 시각, 기상 시각, 수면 시간의
    규칙성을 보여 줍니다.</p>
    <p><b>공개 연구 데이터</b>는 전문가가 판정한 수면 단계를 이용해
    얕은 수면, 깊은 수면, REM 수면의 시간대별 변화를 보여 줍니다.</p>
    <p><b>심화 탐구 질문:</b> 수면 시간만으로 수면 구조를 충분히 설명할 수 있을까요?</p>
    <p>수면 시간은 중요한 지표이지만, 수면 단계와 그 변화까지 알아야
    수면 구조를 더 자세히 이해할 수 있습니다.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 수면 단계 분류")
    st.write("- W: 깨어 있음")
    st.write("- 1·2: 이 프로그램에서는 얕은 수면으로 묶어 표시")
    st.write("- 3·4: 깊은 수면으로 묶어 표시")
    st.write("- R: REM 수면")

    st.markdown("### 참고 자료")
    st.markdown(
        "[Sleep-EDF Expanded 공개 연구 데이터](https://physionet.org/content/sleep-edfx/1.0.0/)"
    )
    st.caption(
        "이 앱은 수면을 진단하지 않으며, "
        "공개 연구 데이터와 사용자가 입력한 시간을 교육 목적으로 분석합니다."
    )

st.divider()
st.markdown(
    "<div style='text-align:center;color:#cbd2f5;font-size:12px'>"
    "🌙 나의 수면 리듬 분석실 · 공개 연구 데이터 기반 탐구"
    "</div>",
    unsafe_allow_html=True
)
