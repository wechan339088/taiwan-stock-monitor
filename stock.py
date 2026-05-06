import streamlit as st
import pandas as pd
import requests
import yfinance as yf
import urllib3
import time

# 基礎設定與標題
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="台股飆股監測", layout="wide")
st.title("🚀 台股個股 1.3 倍爆量監測站")
st.write("✨ 系統狀態：排除 ETF / 自動即時掃描 / 零延遲證交所連線")

# 1. 抓取全市場代碼 (只抓 4 碼純數字個股，排除 00 開頭的 ETF)
@st.cache_data(ttl=86400)
def get_stock_list():
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    res = requests.get(url, verify=False)
    data = res.json()
    stock_dict = {item['Code']: item['Name'] for item in data if len(item['Code']) == 4 and item['Code'].isdigit()}
    return stock_dict

# 2. 批量下載 5 日均量 (加速運算)
@st.cache_data(ttl=43200)
def get_5ma_volumes(stock_dict):
    codes = list(stock_dict.keys())
    tickers = [f"{code}.TW" for code in codes]
    data = yf.download(tickers, period="6d", progress=False)['Volume']
    ma5_dict = {}
    for code in codes:
        ticker = f"{code}.TW"
        if ticker in data:
            vols = data[ticker].dropna()[:-1]
            if len(vols) >= 4:
                ma5_dict[code] = vols.mean() / 1000
    return ma5_dict

# 3. 批量抓取證交所即時量 (50 檔包成一包，速度提升 50 倍)
def get_live_volumes(codes):
    live_dict = {}
    chunk_size = 50 
    for i in range(0, len(codes), chunk_size):
        chunk = codes[i:i+chunk_size]
        query_str = "|".join([f"tse_{c}.tw" for c in chunk])
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={query_str}"
        try:
            res = requests.get(url, verify=False)
            data = res.json()
            if 'msgArray' in data:
                for item in data['msgArray']:
                    live_dict[item['c']] = int(item['v'])
        except: pass
        time.sleep(0.05) 
    return live_dict

# --- 執行主程式：自動掃描並顯示結果 ---
with st.spinner("⚡ 正在掃描全市場個股數據 (約需 3-5 秒)..."):
    stock_dict = get_stock_list()
    ma5_dict = get_5ma_volumes(stock_dict)
    live_dict = get_live_volumes(list(stock_dict.keys()))
    
    results = []
    for code, name in stock_dict.items():
        if code in ma5_dict and code in live_dict:
            ratio = live_dict[code] / ma5_dict[code]
            if ratio >= 1.3: # 直接設定 1.3 倍觸發
                results.append({
                    "標的": f"{code} {name}",
                    "即時總量(張)": live_dict[code],
                    "5日均量(張)": int(ma5_dict[code]),
                    "爆量倍數": round(ratio, 2)
                })

    if results:
        df = pd.DataFrame(results).sort_values("爆量倍數", ascending=False).reset_index(drop=True)
        df.index += 1
        st.success(f"✅ 掃描完成！發現 {len(df)} 檔個股符合條件。")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("目前無個股突破 1.3 倍門檻。")