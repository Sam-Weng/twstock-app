import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ==============================================================================
# 模組一：數據獲取與本地緩存模組
# ==============================================================================
# class DataManager:
    # """台灣股市數據管理模組"""
    # def __init__(self):
        # self.supported_stocks = {"2330": "台積電", "2454": "聯發科", "2317": "鴻海"}

    # def fetch_taiwan_stock_data(self, stock_id: str, days: int = 120) -> pd.DataFrame:
        # """獲取台股歷史 K 線數據（模擬生成，含隨機波動）"""
        # if stock_id not in self.supported_stocks:
            # return pd.DataFrame()
        
        # np.random.seed(int(stock_id))
        # end_date = datetime.now()
        # start_date = end_date - timedelta(days=days)
        # date_range = pd.date_range(start=start_date, end=end_date, freq='B')
        
        # base_price = 1000 if stock_id == "2330" else (600 if stock_id == "2454" else 180)
        # prices = base_price + np.cumsum(np.random.normal(0, base_price * 0.015, len(date_range)))
        
        # df = pd.DataFrame({
            # 'Date': date_range,
            # 'Stock_ID': stock_id,
            # 'Close': prices,
            # 'Open': prices * (1 + np.random.normal(0, 0.005, len(date_range))),
            # 'High': prices * (1 + np.abs(np.random.normal(0, 0.01, len(date_range)))),
            # 'Low': prices * (1 - np.abs(np.random.normal(0, 0.01, len(date_range)))),
            # 'Volume': np.random.randint(5000, 50000, len(date_range))
        # })
        # df.set_index('Date', inplace=True)
        # return df
import pandas as pd
import numpy as np
import requests
import twstock
from datetime import datetime, timedelta

class DataManager:
    """台灣股市數據管理模組 - 實接證交所 OpenAPI 與 twstock 歷史資料"""
    def __init__(self):
        # 定義 APP 預設支援的熱門測試標的
        self.supported_stocks = {"2330": "台積電", "2454": "聯發科", "2317": "鴻海", "5434": "崇越", "2495": "普安"}
        # 證交所 OpenAPI 的每日個股收盤行情 API 節點
        self.twse_openapi_url = "https://twse.com.tw"

    def _fetch_today_realtime(self, stock_id: str) -> dict:
        """從證交所 OpenAPI 獲取當日最新的收盤行情數據"""
        try:
            # 呼叫官方每日收盤 OpenAPI
            response = requests.get(self.twse_openapi_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # 篩選出特定代號的股票資料
                stock_data = next((item for item in data if item.get('Code') == stock_id), None)
                if stock_data:
                    return {
                        'Open': float(stock_data['OpeningPrice'].replace(',', '')),
                        'High': float(stock_data['HighestPrice'].replace(',', '')),
                        'Low': float(stock_data['LowestPrice'].replace(',', '')),
                        'Close': float(stock_data['ClosingPrice'].replace(',', '')),
                        'Volume': int(stock_data['TradeVolume'].replace(',', ''))
                    }
        except Exception as e:
            print(f"證交所 OpenAPI 連線異常 (可能為非交易時段): {e}")
        return None

    def fetch_taiwan_stock_data(self, stock_id: str, days: int = 120) -> pd.DataFrame:
        """透過 twstock 獲取歷史 K 線，並結合證交所 OpenAPI 最新數據"""
        if stock_id not in self.supported_stocks:
            return pd.DataFrame()
        
        try:
            # 1. 抓取歷史數據 (利用 twstock 爬取台灣證券交易所底層資料)
            stock = twstock.Stock(stock_id)
            # 動態推算需要抓取的月份數量 (大約每 30 天算一個月)
            months_needed = int(np.ceil(days / 30)) + 1
            now = datetime.now()
            
            # 取得歷史明細
            raw_history = []
            for m in range(months_needed):
                target_date = now - timedelta(days=m * 30)
                # 抓取該月份資料
                month_data = stock.fetch(target_date.year, target_date.month)
                raw_history.extend(month_data)
            
            # 2. 將 twstock 數據解析轉換成標準的 Pandas DataFrame
            data_list = []
            for item in raw_history:
                data_list.append({
                    'Date': item.date,
                    'Stock_ID': stock_id,
                    'Open': item.open,
                    'High': item.high,
                    'Low': item.low,
                    'Close': item.close,
                    'Volume': item.capacity
                })
            
            df = pd.DataFrame(data_list)
            # 移除重複日期並排序
            df.drop_duplicates(subset=['Date'], inplace=True)
            df.set_index('Date', inplace=True)
            df.sort_index(inplace=True)
            
            # 3. 補充當日最新即時數據：若當前最新一筆歷史資料不是今天，則調用證交所 OpenAPI 補齊
            today_date = datetime.now().date()
            if df.index[-1].date() != today_date:
                today_data = self._fetch_today_realtime(stock_id)
                if today_data:
                    today_df = pd.DataFrame([today_data], index=[pd.Timestamp(today_date)])
                    today_df['Stock_ID'] = stock_id
                    df = pd.concat([df, today_df])
            
            # 4. 依照使用者選擇的回溯天數切片輸出
            return df.tail(days)
            
        except Exception as e:
            # 網路斷線或證交所維護時的降級防禦機制 (回傳模擬數據確保 APP 不崩潰)
            print(f"真實數據獲取失敗，啟動本地防禦備援: {e}")
            return self._generate_mock_data(stock_id, days)

    def _generate_mock_data(self, stock_id: str, days: int) -> pd.DataFrame:
        """備援機制：生成高品質模擬數據"""
        np.random.seed(int(stock_id))
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')
        base_price = 1000 if stock_id == "2330" else (600 if stock_id == "2454" else 180)
        prices = base_price + np.cumsum(np.random.normal(0, base_price * 0.015, len(date_range)))
        df = pd.DataFrame({
            'Date': date_range, 'Stock_ID': stock_id, 'Close': prices,
            'Open': prices * (1 + np.random.normal(0, 0.005, len(date_range))),
            'High': prices * (1 + np.abs(np.random.normal(0, 0.01, len(date_range)))),
            'Low': prices * (1 - np.abs(np.random.normal(0, 0.01, len(date_range)))),
            'Volume': np.random.randint(5000, 50000, len(date_range))
        })
        df.set_index('Date', inplace=True)
        return df


# ==============================================================================
# 模組二：統計分析與指標計算模組
# ==============================================================================
# class StockAnalyzer:  ## 2026/05/24 13:35
    # """台股技術指標與統計分析模組"""
    # @staticmethod
    # def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        # """計算 MA、RSI 以及 KD 技術指標"""
        # if df.empty:
            # return df
        # df = df.copy()
        
        # # 1. 移動平均線 (MA)
        # df['MA5'] = df['Close'].rolling(window=5).mean()
        # df['MA20'] = df['Close'].rolling(window=20).mean()
        
        # # 2. 相對強弱指標 (RSI)
        # delta = df['Close'].diff()
        # gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        # loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        # rs = gain / (loss + 1e-10)
        # df['RSI14'] = 100 - (100 / (1 + rs))
        
        # # 3. 隨機指標 (KD 線)
        # low_min = df['Low'].rolling(window=9).min()
        # high_max = df['High'].rolling(window=9).max()
        # rsv = 100 * ((df['Close'] - low_min) / (high_max - low_min + 1e-10))
        
        # df['K'] = 50.0
        # df['D'] = 50.0
        # for i in range(1, len(df)):
            # if pd.isna(rsv.iloc[i]):
                # continue
            # df.loc[df.index[i], 'K'] = (2/3) * df['K'].iloc[i-1] + (1/3) * rsv.iloc[i]
            # df.loc[df.index[i], 'D'] = (2/3) * df['D'].iloc[i-1] + (1/3) * df['K'].iloc[i]
            
        # return df

class StockAnalyzer:
    """台股技術指標與統計分析模組（已補強布林通道）"""
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """計算 MA、RSI、KD 以及布林通道指標"""
        if df.empty:
            return df
        df = df.copy()
        
        # 1. 移動平均線 (MA)
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean() # 此處 20MA 即為布林中軌
        
        # 2. 布林通道計算 (20MA +/- 2倍標準差)
        std20 = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['MA20'] + (std20 * 2)
        df['BB_Lower'] = df['MA20'] - (std20 * 2)
        
        # 3. 相對強弱指標 (RSI)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-10)
        df['RSI14'] = 100 - (100 / (1 + rs))
        
        # 4. 隨機指標 (KD 線)
        low_min = df['Low'].rolling(window=9).min()
        high_max = df['High'].rolling(window=9).max()
        rsv = 100 * ((df['Close'] - low_min) / (high_max - low_min + 1e-10))
        
        df['K'] = 50.0
        df['D'] = 50.0
        for i in range(1, len(df)):
            if pd.isna(rsv.iloc[i]):
                continue
            df.loc[df.index[i], 'K'] = (2/3) * df['K'].iloc[i-1] + (1/3) * rsv.iloc[i]
            df.loc[df.index[i], 'D'] = (2/3) * df['D'].iloc[i-1] + (1/3) * df['K'].iloc[i]
            
        return df
        

# ==============================================================================
# 模組三：基準推薦與買賣訊號模組
# ==============================================================================
# class StrategyEngine:  ## 2026/05/24 13:35
    # """基準買賣決策推導引擎"""
    # @staticmethod
    # def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
        # """依據 MA 均線黃金/死亡交叉與 RSI 超買/超賣進行綜合判定"""
        # if df.empty or 'MA20' not in df.columns:
            # return df
        # df = df.copy()
        # df['Signal'] = '觀望 (Hold)'
        # df['Reason'] = '指標未達觸發基準'
        
        # for i in range(1, len(df)):
            # current_date = df.index[i]
            # if (df['MA5'].iloc[i-1] <= df['MA20'].iloc[i-1]) and (df['MA5'].iloc[i] > df['MA20'].iloc[i]):
                # if df['RSI14'].iloc[i] < 70:
                    # df.loc[current_date, 'Signal'] = '買入 (Buy)'
                    # df.loc[current_date, 'Reason'] = 'MA5黃金交叉突破MA20，且RSI未過熱'
            
            # elif (df['MA5'].iloc[i-1] >= df['MA20'].iloc[i-1]) and (df['MA5'].iloc[i] < df['MA20'].iloc[i]):
                # df.loc[current_date, 'Signal'] = '賣出 (Sell)'
                # df.loc[current_date, 'Reason'] = 'MA5死亡交叉跌破MA20'
                
            # elif df['RSI14'].iloc[i] > 80:
                # df.loc[current_date, 'Signal'] = '賣出 (Sell)'
                # df.loc[current_date, 'Reason'] = 'RSI指標大於80，市場過度超買'
                
            # elif df['RSI14'].iloc[i] < 20:
                # df.loc[current_date, 'Signal'] = '買入 (Buy)'
                # df.loc[current_date, 'Reason'] = 'RSI指標小於20，市場過度超賣'
                
        # return df

class StrategyEngine:
    """基準買賣決策推導引擎（優化：布林通道 + RSI 逆勢波策略）"""
    @staticmethod
    def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
        """綜合判定：動態上下軌突破與 RSI 強弱勢共振"""
        if df.empty or 'BB_Upper' not in df.columns:
            return df
        df = df.copy()
        df['Signal'] = '觀望 (Hold)'
        df['Reason'] = '指標未達觸發基準'
        
        for i in range(1, len(df)):
            current_date = df.index[i]
            close_price = df['Close'].iloc[i]
            rsi_val = df['RSI14'].iloc[i]
            
            # 【優化逆勢買入基準】：股價跌破布林下軌 且 RSI 處於低檔超賣區(<35)
            if (close_price <= df['BB_Lower'].iloc[i]) and (rsi_val < 35):
                df.loc[current_date, 'Signal'] = '買入 (Buy)'
                df.loc[current_date, 'Reason'] = f"股價跌破布林下軌(${close_price:.1f})，且RSI({rsi_val:.1f})極端超賣，觸發逆勢反彈訊號。"
            
            # 【優化逆勢賣出基準】：股價突破布林上軌 且 RSI 處於高檔超買區(>65)
            elif (close_price >= df['BB_Upper'].iloc[i]) and (rsi_val > 65):
                df.loc[current_date, 'Signal'] = '賣出 (Sell)'
                df.loc[current_date, 'Reason'] = f"股價衝破布林上軌(${close_price:.1f})，且RSI({rsi_val:.1f})過熱超買，觸發逢高鎖利訊號。"
                
            # 【輔助均線訊號】作為原策略的防守補充
            elif (df['MA5'].iloc[i-1] <= df['MA20'].iloc[i-1]) and (df['MA5'].iloc[i] > df['MA20'].iloc[i]) and (rsi_val < 60):
                df.loc[current_date, 'Signal'] = '買入 (Buy)'
                df.loc[current_date, 'Reason'] = 'MA5黃金交叉突破20MA中軌，趨勢轉強。'
                
            elif (df['MA5'].iloc[i-1] >= df['MA20'].iloc[i-1]) and (df['MA5'].iloc[i] < df['MA20'].iloc[i]):
                df.loc[current_date, 'Signal'] = '賣出 (Sell)'
                df.loc[current_date, 'Reason'] = 'MA5死亡交叉跌破20MA中軌，防守轉弱。'
                
        return df       

# ==============================================================================
# APP 介面與整合測試端
# ==============================================================================
st.set_page_config(page_title="台股智勝寶 APP 模擬環境", layout="wide")

st.title("📊 台灣股市統計分析與基準推薦系統")
st.caption("📱 專家級移動端 APP 核心邏輯與模擬測試面板")

# 實例化類別
dm = DataManager()
analyzer = StockAnalyzer()
engine = StrategyEngine()

st.sidebar.header("📱 APP 功能導航")
selected_stock_id = st.sidebar.selectbox(
    "選擇測試股票", 
    options=list(dm.supported_stocks.keys()),
    format_func=lambda x: f"{x} {dm.supported_stocks[x]}"
)
analysis_days = st.sidebar.slider("歷史數據回溯天數", min_value=30, max_value=180, value=90)

with st.spinner('🔄 正在同步台灣證券交易所即時報價並計算指標...'):
    raw_data = dm.fetch_taiwan_stock_data(selected_stock_id, days=analysis_days)
    analyzed_data = analyzer.calculate_indicators(raw_data)
    final_data = engine.generate_signals(analyzed_data)

if final_data.empty:
    st.error("無法取得數據，請檢查核心網路數據層。")
else:
    latest_data = final_data.iloc[-1]
    latest_date = final_data.index[-1].strftime('%Y-%m-%d')
    
    st.subheader(f"⚡ 即時基準推薦報告 ({latest_date})")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("當前股價", f"${latest_data['Close']:.2f}", f"{(latest_data['Close']-latest_data['Open'])/latest_data['Open']*100:.2f}%")
    
    sig = latest_data['Signal']
    if "買入" in sig:
        col2.success(f"建議行動：{sig}")
    elif "賣出" in sig:
        col2.error(f"建議行動：{sig}")
    else:
        col2.warning(f"建議行動：{sig}")
        
    col3.metric("RSI (14D)", f"{latest_data['RSI14']:.2f}")
    col4.metric("KD 隨機指標", f"K:{latest_data['K']:.1f} / D:{latest_data['D']:.1f}")
    
    st.info(f"💡 **基準觸發原因**：{latest_data['Reason']}")

    # st.subheader("📈 統計技術分析互動圖表")   ## 2026/05/24 13:15
    # fig = go.Figure()
    
    # fig.add_trace(go.Candlestick(
        # x=final_data.index,
        # open=final_data['Open'], high=final_data['High'],
        # low=final_data['Low'], close=final_data['Close'],
        # name='K線'
    # ))
    # fig.add_trace(go.Scatter(x=final_data.index, y=final_data['MA5'], name='5MA週線', line=dict(color='orange', width=1.5)))
    # fig.add_trace(go.Scatter(x=final_data.index, y=final_data['MA20'], name='20MA月線', line=dict(color='purple', width=1.5)))
    
    # fig.update_layout(title=f"{dm.supported_stocks[selected_stock_id]} 歷史趨勢與均線追蹤", xaxis_rangeslider_visible=False, height=450)
    # st.plotly_chart(fig, use_container_width=True)

    # st.subheader("📈 統計技術分析互動圖表（雙圖連動模式）")  ## 2026/05/24 13:40
    
    # # 引入 Plotly 的多圖模組
    # from plotly.subplots import make_subplots
    
    # # 建立雙圖架構：2列1行，主圖佔 70% 高度，副圖佔 30% 高度，並共享 X 軸(時間軸)
    # fig = make_subplots(
        # rows=2, cols=1, 
        # shared_xaxes=True, 
        # vertical_spacing=0.08,
        # row_heights=[0.7, 0.3]
    # )
    
    # # ==================== 【第 1 頁：主圖 - K線與均線】 ====================
    # # 1. K 線圖
    # fig.add_trace(go.Candlestick(
        # x=final_data.index,
        # open=final_data['Open'], high=final_data['High'],
        # low=final_data['Low'], close=final_data['Close'],
        # name='K線'
    # ), row=1, col=1)
    
    # # 2. 5MA 週線
    # fig.add_trace(go.Scatter(
        # x=final_data.index, y=final_data['MA5'], 
        # name='5MA週線', line=dict(color='orange', width=1.5)
    # ), row=1, col=1)
    
    # # 3. 20MA 月線
    # fig.add_trace(go.Scatter(
        # x=final_data.index, y=final_data['MA20'], 
        # name='20MA月線', line=dict(color='purple', width=1.5)
    # ), row=1, col=1)
    
    # # ==================== 【第 2 頁：副圖 - RSI 與 KD 指標】 ====================
    # # 1. RSI 14 天線
    # fig.add_trace(go.Scatter(
        # x=final_data.index, y=final_data['RSI14'], 
        # name='RSI14', line=dict(color='blue', width=1.5)
    # ), row=2, col=1)
    
    # # 2. KD 指標的 K 線
    # fig.add_trace(go.Scatter(
        # x=final_data.index, y=final_data['K'], 
        # name='K線(KD)', line=dict(color='red', width=1.2, dash='dot')
    # ), row=2, col=1)
    
    # # 3. KD 指標的 D 線
    # fig.add_trace(go.Scatter(
        # x=final_data.index, y=final_data['D'], 
        # name='D線(KD)', line=dict(color='green', width=1.2, dash='dot')
    # ), row=2, col=1)
    
    # # 4. 加入副圖的超買/超賣基準輔助線（RSI/KD 常見的 20 與 80 分界線）
    # fig.add_hline(y=80, line_dash="dash", line_color="red", line_width=1, row=2, col=1)
    # fig.add_hline(y=20, line_dash="dash", line_color="green", line_width=1, row=2, col=1)
    
    # # ==================== 【全域樣式與佈局調整】 ====================
    # fig.update_layout(
        # title=f"{dm.supported_stocks[selected_stock_id]} 綜合技術指標追蹤面板",
        # xaxis_rangeslider_visible=False, # 隱藏主圖下方的時間滑桿以釋放空間
        # height=650,                      # 放大整體畫布高度以利雙圖呈現
        # hovermode='x unified',           # 滑鼠滑過時，同一個 X 軸日期的數據全部整合顯示
        # legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1) # 讓圖例橫向排列在最上方
    # )
    
    # # 調整 Y 軸的名稱標籤
    # fig.update_yaxes(title_text="股票價格 (TWD)", row=1, col=1)
    # fig.update_yaxes(title_text="指標數值 (0-100)", row=2, col=1)
    
    # # 將繪製好的雙圖表渲染至 Streamlit APP 頁面上
    # st.plotly_chart(fig, use_container_width=True)

    st.subheader("📈 統計技術分析互動圖表（布林通道與雙圖連動模式）")
    
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3]
    )
    
    # ==================== 【第 1 頁：主圖 - K線、均線與布林通道】 ====================
    # 1. K 線圖
    fig.add_trace(go.Candlestick(
        x=final_data.index, open=final_data['Open'], high=final_data['High'],
        low=final_data['Low'], close=final_data['Close'], name='K線'
    ), row=1, col=1)
    
    # 2. 布林上軌 (用虛線呈現壓力)
    fig.add_trace(go.Scatter(
        x=final_data.index, y=final_data['BB_Upper'], 
        name='布林上軌(+2σ)', line=dict(color='red', width=1, dash='dash')
    ), row=1, col=1)
    
    # 3. 20MA中軌 (布林中軌)
    fig.add_trace(go.Scatter(
        x=final_data.index, y=final_data['MA20'], 
        name='20MA中軌(布林)', line=dict(color='purple', width=1.5)
    ), row=1, col=1)
    
    # 4. 布林下軌 (用虛線呈現支撐)
    fig.add_trace(go.Scatter(
        x=final_data.index, y=final_data['BB_Lower'], 
        name='布林下軌(-2σ)', line=dict(color='green', width=1, dash='dash')
    ), row=1, col=1)
    
    # 5. 5MA 週線
    fig.add_trace(go.Scatter(
        x=final_data.index, y=final_data['MA5'], 
        name='5MA週線', line=dict(color='orange', width=1)
    ), row=1, col=1)
    
    # ==================== 【第 2 頁：副圖 - RSI 與 KD 指標】 ====================
    fig.add_trace(go.Scatter(
        x=final_data.index, y=final_data['RSI14'], 
        name='RSI14', line=dict(color='blue', width=1.5)
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(
        x=final_data.index, y=final_data['K'], 
        name='K線(KD)', line=dict(color='gray', width=1, dash='dot')
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(
        x=final_data.index, y=final_data['D'], 
        name='D線(KD)', line=dict(color='silver', width=1, dash='dot')
    ), row=2, col=1)
    
    # RSI 的強弱界線
    fig.add_hline(y=65, line_dash="dot", line_color="orange", line_width=1, row=2, col=1)
    fig.add_hline(y=35, line_dash="dot", line_color="teal", line_width=1, row=2, col=1)
    
    # ==================== 【全域樣式與佈局調整】 ====================
    fig.update_layout(
        title=f"{dm.supported_stocks[selected_stock_id]} 布林逆勢操作策略面板",
        xaxis_rangeslider_visible=False,
        height=680,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_yaxes(title_text="股票價格 (TWD)", row=1, col=1)
    fig.update_yaxes(title_text="指標數值", row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 歷史訊號日誌（用於模擬回測審查）")
    log_df = final_data[['Close', 'MA5', 'MA20', 'RSI14', 'Signal', 'Reason']].tail(10)
    st.dataframe(log_df.style.highlight_max(axis=0, subset=['Close']))
