import streamlit as st
import pandas as pd
import requests
import yfinance as yf
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="台股極速監測", layout="wide")

st.title("🔥 台股個股極速監測站 (雙引擎版)")
st.write("✨ 系統狀態：排除 ETF / 雙分頁設計 / 零延遲即時連線")

tab1, tab2 = st.tabs(["⚡ 第一頁：即時爆量監測 (大於1.3倍)", "🚀 第二頁：近3日漲幅排行"])

# 1. 抓取全市場代碼 (完全排除 ETF，只留 4 碼純數字個股)
@st.cache_data(ttl=86400)
def get_stock_list():
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    res = requests.get(url, verify=False)
    data = res.json()
    return {item['Code']: item['Name'] for item in data if len(item['Code']) == 4 and item['Code'].isdigit()}

# 2. 批量下載歷史資料 (5MA 與 漲跌幅一次算完，速度極快)
@st.cache_data(ttl=43200)
def get_historical_data(stock_dict):
    codes = list(stock_dict.keys())
    tickers = [f"{code}.TW" for code in codes]
    
    # 啟動黑科技：一次下載全市場歷史資料
    df = yf.download(tickers, period="6d", progress=False)
    
    ma5_dict = {}
    perf_dict = {}
    
    try:
        vol_df = df['Volume']
        close_df = df['Close']
        
        for code in codes:
            ticker = f"{code}.TW"
            if ticker in vol_df.columns and ticker in close_df.columns:
                # 計算 5MA
                vols = vol_df[ticker].dropna()[:-1]
                if len(vols) >= 4:
                    ma5_dict[code] = vols.mean() / 1000
                
                # 計算近 3 日漲幅
                closes = close_df[ticker].dropna()
                if len(closes) >= 4:
                    old_price = float(closes.iloc[-4])
                    latest_price = float(closes.iloc[-1])
                    if old_price > 0:
                        pct_change = ((latest_price - old_price) / old_price) * 100
                        perf_dict[code] = {
                            "old": old_price,
                            "new": latest_price,
                            "pct": pct_change
                        }
    except Exception:
        pass
        
    return ma5_dict, perf_dict

# 3. 批量抓取證交所即時量
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

# --- 主程式執行區 ---
with st.spinner("⚡ 系統極速運算中，正在載入全市場個股數據..."):
    stock_dict = get_stock_list()
    ma5_dict, perf_dict = get_historical_data(stock_dict)

# ================= 第一頁：爆量監測 =================
with tab1:
    live_dict = get_live_volumes(list(stock_dict.keys()))
    results = []
    for code, name in stock_dict.items():
        if code in ma5_dict and code in live_dict:
            ratio = live_dict[code] / ma5_dict[code]
            if ratio >= 1.3:
                results.append({
                    "標的": f"{code} {name}",
                    "即時總量(張)": live_dict[code],
                    "5日均量(張)": int(ma5_dict[code]),
                    "爆量倍數": round(ratio, 2)
                })
    if results:
        df1 = pd.DataFrame(results).sort_values("爆量倍數", ascending=False).reset_index(drop=True)
        df1.index += 1
        st.success(f"✅ 即時掃描完成！為您過濾出 {len(df1)} 檔大於 1.3 倍的個股。")
        st.dataframe(df1, use_container_width=True)
    else:
        st.info("目前無個股突破 1.3 倍門檻。")

# ================= 第二頁：漲幅排行 =================
with tab2:
    perf_results = []
    for code, name in stock_dict.items():
        if code in perf_dict:
            perf_results.append({
                "標的": f"{code} {name}",
                "3天前價格": round(perf_dict[code]["old"], 2),
                "最新價格": round(perf_dict[code]["new"], 2),
                "近3日漲幅(%)": round(perf_dict[code]["pct"], 2)
            })
    if perf_results:
        df2 = pd.DataFrame(perf_results).sort_values("近3日漲幅(%)", ascending=False).reset_index(drop=True)
        df2.index += 1
        st.success(f"✅ 波段掃描完成！為您列出全市場個股漲跌幅排行榜。")
        st.dataframe(df2, use_container_width=True)
    else:
        st.warning("資料載入中，請稍後再試。")
