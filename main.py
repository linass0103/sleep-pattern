
from pathlib import Path
import re
from datetime import time

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import mne

st.set_page_config(
    page_title="나의 수면 리듬 분석실",
    page_icon="🌙",
    layout="wide"
)

DATA_FILE = Path(__file__).parent / "SC4001EC-Hypnogram.edf"

# =========================
# 디자인
# =========================
COLORS = {
    "깨어 있음": "#FFE0A3",
    "REM 수면": "#E88CF2",
    "얕은 수면": "#78CBFF",
    "깊은 수면": "#8580FA",
    "미분류": "#BBC3DF",
}

STAGE_ORDER = ["깊은 수면", "얕은 수면", "REM 수면", "깨어 있음", "미분류"]
STAGE_Y = {
    "깊은 수면": 0,
    "얕은 수면": 1,
    "REM 수면": 2,
    "깨어 있음": 3,
    "미분류": -1,
}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&display=swap');

.stApp {
    background:
      radial-gradient(ellipse at 80% 5%,rgba(180,155,255,.20),transparent 34%),
      radial-gradient(ellipse at 15% 20%,rgba(255,157,190,.12),transparent 32%),
      linear-gradient(160deg,#091332,#18265b 52%,#30265d 80%,#49366c);
    color:#f8f4ff;
    font-family:'Gowun Dodum',sans-serif;
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
    min-height:120px;
}
.metric-name {font-size:13px;color:#dbe1ff;}
.metric-value {font-size:24px;font-weight:bold;margin:8px 0;color:white;}
.metric-note {font-size:12px;color:#c5d5ff;}
.stButton button {
    border-radius:12px;
    background:#4556a0;
    color:white;
    border:1px solid #aab6ff;
}
hr {border-color:#a6b2ff33;}
</style>
""", unsafe_allow_html=True)

# =========================
# 사이드바
# =========================
with st.sidebar:
    st.markdown(
        "<div style='text-align:center;font-size:48px'>🌙</div>",
        unsafe_allow_html=True
    )
    st.markdown("## 수면 리듬 분석실")
    page = st.radio(
        "메뉴",
        [
            "전체 대시보드",
            "내 일주일 수면",
            "연구 데이터 심화 분석",
            "데이터와 과학 원리"
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

# =========================
# 시간 입력 도구
# =========================
DAYS = ["월", "화", "수", "목", "금", "토", "일"]
HOURS = list(range(5, 24)) + list(range(0, 5))
MINUTES = list(range(60))

def hour_label(h):
    if h < 12:
        return f"오전 {12 if h == 0 else h}시"
    return f"오후 {12 if h == 12 else h - 12}시"

def clock_minutes(h, m):
    return h * 60 + m

def duration_label(hours):
    mins = round(hours * 60)
    return f"{mins // 60}시간 {mins % 60}분"

if "sleep_inputs" not in st.session_state:
    defaults = [
        (23, 30, 7, 0),
        (23, 30, 7, 0),
        (0, 0, 7, 0),
        (23, 40, 7, 0),
        (0, 0, 7, 0),
        (1, 0, 9, 0),
        (0, 0, 9, 0),
    ]
    st.session_state.sleep_inputs = {
        day: {
            "bed_hour": v[0], "bed_minute": v[1],
            "wake_hour": v[2], "wake_minute": v[3]
        }
        for day, v in zip(DAYS, defaults)
    }

def calculate_weekly(inputs):
    rows = []
    for day in DAYS:
        v = inputs[day]
        bed = clock_minutes(v["bed_hour"], v["bed_minute"])
        wake = clock_minutes(v["wake_hour"], v["wake_minute"])
        sleep = (wake - bed) % 1440

        # 취침 시각을 오전 5시 기준으로 펼쳐 자정 전후를 보정
        bed_shift = bed if bed >= 300 else bed + 1440
        wake_shift = wake if wake >= 300 else wake + 1440

        rows.append({
            "요일": day,
            "취침 시각": f"{v['bed_hour']:02d}:{v['bed_minute']:02d}",
            "기상 시각": f"{v['wake_hour']:02d}:{v['wake_minute']:02d}",
            "취침 분": bed,
            "기상 분": wake,
            "취침 비교값": bed_shift,
            "기상 비교값": wake_shift,
            "수면 시간": sleep / 60,
        })
    return pd.DataFrame(rows)

# =========================
# 연구 EDF 데이터 읽기
# =========================
@st.cache_data
def load_hypnogram(path, modified):
    annotations = mne.read_annotations(path)
    rows = []

    for ann in annotations:
        desc = str(ann["description"])
        match = re.search(
            r"Sleep stage\s+([W1234R?])",
            desc,
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

        seconds = float(ann["duration"])
        if seconds <= 0:
            continue

        rows.append({
            "시작(초)": float(ann["onset"]),
            "지속시간(초)": seconds,
            "수면 단계": mapping[code],
            "원본 판정": desc,
        })

    if not rows:
        raise ValueError(
            "수면 단계 기록을 찾지 못했습니다. "
            "Hypnogram EDF 파일인지 확인해 주세요."
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
    except Exception as e:
        research_error = str(e)

# =========================
# 그래프 함수
# =========================
def style_chart(fig, height=350):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,25,70,.3)",
        font=dict(color="#F4F3FF", family="Arial", size=12),
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

def stage_summary(df):
    result = df.groupby("수면 단계", as_index=False)["시간(분)"].sum()
    total = result["시간(분)"].sum()
    result["비율(%)"] = result["시간(분)"] / total * 100 if total else 0
    return result

def stage_minutes(summary, stage):
    values = summary.loc[summary["수면 단계"] == stage, "시간(분)"]
    return float(values.iloc[0]) if not values.empty else 0.0

# =========================
# 개인 수면 분석 화면
# =========================
def render_personal_sleep():
    st.markdown("## 🛏️ 내 일주일 수면 패턴")
    st.write("요일별 취침·기상 시각을 각각 선택해 줘.")

    st.caption(
        "시간은 오전 5시부터 다음 날 오전 4시까지, "
        "분은 00~59분 중에서 고를 수 있어."
    )

    for day in DAYS:
        with st.container(border=True):
            st.markdown(f"### {day}요일")
            left, right = st.columns(2)

            with left:
                st.markdown("🌙 취침 시각")
                hcol, mcol = st.columns(2)
                with hcol:
                    st.selectbox(
                        "취침 시간",
                        HOURS,
                        format_func=hour_label,
                        key=f"{day}_bed_h",
                        index=HOURS.index(
                            st.session_state.sleep_inputs[day]["bed_hour"]
                        )
                    )
                with mcol:
                    st.selectbox(
                        "취침 분",
                        MINUTES,
                        format_func=lambda x: f"{x:02d}분",
                        key=f"{day}_bed_m",
                        index=st.session_state.sleep_inputs[day]["bed_minute"]
                    )

            with right:
                st.markdown("☀️ 기상 시각")
                hcol, mcol = st.columns(2)
                with hcol:
                    st.selectbox(
                        "기상 시간",
                        HOURS,
                        format_func=hour_label,
                        key=f"{day}_wake_h",
                        index=HOURS.index(
                            st.session_state.sleep_inputs[day]["wake_hour"]
                        )
                    )
                with mcol:
                    st.selectbox(
                        "기상 분",
                        MINUTES,
                        format_func=lambda x: f"{x:02d}분",
                        key=f"{day}_wake_m",
                        index=st.session_state.sleep_inputs[day]["wake_minute"]
                    )

    if st.button("🌙 일주일 수면 분석하기", type="primary"):
        for day in DAYS:
            st.session_state.sleep_inputs[day] = {
                "bed_hour": st.session_state[f"{day}_bed_h"],
                "bed_minute": st.session_state[f"{day}_bed_m"],
                "wake_hour": st.session_state[f"{day}_wake_h"],
                "wake_minute": st.session_state[f"{day}_wake_m"],
            }
        st.session_state.weekly_result = calculate_weekly(
            st.session_state.sleep_inputs
        )
        st.session_state.analysis_ready = True

    if "weekly_result" not in st.session_state:
        st.session_state.weekly_result = calculate_weekly(
            st.session_state.sleep_inputs
        )

    # 사용자가 선택한 최신 시각을 즉시 반영
    latest_inputs = {}
    for day in DAYS:
        latest_inputs[day] = {
            "bed_hour": st.session_state.get(
                f"{day}_bed_h",
                st.session_state.sleep_inputs[day]["bed_hour"]
            ),
            "bed_minute": st.session_state.get(
                f"{day}_bed_m",
                st.session_state.sleep_inputs[day]["bed_minute"]
            ),
            "wake_hour": st.session_state.get(
                f"{day}_wake_h",
                st.session_state.sleep_inputs[day]["wake_hour"]
            ),
            "wake_minute": st.session_state.get(
                f"{day}_wake_m",
                st.session_state.sleep_inputs[day]["wake_minute"]
            ),
        }

    weekly = calculate_weekly(latest_inputs)

    if not st.session_state.get("analysis_ready", False):
        st.info("시간을 선택한 뒤 분석 버튼을 누르면 상세 분석을 확인할 수 있어.")
        return

    avg = weekly["수면 시간"].mean()
    weekday_avg = weekly.iloc[:5]["수면 시간"].mean()
    weekend_avg = weekly.iloc[5:]["수면 시간"].mean()
    weekend_diff = weekend_avg - weekday_avg

    # 요일 순서대로 시각의 자정 경계 보정
    bed_values = weekly["취침 비교값"].tolist()
    wake_values = weekly["기상 비교값"].tolist()
    bed_variation = pd.Series(bed_values).std()
    wake_variation = pd.Series(wake_values).std()

    st.session_state.weekly_result = weekly

    st.markdown("### ✨ 핵심 요약")
    cols = st.columns(4)
    metrics = [
        ("🌙 하루 평균 수면", duration_label(avg)),
        ("📚 평일 평균", duration_label(weekday_avg)),
        ("🌷 주말 평균", duration_label(weekend_avg)),
        ("↕️ 주말-평일 차이", f"{weekend_diff:+.1f}시간"),
    ]

    for col, (name, value) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="metric">
                <div class="metric-name">{name}</div>
                <div class="metric-value">{value}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 🌌 1. 요일별 수면 시간")
    fig = px.bar(
        weekly, x="요일", y="수면 시간",
        color="수면 시간",
        color_continuous_scale=["#8580FA", "#78CBFF", "#E88CF2"],
        hover_data=["취침 시각", "기상 시각"],
        title="요일별 수면 시간과 권장 범위"
    )
    fig.add_hline(
        y=8, line_dash="dash", line_color="#FFE0A3",
        annotation_text="8시간"
    )
    fig.add_hline(
        y=10, line_dash="dot", line_color="#8FE6DB",
        annotation_text="10시간"
    )
    fig.update_yaxes(title="수면 시간 (시간)")
    fig.update_xaxes(title="")
    st.plotly_chart(style_chart(fig, 350), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 🌙 2. 요일별 상세 기록")
    table = weekly[["요일", "취침 시각", "기상 시각", "수면 시간"]].copy()
    table["수면 시간"] = table["수면 시간"].apply(duration_label)
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 수면 시간 부족량
    weekly["8시간 기준 부족"] = (8 - weekly["수면 시간"]).clip(lower=0)
    weekly["10시간 기준 초과"] = (weekly["수면 시간"] - 10).clip(lower=0)
    short = weekly[weekly["수면 시간"] < 8]
    long = weekly[weekly["수면 시간"] > 10]

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 🧠 3. 권장 수면 시간과 비교")
    st.write(
        "13~17세 청소년은 일반적으로 하루 8~10시간의 수면이 권장돼. "
        "이는 개인별 필요량을 확정하는 기준이 아니라 참고 범위야."
    )

    if not short.empty:
        for _, row in short.iterrows():
            st.write(
                f"- **{row['요일']}요일:** {duration_label(row['수면 시간'])}. "
                f"8시간 기준으로 약 {round(row['8시간 기준 부족']*60)}분 부족해."
            )
    else:
        st.success("입력한 모든 요일이 8시간 이상이야.")

    if not long.empty:
        for _, row in long.iterrows():
            st.write(
                f"- **{row['요일']}요일:** {duration_label(row['수면 시간'])}. "
                "10시간을 초과한 기록이야."
            )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 🔍 4. 피로를 느낄 수 있는 이유")

    if avg < 8:
        st.write(
            f"- 일주일 평균이 {duration_label(avg)}로 8시간보다 짧아. "
            "수면 시간이 부족하면 낮 동안 졸림이나 집중력 저하를 경험할 가능성이 있어."
        )
    else:
        st.write(
            f"- 일주일 평균은 {duration_label(avg)}야. "
            "평균이 권장 범위에 있더라도 수면의 질, 스트레스, 규칙성 등에 따라 피곤할 수 있어."
        )

    if abs(weekend_diff) >= 1:
        st.write(
            f"- 주말과 평일의 평균 수면 시간이 {abs(weekend_diff):.1f}시간 차이 나. "
            "차이가 크면 생활 시간표가 달라질 수 있고 생체 리듬에 영향을 줄 가능성이 있어."
        )
    else:
        st.write(
            f"- 주말과 평일의 평균 수면 시간 차이는 {abs(weekend_diff):.1f}시간이야. "
            "수면 시간 차이 외에도 기상 시각의 규칙성을 살펴보면 좋아."
        )

    if bed_variation >= 90:
        st.write(
            "- 취침 시각이 요일마다 크게 달라지는 편이야. "
            "가능하다면 취침·기상 시각을 일정하게 유지할 방법을 찾아봐."
        )
    if wake_variation >= 90:
        st.write(
            "- 기상 시각 변동도 큰 편이야. "
            "기상 시각이 자주 바뀌면 일정한 생활 리듬을 만들기 어려울 수 있어."
        )

    st.caption(
        "이 해석은 입력한 수면 시간에서 추정한 가능성이야. "
        "실제 피로 원인을 확정하거나 질병을 진단하지는 않아."
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # 요일별 개선 제안
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 🌷 5. 요일별 수면 계획 제안")

    st.write(
        "아래는 기상 시각을 유지한다고 가정했을 때, "
        "8시간 또는 9시간 수면을 확보하기 위한 취침 시각이야."
    )

    plans = []
    for _, row in weekly.iterrows():
        wake = int(row["기상 분"])
        target8 = (wake - 8 * 60) % 1440
        target9 = (wake - 9 * 60) % 1440

        def fmt_clock(mins):
            h, m = divmod(int(mins), 60)
            return f"{h:02d}:{m:02d}"

        plans.append({
            "요일": row["요일"],
            "현재 수면": duration_label(row["수면 시간"]),
            "현재 취침": row["취침 시각"],
            "기상": row["기상 시각"],
            "8시간 확보 취침": fmt_clock(target8),
            "9시간 확보 취침": fmt_clock(target9),
        })

    st.dataframe(
        pd.DataFrame(plans),
        use_container_width=True,
        hide_index=True
    )

    st.write(
        "예를 들어 평일 기상 시각이 오전 7시라면, "
        "8시간을 확보하려면 전날 밤 11시, "
        "9시간을 확보하려면 밤 10시에 자는 일정이 돼."
    )
    st.caption(
        "실제로 잠드는 데 걸리는 시간은 반영하지 않은 단순 계산이야. "
        "가능한 범위에서 수면 시간을 충분히 확보하는 데 참고해."
    )
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 연구 데이터 분석
# =========================
def render_research():
    st.markdown("## 🔬 공개 연구 데이터 심화 분석")

    if research_df is None:
        st.warning(
            f"'{DATA_FILE.name}'을 읽지 못했어. "
            "main.py와 EDF 파일이 같은 폴더에 있는지 확인해 줘."
        )
        if research_error:
            st.code(research_error)
        return

    summary = stage_summary(research_df)
    wake = stage_minutes(summary, "깨어 있음")
    light = stage_minutes(summary, "얕은 수면")
    deep = stage_minutes(summary, "깊은 수면")
    rem = stage_minutes(summary, "REM 수면")
    total = research_df["시간(분)"].sum()
    sleep_total = light + deep + rem

    st.success("Hypnogram 연구 데이터를 불러왔어.")

    c1, c2, c3 = st.columns(3)
    c1.metric("기록 길이", f"{total/60:.2f}시간")
    c2.metric("수면 단계 판정", f"{sleep_total:.0f}분")
    c3.metric("REM 수면", f"{rem:.0f}분")

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 🌌 1. 밤사이 수면 단계 변화")
    st.plotly_chart(make_hypnogram(research_df), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### 🌸 2. 단계별 비율")
        pie_data = summary[summary["수면 단계"] != "미분류"]
        fig = px.pie(
            pie_data, names="수면 단계", values="시간(분)",
            hole=.48, color="수면 단계",
            color_discrete_map=COLORS
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(style_chart(fig, 330), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### ✨ 3. 전반부와 후반부")

        start = research_df["시작(초)"].min()
        end = research_df["종료(초)"].max()
        midpoint = (start + end) / 2
        pieces = []

        for _, row in research_df.iterrows():
            s, e = row["시작(초)"], row["종료(초)"]
            if s < midpoint:
                pieces.append({
                    "구간": "전반부",
                    "수면 단계": row["수면 단계"],
                    "시간(분)": (min(e, midpoint) - s) / 60
                })
            if e > midpoint:
                pieces.append({
                    "구간": "후반부",
                    "수면 단계": row["수면 단계"],
                    "시간(분)": (e - max(s, midpoint)) / 60
                })

        comp = pd.DataFrame(pieces)
        comp = comp.groupby(
            ["구간", "수면 단계"], as_index=False
        )["시간(분)"].sum()

        fig = px.bar(
            comp, x="수면 단계", y="시간(분)",
            color="수면 단계", facet_col="구간",
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
            f"- 판정된 수면 단계 중 깊은 수면은 {deep/sleep_total*100:.1f}%, "
            f"REM 수면은 {rem/sleep_total*100:.1f}%야."
        )

    st.write(
        "- 전반부와 후반부의 단계 분포를 비교하면 수면 구조가 "
        "시간에 따라 어떻게 달라지는지 살펴볼 수 있어."
    )
    st.info(
        "연구 데이터는 전문가가 판정한 수면 단계 기록이야. "
        "내 취침·기상 시각만으로 내 REM 수면이나 깊은 수면 시간을 "
        "알아낼 수는 없어."
    )

    shown = summary.copy()
    shown["시간(분)"] = shown["시간(분)"].round(1)
    shown["비율(%)"] = shown["비율(%)"].round(1)
    st.dataframe(shown, use_container_width=True, hide_index=True)

    st.download_button(
        "📥 연구 데이터 통계 다운로드",
        data=shown.to_csv(index=False).encode("utf-8-sig"),
        file_name="sleep_stage_analysis.csv",
        mime="text/csv"
    )
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 페이지 표시
# =========================
if page in ["전체 대시보드", "내 일주일 수면"]:
    render_personal_sleep()

if page in ["전체 대시보드", "연구 데이터 심화 분석"]:
    st.divider()
    render_research()

if page == "데이터와 과학 원리":
    st.markdown("## 📚 데이터와 과학 원리")
    st.markdown("""
    <div class="panel">
    <h3>수면 시간만으로 수면 구조를 알 수 있을까?</h3>
    <p>취침·기상 시각은 전체 수면 시간을 추정하는 데 도움이 됩니다.</p>
    <p>그러나 얕은 수면, 깊은 수면, REM 수면을 구분하려면
    뇌파 등 수면 측정 신호를 바탕으로 한 단계 판정이 필요합니다.</p>
    <p>이 프로젝트는 개인의 수면 시간 분석과 공개 연구 데이터의
    수면 단계 분석을 함께 사용해 두 자료의 차이를 탐구합니다.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 단계 분류")
    st.write("- W: 깨어 있음")
    st.write("- 1·2: 얕은 수면으로 묶어 표시")
    st.write("- 3·4: 깊은 수면으로 묶어 표시")
    st.write("- R: REM 수면")

    st.markdown(
        "[Sleep-EDF Expanded 공개 데이터 출처](https://physionet.org/content/sleep-edfx/1.0.0/)"
    )
    st.markdown(
        "[CDC 청소년 수면 권장 정보](https://www.cdc.gov/sleep/about/index.html)"
    )

st.divider()
st.markdown(
    "<div style='text-align:center;color:#cbd2f5;font-size:12px'>"
    "🌙 나의 수면 리듬 분석실 · Sleep Rhythm Lab"
    "</div>",
    unsafe_allow_html=True
)
