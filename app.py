# app.py
"""
서울 기온 분석 Streamlit 앱
- 입력: seoul_temperature.csv (날짜, 지점, 평균기온(℃), 최저기온(℃), 최고기온(℃))
- 기능:
  1) 연도별 평균기온 꺾은선 그래프
  2) 5년 이동평균선 겹쳐 표시
  3) 사이드바 연도 범위 슬라이더
  4) 값이 없는 연도는 선을 끊어서 표시 (임의 연결 없음)
  5) 추가 그래프: 히트맵, 산점도, 막대그래프
- 필요 라이브러리: streamlit, pandas, plotly
"""

import os

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="서울 기온 분석", page_icon="🌡️", layout="wide")

CSV_PATH = "seoul_temperature.csv"


def load_data(path):
    """CSV 로드 + 전처리."""
    # 파일 존재 확인
    if not os.path.exists(path):
        st.error(f"데이터를 찾지 못했습니다: {path}")
        st.info("app.py와 같은 폴더에 seoul_temperature.csv 파일을 두세요.")
        st.stop()

    df = None
    for enc in ("utf-8-sig", "cp949"):
        try:
            df = pd.read_csv(path, sep=None, engine="python", encoding=enc)
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    if df is None:
        df = pd.read_csv(path, sep=None, engine="python")

    # 컬럼명 공백 제거
    df.columns = [str(c).strip() for c in df.columns]

    # 문자열 값 공백 제거(날짜 앞의 탭 포함)
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()

    # 날짜 변환
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")

    # 기온 컬럼 숫자 변환 (예: '13.5', '13.5℃' 처리)
    for col in ["평균기온(℃)", "최저기온(℃)", "최고기온(℃)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace("℃", "").str.strip(),
                errors="coerce",
            )

    # 지점 컬럼이 있으면 관측치가 가장 많은 지점으로 필터
    if "지점" in df.columns:
        top = df["지점"].value_counts().index[0]
        df = df[df["지점"].astype(str).str.strip() == str(top)].copy()
        df["지점"] = top

    # 필수 컬럼만 유지, 결측 행 제거
    df = df[
        ["날짜", "지점", "평균기온(℃)", "최저기온(℃)", "최고기온(℃)"]
    ].dropna()
    return df


# ---------------- 데이터 로드 ----------------
df = load_data(CSV_PATH)
df["연도"] = df["날짜"].dt.year

if df.empty:
    st.error("데이터가 비어 있습니다. CSV 파일의 내용을 확인하세요.")
    st.stop()

# ---------------- 사이드바 ----------------
st.title("서울 기온 분석 🌡️")
st.caption("데이터: seoul_temperature.csv  |  서울 기상관측소 일별 기온")

st.sidebar.header("분석 조건")
stations = sorted(df["지점"].unique())
station = st.sidebar.selectbox("관측 지점", ["전체"] + stations, index=0)

year_min = int(df["연도"].min())
year_max = int(df["연도"].max())
yr0, yr1 = st.sidebar.slider(
    "연도 범위", year_min, year_max, value=(year_min, year_max)
)

dff = df if station == "전체" else df[df["지점"] == station]

# ---------------- 집계 ----------------
yearly = (
    dff.groupby("연도")["평균기온(℃)"]
       .agg(연평균기온="mean", 관측일수="count")
       .reset_index()
)

# 5년 이동평균 (관측 연도 기준 5개 이동 평균)
yearly["5년이동평균"] = yearly["연평균기온"].rolling(window=5, min_periods=1).mean()

# 전체 연도 구간으로 확장 -> 값이 없는 연도는 NaN -> 그래프에서 선이 끊김
years_all = pd.DataFrame(
    {"연도": range(int(yearly["연도"].min()), int(yearly["연도"].max()) + 1)}
)
plot_df = years_all.merge(yearly, on="연도", how="left")

# 선택 구간
plot_range = (
    plot_df[(plot_df["연도"] >= yr0) & (plot_df["연도"] <= yr1)]
    .sort_values("연도")
    .reset_index(drop=True)
)

sel = dff[(dff["연도"] >= yr0) & (dff["연도"] <= yr1)]

# ---------------- 화면 구성 ----------------
st.subheader(f"선택 구간: {yr0}년 ~ {yr1}년")

if len(sel) == 0:
    st.warning("선택한 구간에 관측 데이터가 없습니다.")
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("구간 평균기온", f"{sel['평균기온(℃)'].mean():.2f} ℃")
    c2.metric("구간 최고기온", f"{sel['최고기온(℃)'].max():.1f} ℃")
    c3.metric("구간 최저기온", f"{sel['최저기온(℃)'].min():.1f} ℃")
    c4.metric("관측 일수", len(sel))

    st.write("**추가 지표**")
    st.dataframe(
        pd.DataFrame(
            [
                [
                    "일교차 평균",
                    (sel["최고기온(℃)"] - sel["최저기온(℃)"]).mean(),
                ],
                ["33℃ 이상 일수", int((sel["최고기온(℃)"] >= 33).sum())],
                ["0℃ 이하 일수", int((sel["최저기온(℃)"] <= 0).sum())],
            ],
            columns=["지표", "값"],
        ),
        use_container_width=True,
    )

# --- 그래프 ---
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=plot_range["연도"],
        y=plot_range["연평균기온"],
        mode="lines",
        name="연평균기온(℃)",
        line=dict(color="#d62728", width=2),
    )
)
fig.add_trace(
    go.Scatter(
        x=plot_range["연도"],
        y=plot_range["5년이동평균"],
        mode="lines",
        name="5년 이동평균(℃)",
        line=dict(color="#1f77b4", width=2, dash="dash"),
    )
)
fig.update_layout(
    title="연도별 평균기온과 5년 이동평균",
    xaxis_title="연도",
    yaxis_title="기온 (℃)",
    hovermode="x unified",
    margin=dict(l=40, r=20, t=40, b=30),
)
fig.update_xaxes(dtick=10)
st.plotly_chart(fig, use_container_width=True)
st.caption(
    "값이 없는 연도는 NaN 처리되어 선이 끊겨 표시됩니다. "
    "값을 임의로 이어 붙이지 않습니다."
)

# --- 연도별 표 ---
st.subheader("선택 구간 연도별 값")
tab = plot_range[["연도", "관측일수", "연평균기온", "5년이동평균"]].copy()
tab["연평균기온"] = tab["연평균기온"].round(2)
tab["5년이동평균"] = tab["5년이동평균"].round(2)
st.dataframe(tab.fillna("–"), use_container_width=True)
st.caption(
    "– = 해당 연도 값 없음(결측). "
    "연평균은 관측 연도로만 계산되며, 관측일수가 적은 해는 불안정할 수 있습니다."
)

# --- 극단값 ---
hot_year = yearly.loc[yearly["연평균기온"].idxmax()]
cold_year = yearly.loc[yearly["연평균기온"].idxmin()]
hot_day = dff.loc[dff["평균기온(℃)"].idxmax()]
st.subheader("극단값 참고 (전체 데이터 기준)")
st.dataframe(
    pd.DataFrame(
        [
            [
                "가장 더운 해(연평균 기준)",
                f"{int(hot_year['연도'])}년",
                f"{hot_year['연평균기온']:.2f} ℃",
            ],
            [
                "가장 추운 해(연평균 기준)",
                f"{int(cold_year['연도'])}년",
                f"{cold_year['연평균기온']:.2f} ℃",
            ],
            [
                "일별 평균기온 최고",
                hot_day["날짜"].strftime("%Y-%m-%d"),
                f"{hot_day['평균기온(℃)']:.2f} ℃",
            ],
        ],
        columns=["지표", "날짜", "값"],
    ),
    use_container_width=True,
)

# --- 원자료 교차 검증 ---
st.subheader("원자료 교차 검증")
st.dataframe(
    pd.DataFrame(
        [
            ["일별 평균기온 최고", "최고", f"{dff['평균기온(℃)'].max():.2f} ℃"],
            ["일별 평균기온 최저", "최저", f"{dff['평균기온(℃)'].min():.2f} ℃"],
            [
                "일별 최고기온 최고",
                "최고",
                f"{dff['최고기온(℃)'].max():.2f} ℃",
            ],
            [
                "일별 최저기온 최저",
                "최저",
                f"{dff['최저기온(℃)'].min():.2f} ℃",
            ],
        ],
        columns=["지표", "방향", "값"],
    ),
    use_container_width=True,
)
st.caption(
    "원본 CSV와 직접 대조할 때 사용하세요. "
    "(가장 큰 값·작은 값과 해당 날짜)"
)

# ---------------- 추가 그래프 작성을 위한 전처리 ----------------
dff["월"] = dff["날짜"].dt.month


def season_of(m):
    if m in [3, 4, 5]:
        return "봄"
    if m in [6, 7, 8]:
        return "여름"
    if m in [9, 10, 11]:
        return "가을"
    return "겨울"


dff["계절"] = dff["월"].map(season_of)

# ---------------- 추가 그래프 ----------------
st.subheader("다양한 그래프 추가")

# 1) 히트맵: 연도 × 월 평균기온
st.write("**히트맵: 연도 × 월 평균기온**")
heatmap_pivot = dff.pivot_table(
    index="연도", columns="월", values="평균기온(℃)", aggfunc="mean"
)
fig_heat = go.Figure(
    data=go.Heatmap(
        z=heatmap_pivot.values,
        x=heatmap_pivot.columns,
        y=heatmap_pivot.index,
        colorscale="RdYlBu_r",
        colorbar=dict(title="℃"),
        hovertemplate="연도=%{y}월=%{x}<br>평균기온= %{z:.2f} ℃<extra></extra>",
    )
)
fig_heat.update_layout(
    title="연도 × 월 평균기온 히트맵",
    xaxis_title="월",
    yaxis_title="연도",
    margin=dict(l=40, r=20, t=40, b=30),
)
st.plotly_chart(fig_heat, use_container_width=True)
st.caption(
    "짙은 빨강 = 높은 기온, 짙은 파랑 = 낮은 기온. "
    "각 칸은 해당 연도·월의 평균기온이며, 관측이 없는 조합은 비어 보입니다."
)

# 2) 산점도: 일별 평균기온 vs 최고기온 (색으로 계절)
st.write("**산점도: 일별 평균기온 vs 최고기온**")
fig_scatter = px.scatter(
    dff,
    x="평균기온(℃)",
    y="최고기온(℃)",
    color="계절",
    opacity=0.4,
    title="일별 평균기온 vs 최고기온",
    labels={
        "평균기온(℃)": "평균기온(℃)",
        "최고기온(℃)": "최고기온(℃)",
        "계절": "계절",
    },
)
fig_scatter.update_traces(marker_size=4)
fig_scatter.update_layout(
    xaxis_title="평균기온(℃)",
    yaxis_title="최고기온(℃)",
    margin=dict(l=40, r=20, t=40, b=30),
)
st.plotly_chart(fig_scatter, use_container_width=True)
st.caption(
    "점이 위쪽으로 퍼져 있을수록 일교차가 큽니다. "
    "점의 분포에서 이상값과 계절별 패턴, 평균과 최고의 관계를 확인할 수 있습니다."
)

# 3) 막대: 월별 최저/평균/최고 평균 (계절성 비교)
st.write("**막대: 월별 최저/평균/최고 평균기온**")
monthly_stats = dff.groupby("월").agg(
    최저기온_평균=("최저기온(℃)", "mean"),
    평균기온_평균=("평균기온(℃)", "mean"),
    최고기온_평균=("최고기온(℃)", "mean"),
).reset_index()
fig_bar = go.Figure()
fig_bar.add_trace(
    go.Bar(
        x=monthly_stats["월"],
        y=monthly_stats["최저기온_평균"],
        name="최저기온 평균",
        marker_color="#2ca02c",
    )
)
fig_bar.add_trace(
    go.Bar(
        x=monthly_stats["월"],
        y=monthly_stats["평균기온_평균"],
        name="평균기온 평균",
        marker_color="#1f77b4",
    )
)
fig_bar.add_trace(
    go.Bar(
        x=monthly_stats["월"],
        y=monthly_stats["최고기온_평균"],
        name="최고기온 평균",
        marker_color="#d62728",
    )
)
fig_bar.update_layout(
    title="월별 평균기온·최저기온·최고기온",
    xaxis_title="월",
    yaxis_title="기온 (℃)",
    barmode="group",
    margin=dict(l=40, r=20, t=40, b=30),
)
st.plotly_chart(fig_bar, use_container_width=True)
st.caption(
    "12개월을 막대로 비교하면 계절별 기온 차이와 월별 극값(1월 가장 낮음, 8월 가장 높음)을 확인할 수 있습니다."
)

# 4) 막대: 연도별 관측 일수 (데이터 결측 확인)
st.write("**막대: 연도별 관측 일수**")
annual_counts = dff.groupby("연도").size().reset_index(name="관측일수")
fig_count = px.bar(
    annual_counts,
    x="연도",
    y="관측일수",
    title="연도별 관측 일수",
    labels={"연도": "연도", "관측일수": "관측 일수"},
)
fig_count.update_layout(margin=dict(l=40, r=20, t=40, b=30))
st.plotly_chart(fig_count, use_container_width=True)
st.caption(
    "관측 일수가 0이거나 적으면 해당 연도 데이터가 거의 없어 연평균이 불안정할 수 있습니다."
)

# ---------------- 그래프를 통해 알 수 있는 점 ----------------
st.subheader("그래프를 통해 알 수 있는 점")
st.markdown(
    """
- **히트맵**: 특정 연도·월의 고온/저온 패턴, 여름과 겨울의 대비, 최근 연도 고온화 여부 확인 가능
- **산점도**: 평균기온과 최고기온의 관계, 일교차 분포, 이상값 확인 가능
- **월별 막대**: 계절별 기온 차이와 월별 극값(1월 가장 낮음, 8월 가장 높음) 확인 가능
- **연간 관측일수 막대**: 관측 중단 연도(1950~1953 등)나 결측 연도를 확인 가능
"""
)

# --- 처리 방법 ---
with st.expander("1) 데이터 처리 방법"):
    st.markdown(
        """
- **인코딩**: `utf-8-sig` 우선 시도, 실패 시 `cp949`(EUC-KR) 시도
- **구분자**: `sep=None`(자동 감지) → 탭/콤마 혼합에도 대응
- **날짜 앞의 탭**: 모든 문자열 컬럼을 `str.strip()` 처리 → 날짜 앞의 탭 문자 제거
- **연도/계절**: 연도 `dt.year`, 월 `dt.month`, 계절 `month` 기준 자동 분류
- **연평균기온**: 연도별 일별 `평균기온(℃)`의 평균
- **5년 이동평균**: 관측 연도를 연도순으로 늘어놓은 뒤 5개 단위 이동 평균
  (초기 연도는 사용 가능한 관측값만 사용)
- **선택 구간 통계**: 해당 연도 범위 안의 실제 관측된 날짜로 계산
- **결측 처리**: 값이 없는 연도는 `NaN` → 그래프에서 선을 끊어서 표시, 임의 연결 없음
"""
    )

# --- 해석 시 주의 ---
with st.expander("2) 해석 시 주의"):
    st.markdown(
        """
- **구간에 따라 추세가 달라짐**: 어느 범위를 선택하느냐에 따라 추세·극단값이 달라집니다.
- **한 해 값 vs 긴 흐름**: 가장 더운 해/추운 해 같은 한 해 값과 이동평균으로 보는 긴 흐름은 다릅니다.
- **값이 없는 기간**: 1950~1953년(한국전쟁 시기) 등 관측이 중단된 연도는 데이터에 없으므로 선이 끊깁니다.
  AI는 이러한 결측의 원인을 모르므로, 결측 구간 주변의 해석은 직접 확인하세요.
- **숫자 이상**: 1953년 0.64℃처럼 상식과 다른 값이 보이면 원본 CSV에서 해당 연도 행을 직접 대조하세요.
  관측일수가 적은 해의 연평균은 왜곡될 수 있습니다.
- **실행 ≠ 결과 보장**: 오류 없이 실행되어도 계산·해석이 옳은 것은 아닙니다.
- **해설 범위**: 원인·건강 영향 등 데이터에 없는 이야기로 넘어가지 않습니다.
"""
    )

# --- 측정값 정의 ---
with st.expander("3) 측정값 정의(무엇을 잴까)"):
    st.dataframe(
        pd.DataFrame(
            [
                ["연평균기온", "연도별 일별 평균기온(℃)의 평균"],
                ["일교차", "최고기온 − 최저기온 (일별 후 평균)"],
                ["33℃ 이상 날 수", "최고기온 ≥ 33℃인 날의 수"],
                ["0℃ 이하 날 수", "최저기온 ≤ 0℃인 날의 수"],
                [
                    "일별 최고기온 최고",
                    "최고기온(℃)의 최댓값 (날짜 포함)",
                ],
                [
                    "일별 최저기온 최저",
                    "최저기온(℃)의 최솟값 (날짜 포함)",
                ],
            ],
            columns=["측정값", "계산 방법"],
        ),
        use_container_width=True,
    )

# --- 추세 비교 (기간별 기울기) ---
with st.expander("4) 추세 비교 (기간별 기울기)"):
    st.caption("연평균기온 기준 선형 기울기. 10년 단위(℃/10년)로 표시.")

    def slope(x, y):
        n = len(x)
        if n < 2:
            return float("nan")
        mx, my = x.mean(), y.mean()
        num = ((x - mx) * (y - my)).sum()
        den = ((x - mx) ** 2).sum()
        return num / den if den else float("nan")

    rows, labels = [], []
    for w in [10, 20, 30, 50, 70, 100]:
        sub = yearly[yearly["연도"] > year_max - w]
        if len(sub) >= 2:
            s = slope(sub["연도"], sub["연평균기온"]) * 10  # ℃/10년
            rows.append(s)
            labels.append(f"{int(sub['연도'].min())}–{int(sub['연도'].max())}년")

    st.dataframe(
        pd.DataFrame(
            {"기간": labels, "추세(℃/10년)": [f"{v:.3f}" for v in rows]}
        ),
        use_container_width=True,
    )
