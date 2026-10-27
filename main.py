
import streamlit as st
import pandas as pd
from datetime import date, time, datetime, timedelta

# ------------------------------
# 1. 앱 기본 설정
# ------------------------------
st.set_page_config(
    page_title="나의 수면 리듬 분석실",
    page_icon="🌙",
    layout="wide"
)

st.title("🌙 나의 수면 리듬 분석실")
st.write("일주일 수면 기록을 바탕으로 나의 수면 패턴을 분석해 보세요!")
st.caption("수면 시간 기록은 실제 렘수면이나 깊은 수면을 직접 측정하지 않습니다.")

# ------------------------------
# 2. 수면 시간 계산 함수
# ------------------------------
def calculate_sleep(bed, wake):
    """취침 시간과 기상 시간으로 수면 시간을 계산합니다."""
    bed_minutes = bed.hour * 60 + bed.minute
    wake_minutes = wake.hour * 60 + wake.minute

    # 기상 시간이 취침 시간보다 이르면 다음 날 일어난 것으로 계산합니다.
    if wake_minutes <= bed_minutes:
        wake_minutes += 24 * 60

    return wake_minutes - bed_minutes


def format_sleep(minutes):
    """분 단위 시간을 '몇 시간 몇 분'으로 표시합니다."""
    return f"{minutes // 60}시간 {minutes % 60}분"


def parse_time(value):
    """문자열을 시간으로 바꿉니다. 예: 07:50"""
    return datetime.strptime(str(value).strip(), "%H:%M").time()


# ------------------------------
# 3. 오늘의 수면 기록
# ------------------------------
st.header("1. 오늘의 수면 기록")

col1, col2, col3 = st.columns(3)

with col1:
    sleep_date = st.date_input(
        "잠든 날짜",
        value=date.today() - timedelta(days=1)
    )

with col2:
    today_bed = st.time_input(
        "잠든 시간",
        value=time(0, 30),
        step=300
    )

with col3:
    today_wake = st.time_input(
        "일어난 시간",
        value=time(7, 30),
        step=300
    )

today_minutes = calculate_sleep(today_bed, today_wake)

st.metric("오늘의 수면 시간", format_sleep(today_minutes))

# ------------------------------
# 4. 일주일 수면 기록 입력
# ------------------------------
st.header("2. 일주일 수면 기록")
st.write("월요일부터 일요일까지 취침 시간과 기상 시간을 입력하세요.")

days = ["월", "화", "수", "목", "금", "토", "일"]

# 처음 화면에 표시할 예시 기록입니다.
default_data = pd.DataFrame({
    "요일": days,
    "취침 시간": [
        "00:30", "00:30", "01:00", "00:30",
        "01:30", "02:00", "00:30"
    ],
    "기상 시간": [
        "07:00", "07:00", "07:00", "07:00",
        "07:30", "10:00", "09:30"
    ]
})

# 입력한 기록을 저장해 화면이 갱신되어도 유지합니다.
if "sleep_data" not in st.session_state:
    st.session_state.sleep_data = default_data.copy()

edited_data = st.data_editor(
    st.session_state.sleep_data,
    hide_index=True,
    use_container_width=True,
    column_config={
        "요일": st.column_config.TextColumn(
            "요일",
            disabled=True
        ),
        "취침 시간": st.column_config.TextColumn(
            "잠든 시간 (HH:MM)"
        ),
        "기상 시간": st.column_config.TextColumn(
            "일어난 시간 (HH:MM)"
        )
    },
    key="sleep_editor"
)

st.session_state.sleep_data = edited_data.copy()

# ------------------------------
# 5. 분석 버튼과 입력값 검사
# ------------------------------
if st.button("📊 일주일 수면 패턴 분석하기", type="primary",
             use_container_width=True):

    results = []
    errors = []

    for _, row in edited_data.iterrows():
        try:
            bed = parse_time(row["취침 시간"])
            wake = parse_time(row["기상 시간"])

            minutes = calculate_sleep(bed, wake)

            # 같은 시각을 입력했거나 24시간 이상이면 오류로 안내합니다.
            if minutes <= 0 or minutes >= 1440:
                raise ValueError("시간을 확인해 주세요.")

            results.append({
                "요일": row["요일"],
                "취침 시간": bed.strftime("%H:%M"),
                "기상 시간": wake.strftime("%H:%M"),
                "수면 시간(분)": minutes
            })

        except (ValueError, TypeError):
            errors.append(
                f"{row['요일']}요일의 시간을 확인하세요. "
                "예: 01:30, 07:50"
            )

    if errors:
        st.error("시간 입력을 수정한 뒤 다시 분석해 주세요.")
        for error in errors:
            st.write("- " + error)

        st.session_state.analysis_done = False

    else:
        st.session_state.analysis_results = results
        st.session_state.analysis_done = True


# ------------------------------
# 6. 분석 결과 표시
# ------------------------------
if st.session_state.get("analysis_done", False):

    result = pd.DataFrame(st.session_state.analysis_results)
    sleep_minutes = result["수면 시간(분)"].tolist()

    average = round(sum(sleep_minutes) / len(sleep_minutes))
    longest_index = result["수면 시간(분)"].idxmax()
    shortest_index = result["수면 시간(분)"].idxmin()

    st.header("3. 나의 수면 분석 결과")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "일주일 평균 수면 시간",
        format_sleep(average)
    )

    col2.metric(
        "가장 오래 잔 날",
        result.loc[longest_index, "요일"] + "요일",
        format_sleep(result.loc[longest_index, "수면 시간(분)"])
    )

    col3.metric(
        "가장 짧게 잔 날",
        result.loc[shortest_index, "요일"] + "요일",
        format_sleep(result.loc[shortest_index, "수면 시간(분)"])
    )

    # 요일별 수면 시간 그래프
    st.subheader("요일별 수면 시간")

    chart_data = result.set_index("요일")["수면 시간(분)"] / 60
    st.bar_chart(chart_data, y_label="수면 시간(시간)")

    # 취침·기상 시간 그래프에 사용할 숫자를 만듭니다.
    def clock_to_hours(value):
        t = parse_time(value)
        return t.hour + t.minute / 60

    clock_data = pd.DataFrame({
        "취침 시간": [
            clock_to_hours(x) for x in result["취침 시간"]
        ],
        "기상 시간": [
            clock_to_hours(x) for x in result["기상 시간"]
        ]
    }, index=result["요일"])

    st.subheader("요일별 취침·기상 시각")
    st.line_chart(clock_data, y_label="시각 (시간)")

    # 기록에서 확인할 수 있는 특징을 자동으로 해석합니다.
    st.subheader("수면 패턴 해석")

    difference = max(sleep_minutes) - min(sleep_minutes)

    st.write(
        f"가장 오래 잔 날과 짧게 잔 날의 차이는 "
        f"**{format_sleep(difference)}**입니다."
    )

    if difference <= 60:
        st.write("요일별 수면 시간이 비교적 비슷한 편이에요.")
    elif difference <= 120:
        st.write("요일별 수면 시간에 어느 정도 차이가 있어요.")
    else:
        st.write(
            "요일별 수면 시간 차이가 큰 편이에요. "
            "수면 시간이 짧은 날이 반복되는지 확인해 보세요."
        )

    # 앞의 5일은 평일, 마지막 2일은 주말로 비교합니다.
    weekday_average = round(sum(sleep_minutes[:5]) / 5)
    weekend_average = round(sum(sleep_minutes[5:]) / 2)
    weekend_difference = weekend_average - weekday_average

    st.write(f"평일 평균 수면: **{format_sleep(weekday_average)}**")
    st.write(f"주말 평균 수면: **{format_sleep(weekend_average)}**")

    if weekend_difference >= 30:
        st.write(
            f"주말에 평일보다 평균 "
            f"**{format_sleep(weekend_difference)} 더 오래** 자요."
        )
    elif weekend_difference <= -30:
        st.write(
            f"주말에 평일보다 평균 "
            f"**{format_sleep(abs(weekend_difference))} 덜** 자요."
        )
    else:
        st.write("평일과 주말의 평균 수면 시간이 비슷해요.")

    st.info(
        "이 결과는 입력한 취침·기상 시간으로 계산한 값입니다. "
        "실제 잠든 시각이나 밤중에 깬 시간은 반영하지 않습니다."
    )


# ------------------------------
# 7. 수면 단계와 수면 주기 설명
# ------------------------------
st.header("4. 수면 주기 알아보기")

st.write(
    "수면 중에는 비렘수면과 렘수면이 여러 차례 반복됩니다. "
    "한 주기는 대략 80~100분 정도이지만 개인과 밤에 따라 달라질 수 있어요."
)

with st.expander("얕은 수면 · 깊은 수면 · 렘수면 자세히 알아보기"):

    st.subheader("얕은 수면")
    st.write(
        "잠이 들고 깊은 수면으로 이어지는 과정에 포함되는 단계입니다."
    )

    st.subheader("깊은 수면")
    st.write(
        "비렘수면의 깊은 단계입니다. 밤의 전반부에 "
        "더 많이 나타나는 경향이 있습니다."
    )

    st.subheader("렘수면 (REM)")
    st.write(
        "뇌 활동이 활발하고 생생한 꿈을 꾸기도 하는 단계입니다. "
        "밤의 후반부에는 한 번의 렘수면이 길어지는 경향이 있습니다."
    )

    st.warning(
        "취침·기상 시간만으로 개인의 실제 렘수면이나 깊은 수면 시간을 "
        "계산할 수는 없습니다. 실제 수면 단계 측정에는 뇌파와 "
        "눈 움직임 등의 자료가 필요합니다."
    )


# ------------------------------
# 8. 생체시계와 연결하기
# ------------------------------
st.header("5. 생체시계와 수면 리듬")

st.write(
    "빛은 눈의 망막을 통해 생체시계의 중심인 "
    "시교차상핵(SCN)에 전달되는 신호 중 하나입니다. "
    "수면 기록을 통해 생활 리듬의 규칙성을 살펴볼 수 있지만, "
    "일주일 기록만으로 아침형·저녁형을 확정할 수는 없습니다."
)

st.caption("이 앱은 학습과 자기 관찰을 위한 도구이며, 의학적 진단을 제공하지 않습니다.")
