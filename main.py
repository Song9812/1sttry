import streamlit as st
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import folium_static
from datetime import datetime, time, timedelta

# maps_navigation 도구 import (가상 환경에서 제공되는 도구)
# 실제 Streamlit 앱에서는 직접 사용할 수 없으므로, 웹 링크로 대체하여 구현합니다.
# import maps_navigation # 이 줄은 실제 Streamlit 앱에서는 주석 처리되거나 제거되어야 합니다.

# 1. 데이터 로드 및 전처리
@st.cache_data # 데이터를 한 번 로드하면 다시 로드하지 않도록 캐싱
def load_data(file_path):
    df = pd.read_csv(file_path, encoding='cp949') # 한글 인코딩 문제 해결을 위해 cp949 또는 utf-8-sig 시도
    # 'x 좌표'를 경도(longitude)로, 'y 좌표'를 위도(latitude)로 사용
    df = df.rename(columns={'x 좌표': '경도', 'y 좌표': '위도'})
    # 위도와 경도 컬럼이 숫자인지 확인하고, 숫자가 아니면 NaN으로 처리 (에러 방지)
    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
    # 위도 또는 경도가 없는(NaN) 행은 제거
    df.dropna(subset=['위도', '경도'], inplace=True)
    
    # '개방시간' 컬럼 전처리: 시간 파싱 및 정리
    df['개방시간_시작'] = None
    df['개방시간_종료'] = None
    
    for idx, row in df.iterrows():
        open_time_str = str(row['개방시간']).strip()
        if '24시간' in open_time_str or '상시' in open_time_str or '연중' in open_time_str:
            df.at[idx, '개방시간_시작'] = time(0, 0)
            df.at[idx, '개방시간_종료'] = time(23, 59, 59)
        elif '~' in open_time_str:
            try:
                # '09:00~18:00', '9:00~18:00', '0900~1800' 등 다양한 형식 처리 시도
                start_str, end_str = open_time_str.split('~')
                
                # 시간 파싱을 위한 유연한 처리
                start_time_obj = None
                end_time_obj = None

                # HH:MM 형식 시도
                try:
                    start_time_obj = datetime.strptime(start_str.strip(), '%H:%M').time()
                except ValueError:
                    pass
                try:
                    end_time_obj = datetime.strptime(end_str.strip(), '%H:%M').time()
                except ValueError:
                    pass

                # HHMM 형식 시도
                if start_time_obj is None:
                    try:
                        start_time_obj = datetime.strptime(start_str.strip(), '%H%M').time()
                    except ValueError:
                        pass
                if end_time_obj is None:
                    try:
                        end_time_obj = datetime.strptime(end_str.strip(), '%H%M').time()
                    except ValueError:
                        pass
                
                # 최종적으로 파싱 성공 시에만 할당
                if start_time_obj and end_time_obj:
                    df.at[idx, '개방시간_시작'] = start_time_obj
                    df.at[idx, '개방시간_종료'] = end_time_obj
                else:
                    # 파싱 실패 시 None으로 남겨둠
                    pass
            except ValueError:
                pass # 파싱 오류 시 (예: 잘못된 형식) None 유지
        # 그 외의 경우는 None으로 남겨두어 '개방시간 불명'으로 처리

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

# 3. 화장실 개방 여부 판단 함수
def is_toilet_open(current_time, start_time, end_time):
    if start_time is None or end_time is None:
        return '불명' # 개방시간 정보 없음
    
    # 자정을 넘어서 개방하는 경우 (예: 22:00 ~ 02:00) 처리
    if start_time <= end_time: # 당일 개방 종료
        return '개방' if start_time <= current_time <= end_time else '폐쇄'
    else: # 자정을 넘어 개방 (예: 22:00 시작, 02:00 종료)
        return '개방' if current_time >= start_time or current_time <= end_time else '폐쇄'


# 4. 메인 스트림릿 앱
def app():
    st.title("내 근처 서울시 공중화장실 찾기 🚽")

    # 데이터 로드
    df = load_data("서울시 공중화장실 위치정보.csv")

    if df.empty:
        st.error("공중화장실 데이터를 로드하는 데 실패했거나 데이터가 비어 있습니다. CSV 파일의 인코딩을 확인하거나 내용이 올바른지 확인해주세요.")
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
                st.session_state['user_location'] = user_location # 사용자 위치를 세션 상태에 저장
                st.session_state['user_address'] = user_address # 사용자 주소를 세션 상태에 저장
                st.sidebar.success(f"입력된 위치: 위도 {user_location[0]:.4f}, 경도 {user_location[1]:.4f}")
            else:
                st.sidebar.error("입력된 주소를 찾을 수 없습니다. 다시 시도해 주세요.")
        else:
            st.sidebar.warning("주소를 입력해 주세요.")
            
    # 사용자 위치가 설정되었는지 확인
    if 'user_location' in st.session_state and st.session_state['user_location']:
        user_location = st.session_state['user_location']
        user_address = st.session_state['user_address']

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
            
            # 현재 시간 가져오기
            current_time = datetime.now().time()
            st.info(f"현재 시간: {current_time.strftime('%H시 %M분')}")
            
            # 지도 시각화 (Folium)
            m = folium.Map(location=[user_lat, user_lon], zoom_start=14)

            # 사용자 위치 마커
            folium.Marker(
                [user_lat, user_lon],
                popup=f"내 위치: {user_address}",
                icon=folium.Icon(color="red", icon="home", prefix="fa")
            ).add_to(m)

            # 근처 화장실 마커 추가
            toilet_options = {} # 길찾기 선택을 위한 딕셔너리
            for idx, row in nearby_toilets.iterrows():
                # 개방 여부 판단
                open_status = is_toilet_open(current_time, row['개방시간_시작'], row['개방시간_종료'])
                
                # 마커 색깔 설정
                if open_status == '개방':
                    marker_color = "blue"
                    icon_type = "info-sign"
                elif open_status == '폐쇄':
                    marker_color = "darkred"
                    icon_type = "lock"
                else: # 불명
                    marker_color = "lightgray"
                    icon_type = "question-sign"

                # 팝업 정보 구성
                popup_html = f"""
                <b>건물명:</b> {row['건물명'] if pd.notna(row['건물명']) else '정보 없음'}<br>
                <b>개방시간:</b> {row['개방시간'] if pd.notna(row['개방시간']) else '정보 없음'}<br>
                <b>화장실 현황:</b> {row['화장실 현황'] if pd.notna(row['화장실 현황']) else '정보 없음'}<br>
                <b>장애인화장실 현황:</b> {row['장애인화장실 현황'] if pd.notna(row['장애인화장실 현황']) else '정보 없음'}<br>
                <hr style="margin: 5px 0;">
                <b>현재 개방 여부:</b> <b>{open_status}</b><br>
                거리: {row['거리_km']:.2f} km<br>
                도로명주소: {row['도로명주소']}
                """
                
                folium.Marker(
                    [row['위도'], row['경도']],
                    popup=folium.Popup(popup_html, max_width=300),
                    icon=folium.Icon(color=marker_color, icon=icon_type, prefix="fa")
                ).add_to(m)

                # 길찾기 선택을 위한 옵션에 추가
                display_name = f"{row['건물명']} ({row['도로명주소']})"
                toilet_options[display_name] = {'address': row['도로명주소'], 'lat': row['위도'], 'lon': row['경도']}
            
            # 지도 표시
            folium_static(m)

            # 필터링된 화장실 목록 표시 및 길찾기 기능
            st.subheader("찾은 공중화장실 목록")
            # 개방 여부 컬럼 추가
            nearby_toilets['개방여부'] = nearby_toilets.apply(
                lambda row: is_toilet_open(current_time, row['개방시간_시작'], row['개방시간_종료']),
                axis=1
            )
            display_cols = ['건물명', '도로명주소', '거리_km', '개방시간', '개방여부', '화장실 현황', '장애인화장실 현황', '전화번호']
            display_df = nearby_toilets[display_cols].fillna('정보 없음')
            display_df['거리_km'] = display_df['거리_km'].apply(lambda x: f"{x:.2f} km") # 거리 포맷팅
            
            st.dataframe(display_df.set_index('건물명'))

            st.markdown("---")
            st.subheader("선택한 화장실 길찾기")
            
            # 길찾기할 화장실 선택
            selected_toilet_display_name = st.selectbox(
                "길찾기를 원하는 화장실을 선택하세요:",
                options=list(toilet_options.keys()),
                index=0 # 기본적으로 첫 번째 항목 선택
            )

            # 선택된 화장실 정보 가져오기
            selected_toilet_info = toilet_options.get(selected_toilet_display_name)
            
            if selected_toilet_info:
                st.write(f"선택된 화장실: **{selected_toilet_display_name}**")
                
                # 구글 지도로 바로 연결하는 버튼
                # 출발지: 사용자 현재 위치 (위도, 경도)
                # 목적지: 선택된 화장실 (위도, 경도)
                Maps_url = (
                    f"https://www.google.com/maps/dir/?api=1&origin={user_lat},{user_lon}"
                    f"&destination={selected_toilet_info['lat']},{selected_toilet_info['lon']}"
                    f"&travelmode=driving" # driving, walking, bicycling, transit 중 선택
                )
                
                st.markdown(f"[Google 지도로 길찾기 (새 탭 열림)]({Maps_url})", unsafe_allow_html=True)

                # **(참고) maps_navigation 도구를 사용하는 예시 (현재 환경에서만 가능)**
                # if st.button("내비게이션 도구로 길찾기"):
                #     try:
                #         # 가상 환경에서 maps_navigation 도구 사용 시
                #         directions = maps_navigation.Google Maps(
                #             origin=user_address, # 사용자 주소
                #             destination=selected_toilet_info['address'] # 선택된 화장실 주소
                #         )
                #         if directions and directions.mapUrl:
                #             st.success("길찾기 정보가 생성되었습니다.")
                #             st.markdown(f"**[길찾기 지도 보기]({directions.mapUrl})**", unsafe_allow_html=True)
                #             if directions.routes:
                #                 st.write("---")
                #                 st.write("**경로 요약:**")
                #                 for i, route in enumerate(directions.routes):
                #                     st.write(f"- 경로 {i+1}: {route.summary} (약 {route.duration.text}, {route.distance.text})")
                #                     # st.json(route.legs[0].steps) # 상세 스텝
                #         else:
                #             st.warning("길찾기 정보를 가져올 수 없습니다. 주소를 확인하거나 다른 방법을 시도해 보세요.")
                #     except Exception as e:
                #         st.error(f"길찾기 도구 사용 중 오류가 발생했습니다: {e}")

            else:
                st.info("선택된 화장실 정보가 없습니다. 목록에서 화장실을 선택해주세요.")

        else:
            st.warning(f"{distance_threshold}km 이내에 화장실을 찾을 수 없습니다. 거리를 늘려보세요.")
    else:
        st.info("왼쪽 사이드바에서 주소를 입력하고 '내 위치로 화장실 찾기' 버튼을 눌러주세요.")

if __name__ == '__main__':
    app()
