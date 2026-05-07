import streamlit as st
import pandas as pd
import requests
import yfinance as yf
import urllib3
import datetime
import time

# 基本設定
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="台股 SMC 即時監測 Pro", layout="wide")

st.title("🔥 台股 SMC 即時動能監測站")
st.write("✨ 模式：本機極速連線 / 🛡️ 門檻：日量 > 450張 / ⏱️ 偵測首小時機構動能")

tab1, tab2, tab3 = st.tabs(["⚡ 即時 3 倍爆量", "⏱️ 開盤首小時動能 (1.5x)", "🚀 近 3 日漲幅排行"])

# 1. 抓取全市場代碼
@st.cache_data(ttl=86400)
def get_stock_list():
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    try:
        res = requests.get(url, verify=False, timeout=10)
        data = res.json()
        return {item['Code']: item['Name'] for item in data if len(item['Code']) == 4 and item['Code'].isdigit()}
    except: return {}

# 2. 獲取歷史日線與 60 分鐘線
@st.cache_data(ttl=3600)
def get_historical_base(stock_dict):
    if not stock_dict: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    codes = list(stock_dict.keys())
    tickers = [f"{code}.TW" for code in codes]
    
    # 下載歷史資料 (日線 & 小時線)
    df_d = yf.download(tickers, period="7d", progress=False)
    df_h = yf.download(tickers, period="5d", interval="60m", progress=False)
    
    vol_d = df_d['Volume'] if 'Volume' in df_d else pd.DataFrame()
    close_d = df_d['Close'] if 'Close' in df_d else pd.DataFrame()
    vol_h = df_h['Volume'] if 'Volume' in df_h else pd.DataFrame()
    
    return vol_d, vol_h, close_d

# 3. 證交所即時連線 (抓取即時量與即時價)
def get_live_data(codes):
    if not codes: return {}
    live_dict = {}
    for i in range(0, len(codes), 50):
        chunk = codes[i:i+50]
        query = "|".join([f"tse_{c}.tw" for c in chunk])
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={query}"
        try:
            res = requests.get(url, verify=False, timeout=5)
            d = res.json()
            if 'msgArray' in d:
                for item in d['msgArray']:
                    # c: 代碼, v: 累積量, z: 最近成交價
                    live_dict[item['c']] = {
                        'vol': int(item['v']) if item['v'] not in ['-', ''] else 0,
                        'price': float(item['z']) if item['z'] not in ['-', ''] else 0
                    }
        except: pass
        time.sleep(0.03) 
    return live_dict

with st.spinner("🚀 即時數據計算中..."):
    stock_dict = get_stock_list()
    daily_vol_df, hourly_vol_df, daily_close_df = get_historical_base(stock_dict)
    live_data = get_live_data(list(stock_dict.keys()))

# --- 分頁一：即時 3 倍爆量 ---
with tab1:
    r1 = []
    for code, name in stock_dict.items():
        ticker = f"{code}.TW"
        if code in live_data and ticker in daily_vol_df.columns:
            cur_v = live_data[code]['vol']
            cur_p = live_data[code]['price']
            hist_v = daily_vol_df[ticker].dropna()[:-1]
            hist_p_series = daily_close_df[ticker].dropna()
            
            if len(hist_v) >= 5 and cur_v >= 450:
                ma5 = hist_v.mean() / 1000
                ratio = cur_v / ma5 if ma5 > 0 else 0
                
                if ratio >= 3.0:
                    yest_p = float(hist_p_series.iloc[-1])
                    if cur_p == 0: cur_p = yest_p # 盤後防呆
                    change_pct = ((cur_p - yest_p) / yest_p) * 100
                    
                    r1.append({
                        "標的": f"{code} {name}",
                        "目前價格": f"{cur_p} ({change_pct:+.2f}%)",
                        "昨日收盤": yest_p,
                        "目前總量(張)": cur_v,
                        "5日均量(張)": int(ma5),
                        "爆量倍數": round(ratio, 2)
                    })
    if r1:
        st.success(f"⚡ 偵測到 {len(r1)} 檔極速爆量標的")
        st.dataframe(pd.DataFrame(r1).sort_values("爆量倍數", ascending=False).reset_index(drop=True), use_container_width=True)
    else: st.info("目前無符合 3 倍爆量標準的標的。")

# --- 分頁二：開盤首小時動能 (09:00 - 10:00) ---
with tab2:
    r2 = []
    for code, name in stock_dict.items():
        ticker = f"{code}.TW"
        if ticker in hourly_vol_df.columns and code in live_data:
            past_first_hours = hourly_vol_df[ticker].dropna()
            past_first_hours = past_first_hours[past_first_hours.index.hour == 9]
            
            if len(past_first_hours) >= 1:
                avg_first_hour = past_first_hours.mean()
                current_v = live_data[code]['vol']
                cur_p = live_data[code]['price']
                hist_p_series = daily_close_df[ticker].dropna()
                
                if avg_first_hour > 0 and current_v >= 450:
                    ratio = current_v / (avg_first_hour / 1000)
                    if ratio >= 1.5:
                        yest_p = float(hist_p_series.iloc[-1])
                        if cur_p == 0: cur_p = yest_p
                        change_pct = ((cur_p - yest_p) / yest_p) * 100
                        
                        r2.append({
                            "標的": f"{code} {name}",
                            "目前價格": f"{cur_p} ({change_pct:+.2f}%)",
                            "昨日收盤": yest_p,
                            "當前累積量(張)": current_v,
                            "歷史首小時均量(張)": int(avg_first_hour / 1000),
                            "動能倍數": round(ratio, 2)
                        })
    if r2:
        st.warning("⚠️ 這些個股已爆出異常能量 (Smart Money Alert)")
        st.dataframe(pd.DataFrame(r2).sort_values("動能倍數", ascending=False).reset_index(drop=True), use_container_width=True)
    else: st.info("目前尚未偵測到顯著的首小時開盤動能。")

# --- 分頁三：漲幅排行 ---
with tab3:
    r3 = []
    for code, name in stock_dict.items():
        ticker = f"{code}.TW"
        if code in live_data and ticker in daily_close_df.columns:
            cur_p = live_data[code]['price']
            hist_p = daily_close_df[ticker].dropna()
            if cur_p == 0 and len(hist_p) > 0: cur_p = float(hist_p.iloc[-1])
            if len(hist_p) >= 4 and cur_p > 0:
                old_p = float(hist_p.iloc[-4])
                pct = ((cur_p - old_p) / old_p) * 100
                r3.append({"標的": f"{code} {name}", "成交價": cur_p, "3日漲幅(%)": round(pct, 2)})
    if r3:
        st.dataframe(pd.DataFrame(r3).sort_values("3日漲幅(%)", ascending=False).reset_index(drop=True), use_container_width=True)
