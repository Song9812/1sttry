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
    # 인코딩 오류 해결: 'cp494'를 'cp949'로 수정했습니다.
    # 만약 cp949로도 오류가 발생하면 'utf-8' 또는 'utf-8-sig'를 시도해보세요.
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
        if '24시간' in open_time_str or '상시' in open_time_str or '연중' in open_time_str:
            df.at[idx, '개방시간_시작'] = time(0, 0)
            df.at[idx, '개방시간_종료'] = time(23, 59, 59)
        elif '~' in open_time_str:
            try:
                start_str, end_str = open_time_str.split('~')
                
                start_time_obj = None
                end_time_obj = None

                # HH:MM 형식 시도
                try:
                    start_time_obj = datetime.strptime(start_str.strip(), '%H:%M').time()
                except ValueError:
                    pass
                if start_time_obj is None: # HHMM 형식 시도
                    try:
                        start_time_obj = datetime.strptime(start_str.strip(), '%H%M').time()
                    except ValueError:
                        pass
                
                try:
                    end_time_obj = datetime.strptime(end_str.strip(), '%H:%M').time()
                except ValueError:
                    pass
                if end_time_obj is None: # HHMM 형식 시도
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

# 3. 화장실 개방 여
