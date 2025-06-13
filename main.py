import streamlit as st
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import folium_static
from datetime import datetime, time
import pytz # 시간대 처리를 위해 pytz 라이브러리 추가

# 1. 데이터 로드 및 전처리
@st.cache_data
def load_data(file_path):
    # CSV 파일 인코딩 오류 처리를 강화합니다.
    try:
        df = pd.read_csv(file_path, encoding='cp949')
    except UnicodeDecodeError:
        st.error("CSV 파일 인코딩 오류! 'cp949'로 파일을 열 수 없습니다. 'utf-8' 또는 'utf-8-sig'로 시도합니다.")
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            st.error("CSV 파일 인코딩 오류! 'utf-8'로도 파일을 열 수 없습니다. 'utf-8-sig'로 시도합니다.")
            df = pd.read_csv(file_path, encoding='utf-8-sig')

    df = df.rename(columns={'x 좌표': '경도', 'y 좌표': '위도'})
    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
    df.dropna(subset=['위도', '경도'], inplace=True)
    
    df['개방시간_시작'] = None
    df['개방시간_종료'] = None
    
    for idx, row in df.iterrows():
        open_time_str = str(row['개방시간']).strip()
        
        # '24시간', '상시', '연중' 등의 키워드 처리
        if '24시간' in open_time_str or '상시' in open_time_str or '연중' in open_time_str:
            df.at[idx, '개방시간_시작'] = time(0, 0)
            df.at[idx, '개방시간_종료'] = time(23, 59, 59)
        # '~' 또는 '-' 기호를 포함하는 시간 범위 처리
        elif '~' in open_time_str or '-' in open_time_str: 
            # 어떤 기호로 분리되어 있는지 확인하고 분리
            if '~' in open_time_str:
                parts = open_time_str.split('~')
            else: # '-' 인 경우
                parts = open_time_str.split('-')

            if len(parts) == 2: # 시작 시간과 종료 시간이 모두 있는 경우
                start_str, end_str = parts[0].strip(), parts[1].strip()
                
                start_time_obj = None
                end_time_obj = None

                # 시작 시간 파싱 시도 (HH:MM -> HHMM 순으로)
                try:
                    start_time_obj = datetime.strptime(start_str, '%H:%M').time()
                except ValueError:
                    try:
                        start_time_obj = datetime.strptime(start_str, '%H%M').time()
                    except ValueError:
                        pass # 파싱 실패, None 유지
                
                # 종료 시간 파싱 시도 (HH:MM -> HHMM 순으로)
                try:
                    end_time_obj = datetime.strptime(end_str, '%H:%M').time()
                except ValueError:
                    try:
                        end_time_obj = datetime.strptime(end_str, '%H%M').time()
                    except ValueError:
                        pass # 파싱 실패, None 유지
                
                if start_time_obj and end_time_obj: # 두 시간 모두 성공적으로 파싱된 경우에만 적용
                    df.at[idx, '개방시간_시작'] = start_time_obj
                    df.at[idx, '개방시간_종료'] = end_time_obj
            # else: parts의 길이가 2가 아니면 (예: '12-34-56'처럼 잘못된 형식) 이 경우도 None으로 남아 '불명' 처리
        # else: 위의 어떤 조건에도 해당하지 않으면 시작/종료 시간은 None으로 남아 '불명' 처리
    return df

# 2. 주소 -> 위도/경도 변환 함수 (Geocoding)
@st.cache_data(show_spinner="주소를 위도/경도로 변환 중...")
def geocode_address(address):
    geolocator = Nominatim(user_agent="toilet_finder_app")
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
    if start_time is None or end_time is None: # 시작 또는 종료 시간이 불명이면 '불명' 반환
        return '불명'
    
    if start_time <= end_time: # 자정을 넘어가지 않는 일반적인 개방 시간 (예: 09:00 ~ 18:00)
        return '개방' if start_time <= current_time <= end_time else '폐쇄'
    else: # 자정을 넘어 개방 (예: 22:00 ~ 02:00)
        return '개방' if current_time >= start_time or current_time <= end_time else '폐쇄'

# 4. 개방여부 스타일링 함수
def highlight_open_status(s):
    if s == '개방':
        return 'background-color: #e6ffe6; color: green; font-weight: bold;'
    elif s == '폐쇄':
        return 'background-color: #ffe6e6; color: red; font-weight: bold;'
    else: # 불명
        return 'background-color: #f0f0f0; color: gray;'

# 5. 메인 스트림릿 앱
def app():
    st.set_page_config(layout="wide")
    st.title("내 근처 서울시 공중화장실 찾기 🚽")

    df = load_data("서울시 공중화장실 위치정보.csv")

    if df.empty:
        st.error("공중화장실 데이터를 로드하는 데 실패했거나 데이터가 비어 있습니다. CSV 파일의 인코딩을 확인하거나 내용이 올바른지 확인해주세요.")
        return

    st.sidebar.header("내 위치 설정")
    user_address = st.sidebar.text_input("현재 위치 주소 입력 (예: 서울특별시 강남구 테헤란로 101)", "서울특별시청")
    
    distance_threshold = st.sidebar.slider(
        "찾을 거리 (km)",
        min_value=0.1, max_value=5.0, value=1.0, step=0.1
    )

    user_location = None
    if st.sidebar.button("내 위치로 화장실 찾기"):
        if user_address:
            user_location = geocode_address(user_address)
            if user_location:
                st.session_state['user_location'] = user_location
                st.session_state['user_address'] = user_address
                st.sidebar.success(f"입력된 위치: 위도 {user_location[0]:.4f}, 경도 {user_location[1]:.4f}")
            else:
                st.sidebar.error("입력된 주소를 찾을 수 없습니다. 다시 시도해 주세요.")
        else:
            st.sidebar.warning("주소를 입력해 주세요.")
            
    if 'user_location' in st.session_state and st.session_state['user_location']:
        user_location = st.session_state['user_location']
        user_address = st.session_state['user_address']

        st.subheader(f"내 위치({user_address}) 근처 {distance_threshold}km 이내 화장실")

        user_lat, user_lon = user_location

        df['거리_km'] = df.apply(
            lambda row: geodesic((user_lat, user_lon), (row['위도'], row['경도'])).km,
            axis=1
        )

        nearby_toilets = df[df['거리_km'] <= distance_threshold].sort_values(by='거리_km').reset_index(drop=True)

        if not nearby_toilets.empty:
            st.write(f"총 {len(nearby_toilets)}개의 화장실이 {distance_threshold}km 이내에 있습니다.")
            
            # 현재 시간을 대한민국 표준시(KST)로 강제 지정
            korea_tz = pytz.timezone('Asia/Seoul')
            current_time_kst = datetime.now(korea_tz).time()
            st.info(f"현재 시간 (대한민국 표준시): {current_time_kst.strftime('%H시 %M분')}") 

            m = folium.Map(location=[user_lat, user_lon], zoom_start=14)

            folium.Marker(
                [user_lat, user_lon],
                popup=f"내 위치: {user_address}",
                icon=folium.Icon(color="red", icon="home", prefix="fa")
            ).add_to(m)

            for idx, row in nearby_toilets.iterrows():
                # KST로 가져온 시간을 is_toilet_open 함수에 전달
                open_status = is_toilet_open(current_time_kst, row['개방시간_시작'], row['개방시간_종료'])
                
                # 마커 색상 및 아이콘 변경
                if open_status == '개방':
                    marker_color = "blue"
                    icon_type = "toilet" # 이모지 아이콘
                    prefix_type = "fa" # 'fa'를 사용하면 Font Awesome 아이콘을 사용합니다.
                                       # Folium의 기본 이모지는 'emoji' prefix로 사용 가능하지만,
                                       # Font Awesome 아이콘 중 화장실 모양이 더 명확합니다.
                elif open_status == '폐쇄':
                    marker_color = "lightgray" # 회색으로 변경
                    icon_type = "lock"
                    prefix_type = "fa"
                else: # 불명
                    marker_color = "orange" # 노란색에 가까운 오렌지로 변경
                    icon_type = "question-sign"
                    prefix_type = "fa"

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
                    icon=folium.Icon(color=marker_color, icon=icon_type, prefix=prefix_type)
                ).add_to(m)
            
            folium_static(m)

            st.subheader("찾은 공중화장실 목록")
            nearby_toilets['개방여부'] = nearby_toilets.apply(
                lambda row: is_toilet_open(current_time_kst, row['개방시간_시작'], row['개방시간_종료']), # KST 시간 적용
                axis=1
            )
            
            display_cols_ordered = [
                '건물명', '거리_km', '개방시간', '개방여부',
                '화장실 현황', '장애인화장실 현황', '도로명주소', '전화번호'
            ]
            display_df = nearby_toilets[display_cols_ordered].fillna('정보 없음')
            display_df['거리_km'] = display_df['거리_km'].apply(lambda x: f"{x:.2f} km")

            st.dataframe(display_df.style.applymap(highlight_open_status, subset=['개방여부']).set_properties(**{'text-align': 'left'}))
            
        else:
            st.warning(f"{distance_threshold}km 이내에 화장실을 찾을 수 없습니다. 거리를 늘려보세요.")
    else:
        st.info("왼쪽 사이드바에서 주소를 입력하고 '내 위치로 화장실 찾기' 버튼을 눌러주세요.")

if __name__ == '__main__':
    app()
