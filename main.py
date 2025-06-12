import streamlit as st
import pandas as pd
from math import radians, cos, sin, asin, sqrt
from streamlit_folium import st_folium
import folium

# 📦 스타일: 지도 아래 여백 줄이기
st.markdown("""
<style>
.block-container {
    padding-bottom: 1rem;
}
iframe {
    height: 500px !important;
}
</style>
""", unsafe_allow_html=True)

# 🧠 거리 계산 함수 (Haversine 공식)
def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c  # km 단위

# 📂 CSV 데이터 로드
@st.cache_data
def load_data():
    df = pd.read_csv("서울시 공영주차장 안내 정보.csv", encoding="euc-kr")
    df = df.dropna(subset=["위도", "경도"])
    df["위도"] = df["위도"].astype(float)
    df["경도"] = df["경도"].astype(float)
    return df

# 데이터 불러오기
df = load_data()

# 🌐 Streamlit 앱 UI 시작
st.title("🅿️ 지도에서 위치 선택 → 근처 주차장 찾기")
st.markdown("지도를 클릭하면 해당 위치 근처의 공영주차장 정보를 보여줍니다.")

# 지도 기본 위치 설정 (서울 시청)
default_location = [37.5665, 126.9780]
m = folium.Map(location=default_location, zoom_start=12)

# 지도 클릭 정보 받기
click_info = st_folium(m, height=500, returned_objects=["last_clicked"])

# 사용자가 클릭한 경우
if click_info and click_info["last_clicked"]:
    lat = click_info["last_clicked"]["lat"]
    lon = click_info["last_clicked"]["lng"]
    st.success(f"📍 선택한 위치: 위도 {lat:.6f}, 경도 {lon:.6f}")

    # 클릭 위치 기반 새 지도 생성 + 빨간 마커
    m2 = folium.Map(location=[lat, lon], zoom_start=15)
    folium.Marker(
        [lat, lon],
        tooltip="선택한 위치",
        icon=folium.Icon(color="red")
    ).add_to(m2)

    # 거리 계산해서 가까운 주차장만 선택
    df["거리(km)"] = df.apply(lambda row: haversine(lat, lon, row["위도"], row["경도"]), axis=1)
    nearby = df[df["거리(km)"] <= 1].sort_values("거리(km)").head(10)

    # 지도에 주차장 마커 추가
    for _, row in nearby.iterrows():
        folium.Marker(
            [row["위도"], row["경도"]],
            tooltip=f"{row['주차장명']} ({row['거리(km)']:.2f}km)",
            popup=row["주소"],
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m2)

    # 최종 지도 다시 표시
    st_folium(m2, height=500)

    # 주차장 정보 표로 표시
    st.write("### 📊 가까운 주차장 정보")
    st.dataframe(nearby[["주차장명", "주소", "전화번호", "거리(km)"]])
else:
    st.info("지도를 클릭해서 위치를 선택하세요!")

