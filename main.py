import streamlit as st
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
from streamlit_folium import folium_static
from datetime import datetime, time
import urllib.parse # URL 인코딩을 위해 추가

# 1. 데이터 로드 및 전처리
@st.cache_data
def load_data(file_path):
    df = pd.read_csv(file_path, encoding='cp494') # 한글 인코딩 문제 해결을 위해 cp494 또는 utf-8-sig 시도
    df = df.rename(columns={'x 좌표': '경도', 'y 좌표': '위도'})
    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
    df.dropna(subset=['위도', '경도'], inplace=True)
    
    df['개방시간_시작'] = None
    df['개방시간_종료'] = None
    
    for idx, row in df.iterrows():
        open_time_str = str(row['개방시간']).strip()
        if '24시간' in open_time_str or '상시' in open_time_str or '연중' in open_time_str:
            df.at[idx, '개방시간_시작'] = time(0, 0)
            df.at[idx, '개방시간_종료'] = time(23, 59, 59)
        elif '~' in open_time_str:
            try:
                start_str, end_str = open_time_str.split('~')
                
                start_time_obj = None
                end_time_obj = None

                try:
                    start_time_obj = datetime.strptime(start_str.strip(), '%H:%M').time()
                except ValueError:
                    pass
                if start_time_obj is None:
                    try:
                        start_time_obj = datetime.strptime(start_str.strip(), '%H%M').time()
                    except ValueError:
                        pass
                
                try:
                    end_time_obj = datetime.strptime(end_str.strip(), '%H:%M').time()
                except ValueError:
                    pass
                if end_time_obj is None:
                    try:
                        end_time_obj = datetime.strptime(end_str.strip(), '%H%M').time()
                    except ValueError:
                        pass
                
                if start_time_obj and end_time_obj:
                    df.at[idx, '개방시간_시작'] = start_time_obj
                    df.at[idx, '개방시간_종료'] = end_time_obj
            except ValueError:
                pass 

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
    if start_time is None or end_time is None:
        return '불명'
    
    if start_time <= end_time:
        return '개방' if start_time <= current_time <= end_time else '폐쇄'
    else:
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
                st.
