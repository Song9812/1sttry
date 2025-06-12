import streamlit as st
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import folium_static

# 1. 데이터 로드 및 전처리
@st.cache_data
def load_data(file_path):
    df = pd.read_csv(file_path, encoding='cp949') # 한글 인코딩 문제 해결을 위해 cp949 또는 utf-8-sig 시도
    # 'x 좌표'를 경도(longitude)로, 'y 좌표'를 위도(latitude)로 사용
    df = df.rename(columns={'x 좌표': '경도', 'y 좌표': '위도'})
    # 위도와 경도 컬럼이 숫자인지 확인하고, 숫자가 아니면 NaN으로 처리 (에러 방지)
    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
    # 위도 또는 경도가 없는(NaN) 행은 제거
    df.dropna(subset=['위도', '경도'], inplace=True)
    return df

# 2. 주소 -> 위도/경도 변환 함수 (Geocoding)
@st.cache_data(show_spinner="주소를 위도/경도로 변환 중...")
def geocode_address(address):
    geolocator = Nominatim(user_agent="toilet_finder_app") # 사용자 에이전트 지정
    try:
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
        else:
            return None
    except Exception as e:
        st.error(f"주소 변환 중 오류가 발생했습니다: {e}")
        return None

# 3. 메인 스트림릿 앱
def app():
    st.title("내 근처 서울시 공중화장실 찾기 🚽")

    # 데이터 로드
    df = load_data("서울시 공중화장실 위치정보.csv")

    if df.empty:
        st.error("공중화장실 데이터를 로드하는 데 실패했거나 데이터가 비어 있습니다.")
        return

    st.sidebar.header("내 위치 설정")
    user_address = st.sidebar.text_input("현재 위치 주소 입력 (예: 서울특별시 강남구 테헤란로 101)", "서울특별시청")
    
    # 거리 슬라이더
    distance_threshold = st.sidebar.slider(
        "찾을 거리 (km)",
        min_value=0.1, max_value=5.0, value=1.0, step=0.1
    )

    user_location = None
    if st.sidebar.button("내 위치로 화장실 찾기"):
        if user_address:
            user_location = geocode_address(user_address)
            if user_location:
                st.sidebar.success(f"입력된 위치: 위도 {user_location[0]:.4f}, 경도 {user_location[1]:.4f}")
            else:
                st.sidebar.error("입력된 주소를 찾을 수 없습니다. 다시 시도해 주세요.")
        else:
            st.sidebar.warning("주소를 입력해 주세요.")
    
    # 맵 및 결과 표시
    if user_location:
        st.subheader(f"내 위치({user_address}) 근처 {distance_threshold}km 이내 화장실")

        # 사용자 위치 위도, 경도
        user_lat, user_lon = user_location

        # 각 화장실과의 거리 계산
        df['거리_km'] = df.apply(
            lambda row: geodesic((user_lat, user_lon), (row['위도'], row['경도'])).km,
            axis=1
        )

        # 거리 기준으로 필터링
        nearby_toilets = df[df['거리_km'] <= distance_threshold].sort_values(by='거리_km').reset_index(drop=True)

        if not nearby_toilets.empty:
            st.write(f"총 {len(nearby_toilets)}개의 화장실이 {distance_threshold}km 이내에 있습니다.")
            
            # 지도 시각화 (Folium)
            m = folium.Map(location=[user_lat, user_lon], zoom_start=14)

            # 사용자 위치 마커
            folium.Marker(
                [user_lat, user_lon],
                popup=f"내 위치: {user_address}",
                icon=folium.Icon(color="red", icon="home", prefix="fa")
            ).add_to(m)

            # 근처 화장실 마커 추가
            for idx, row in nearby_toilets.iterrows():
                # 팝업 정보 구성
                # pd.notna(row['컬럼명']) 으로 NaN 값 체크 및 '정보 없음' 처리
                popup_html = f"""
                <b>건물명:</b> {row['건물명'] if pd.notna(row['건물명']) else '정보 없음'}<br>
                <b>개방시간:</b> {row['개방시간'] if pd.notna(row['개방시간']) else '정보 없음'}<br>
                <b>화장실 현황:</b> {row['화장실 현황'] if pd.notna(row['화장실 현황']) else '정보 없음'}<br>
                <b>장애인화장실 현황:</b> {row['장애인화장실 현황'] if pd.notna(row['장애인화장실 현황']) else '정보 없음'}<br>
                <hr style="margin: 5px 0;">
                거리: {row['거리_km']:.2f} km<br>
                도로명주소: {row['도로명주소']}
                """
                
                folium.Marker(
                    [row['위도'], row['경도']],
                    # `folium.Popup`을 사용하여 HTML 콘텐츠를 포함하고 max_width로 크기 조절
                    popup=folium.Popup(popup_html, max_width=300),
                    icon=folium.Icon(color="blue", icon="info-sign", prefix="fa")
                ).add_to(m)
            
            # 지도 표시
            folium_static(m)

            # 필터링된 화장실 목록 표시
            st.subheader("찾은 공중화장실 목록")
            display_cols = ['건물명', '도로명주소', '거리_km', '개방시간', '화장실 현황', '장애인화장실 현황', '전화번호']
            display_df = nearby_toilets[display_cols].fillna('정보 없음')
            display_df['거리_km'] = display_df['거리_km'].apply(lambda x: f"{x:.2f} km")
            st.dataframe(display_df.set_index('건물명'))

        else:
            st.warning(f"{distance_threshold}km 이내에 화장실을 찾을 수 없습니다. 거리를 늘려보세요.")
    else:
        st.info("왼쪽 사이드바에서 주소를 입력하고 '내 위치로 화장실 찾기' 버튼을 눌러주세요.")

if __name__ == '__main__':
    app()
