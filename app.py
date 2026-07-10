import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import borsapy as bp
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import warnings
import gc
warnings.filterwarnings('ignore')

from backtest_engine import run_backtest, calc_stats, build_perf_chart, STRAT_LABELS, STRAT_COLORS
from sectors import (get_sector, get_theme_sectors, get_theme_info,
                     MACRO_THEMES, MACRO_THEMES_PRIMARY, MACRO_THEMES_SECONDARY,
                     SECTOR_MAP, ALL_SECTORS)
from membership import get_current_constituents, get_all_tickers_ever, check_for_updates_via_borsapy
from sector_summary import build_summary, build_sector_bar_chart, _sector_returns

# ── 1. MINIMAL UI AYARLARI ───────────────────────────────────────────────────
st.set_page_config(page_title="BIST Makro Tarayıcı", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background-color: #0a0a0a; color: #ededed; }
.main-header { font-size: 2.2rem; font-weight: 700; color: #ffffff; letter-spacing: -0.04em; margin-bottom: 0.2rem; }
.sub-header { font-size: 0.85rem; color: #888888; margin-bottom: 2rem; font-family: 'JetBrains Mono', monospace; }
.sec-title { font-size: 1.1rem; font-weight: 600; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #222; padding-bottom: 0.5rem; margin: 2rem 0 1rem 0; }
.mc { background: transparent; border: 1px solid #262626; border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem; transition: border-color 0.2s ease; }
.mc:hover { border-color: #404040; }
.ml { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.3rem; }
.mv { font-size: 1.1rem; font-weight: 600; color: #fff; font-family: 'JetBrains Mono', monospace; }
.pass { color: #10b981 !important; } 
.fail { color: #ef4444 !important; }
.stag { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.7rem; font-family: 'JetBrains Mono', monospace; background: #171717; border: 1px solid #262626; color: #a3a3a3; margin-left: 0.5rem; }
div[data-testid="stButton"] button { background-color: #171717 !important; border: 1px solid #333 !important; border-radius: 6px !important; color: #fff !important; transition: all 0.2s ease; }
div[data-testid="stButton"] button p { font-weight: 600 !important; font-size: 0.95rem !important; }
div[data-testid="stButton"] button:hover { background-color: #262626 !important; border-color: #555 !important; }
div[data-testid="stButton"] button[data-testid="baseButton-primary"] { background-color: #ededed !important; color: #0a0a0a !important; border: none !important; }
div[data-testid="stButton"] button[data-testid="baseButton-primary"] p { color: #0a0a0a !important; font-weight: 700 !important; }
div[data-testid="stButton"] button[data-testid="baseButton-primary"]:hover { background-color: #ffffff !important; opacity: 0.9; }
.stTextInput input, .stSelectbox div[data-baseweb="select"] { background-color: #171717 !important; color: #fff !important; border: 1px solid #333 !important; border-radius: 6px !important; }
</style>
""", unsafe_allow_html=True)

# CANLI TARAMA EVRENİ
try:
    BIST100_YF = [t+".IS" for t in get_current_constituents()]
except Exception as e:
    st.error(f"BIST100 listesi alınamadı: {e}")
    BIST100_YF = []

# BACKTEST EVRENİ
try:
    BIST100_ALL_TIME_YF = [t+".IS" for t in get_all_tickers_ever()]
except Exception as e:
    st.error(f"Tüm zamanların listesi alınamadı: {e}")
    BIST100_ALL_TIME_YF = []

# REVISION WARNING
try:
    REVISION_WARNING = check_for_updates_via_borsapy()
except:
    REVISION_WARNING = None

# ── 2. VERİ ÇEKME (OPTİMİZE EDİLMİŞ - MEMORY DOSTU) ────────────────────────
@st.cache_data(ttl=1800, show_spinner=False, max_entries=100)
def fetch_data(tickers, period, interval):
    data = {}
    progress = st.progress(0, "Hisse verileri çekiliyor...")
    for i, ticker in enumerate(tickers):
        try:
            df = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False, timeout=3)
            if df is not None and len(df) >= 55:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                for col in ['Open','High','Low','Close','Volume']:
                    if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df.dropna(subset=['Close'])
                if len(df) >= 55: data[ticker] = df
        except: pass
        if i % 10 == 0: 
            progress.progress(min((i+1)/len(tickers), 1.0), f"{i+1}/{len(tickers)} hisse")
            gc.collect()
    progress.empty()
    return data

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_single(ticker, period, interval):
    try:
        df = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False, timeout=3)
        if df is not None and len(df) > 10:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            for col in ['Open','High','Low','Close','Volume']:
                if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
            return df.dropna(subset=['Close'])
    except: pass
    return None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_benchmark(period, interval):
    try:
        df = yf.download("XU100.IS", period=period, interval=interval, auto_adjust=True, progress=False, timeout=3)
        if df is not None and len(df) > 0:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
            return df.dropna(subset=['Close'])
    except: pass
    return pd.DataFrame()

# ── 2b. TLREF (TCMB EVDS) ─────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_tl_rate_daily():
    try:
        tcmb = bp.TCMB()
        hist = tcmb.history("overnight")
        if hist is None or hist.empty:
            return pd.Series(dtype=float)
        hist.index = pd.to_datetime(hist.index)
        hist = hist.sort_index()
        rate = hist["lending"] if "lending" in hist.columns else hist.iloc[:, -1]
        rate = pd.to_numeric(rate, errors="coerce").dropna()
        if rate.empty:
            return pd.Series(dtype=float)
        full_idx = pd.date_range(rate.index.min(), datetime.now(), freq="D")
        daily = rate.reindex(full_idx).ffill().dropna()
        return daily
    except Exception:
        return pd.Series(dtype=float)

def _weekly_ohlc_from_series(s):
    if s is None or s.empty:
        return pd.DataFrame()
    w = s.resample("W-FRI").agg(["first", "max", "min", "last"])
    w.columns = ["Open", "High", "Low", "Close"]
    return w.dropna()

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_macro_rate_fallback():
    try:
        df = yf.download("^TNX", period="5y", interval="1wk", auto_adjust=True, progress=False, timeout=3)
        if df is not None and len(df) > 55:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            return df.dropna(subset=['Close'])
    except: pass
    return pd.DataFrame()

def get_tlref_weekly():
    daily = fetch_tl_rate_daily()
    weekly = _weekly_ohlc_from_series(daily)
    if len(weekly) >= 55:
        return weekly, "TCMB Gecelik (O/N) Faizi"
    fb = fetch_macro_rate_fallback()
    if not fb.empty:
        return fb, "Proxy (^TNX — ABD 10Y Tahvil)"
    return pd.DataFrame(), "Veri Yok"

# ── 3. MATEMATİK & İNDİKATÖRLER ───────────────────────────────────────────────
def _c(df): return df['Close'].squeeze().dropna()
def _h(df): return df['High'].squeeze().dropna()
def _l(df): return df['Low'].squeeze().dropna()
def _v(df): return df['Volume'].squeeze().dropna()

def sma(s, n): return s.rolling(n).mean() if len(s) >= n else pd.Series([np.nan]*len(s), index=s.index)
def ema(s, n): return s.ewm(span=n, adjust=False).mean() if len(s) >= n else pd.Series([np.nan]*len(s), index=s.index)

def rsi_calc(s, n=14):
    d = s.diff(); g = d.clip(lower=0).rolling(n).mean(); l = (-d.clip(upper=0)).rolling(n).mean()
    rs = g / l.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50)

def stoch(h, l, c, k=14, smooth=3, d=3):
    lo = l.rolling(k).min(); hi = h.rolling(k).max()
    raw = 100*(c-lo)/(hi-lo).replace(0, np.nan)
    ks = raw.rolling(smooth).mean().fillna(50)
    return ks, ks.rolling(d).mean().fillna(50)

def macd_calc(s, fast=12, slow=26, sig=9):
    m = ema(s,fast)-ema(s,slow); sg = ema(m.fillna(0), sig)
    return m, sg, m-sg

def atr_calc(h, l, c, n=14):
    tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

def vol_ratio(v, n=20):
    if len(v) < n+1: return np.nan
    avg = float(v.iloc[-n-1:-1].mean())
    return float(v.iloc[-1])/avg if avg > 0 else np.nan

def rs_score(c, bm_c, days=20):
    common = c.index.intersection(bm_c.index)
    if len(common) < days+1: return np.nan
    c2 = c.loc[common]; bm2 = bm_c.loc[common]
    return (float(c2.iloc[-1]/c2.iloc[-days]) - 1) - (float(bm2.iloc[-1]/bm2.iloc[-days]) - 1)

def calc_adx(h, l, c, n=14):
    up = h.diff(); down = -l.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(span=n, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=h.index).ewm(span=n, adjust=False).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm, index=h.index).ewm(span=n, adjust=False).mean() / atr)
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(span=n, adjust=False).mean()
    return adx, plus_di, minus_di

def calc_obv(c, v):
    direction = np.sign(c.diff())
    obv = (v * direction).cumsum()
    return obv

# ── 4. MAKRO REJİM MOTORU ─────────────────────────────────────────────────────
def get_macro_regime():
    try:
        df_rate, source = get_tlref_weekly()
        metrics = {"source": source, "is_plato": False}
        if df_rate.empty or len(df_rate) < 55:
            return "Bilinmiyor", [], metrics

        c = _c(df_rate); h = _h(df_rate); l = _l(df_rate)
        sma8_s = sma(c, 8); sma54_s = sma(c, 54)
        sma8 = float(sma8_s.iloc[-1]); sma54 = float(sma54_s.iloc[-1])
        adx, plus_di, minus_di = calc_adx(h, l, c)
        adx_val = float(adx.iloc[-1]); p_di = float(plus_di.iloc[-1]); m_di = float(minus_di.iloc[-1])

        last_val = float(c.iloc[-1])
        ret_2m = (last_val / float(c.iloc[-9]) - 1) if len(c) > 9 else np.nan
        ret_1y = (last_val / float(c.iloc[-53]) - 1) if len(c) > 53 else np.nan

        spread_pct = abs(sma8 - sma54) / sma54 * 100 if sma54 else 0.0
        is_plato = spread_pct < 3 and adx_val < 20

        metrics.update({
            "last": last_val, "sma8": sma8, "sma54": sma54,
            "adx": adx_val, "plus_di": p_di, "minus_di": m_di,
            "ret_2m": ret_2m, "ret_1y": ret_1y, "is_plato": is_plato,
        })

        if is_plato:
            regime = "Denge (Plato)"
            sectors = ["Ulaşım ve Turizm"]
        elif sma8 > sma54 and p_di > m_di and adx_val >= 20:
            regime = "Savunmacı (Risk Off — Faiz Yükseliyor)"
            sectors = ["Gıda ve Perakende", "İletişim", "Sağlık"]
        elif sma8 < sma54 and m_di > p_di and adx_val >= 20:
            regime = "Büyüme (Risk On — Faiz Düşüyor)"
            sectors = ["Banka", "GYO", "İnşaat Malzemeleri", "Holding",
                       "Otomotiv", "Sanayi ve Kimya", "Teknoloji", "Enerji",
                       "Faktoring ve Finansal Kiralama"]
        else:
            regime = "Denge (Plato)"
            sectors = ["Ulaşım ve Turizm"]

        return regime, sectors, metrics
    except Exception as e:
        return "Hata", [], {"source": "Hata", "error": str(e)}

CURRENT_REGIME, REGIME_SECTORS, REGIME_METRICS = get_macro_regime()

# ── 5. STRATEJİLER ────────────────────────────────────────────────────────────
def score_emre(df, bm_df, ticker=None):
    try:
        c = _c(df); v = _v(df)
        if len(c) < 55: return 0, 5, {}, {}
        bm = _c(bm_df) if not bm_df.empty else pd.Series(dtype=float)

        price = float(c.iloc[-1])
        s20 = float(sma(c,20).iloc[-1])
        s50 = float(sma(c,50).iloc[-1])
        rsi_v = float(rsi_calc(c).iloc[-1])
        rs = rs_score(c, bm, 20)
        vr = vol_ratio(v, 20)

        sector = get_sector(ticker) if ticker else ""
        is_macro_aligned = sector in REGIME_SECTORS

        criteria = {
            "RS Pozitif (20g vs BIST)": (not np.isnan(rs) and rs > 0, f"{rs*100:.1f}%" if not np.isnan(rs) else "N/A"),
            "SMA20 & SMA50 Üstünde": (price > s20 and price > s50, f"{price:.2f} > {s20:.2f}/{s50:.2f}"),
            "Hacim Ort. Üstünde": (not np.isnan(vr) and vr >= 0.9, f"{vr:.2f}x" if not np.isnan(vr) else "N/A"),
            "RSI < 80": (rsi_v < 80, f"RSI={rsi_v:.1f}"),
            "Makro Rüzgar (+1)": (is_macro_aligned, f"{sector} ({CURRENT_REGIME})")
        }
        details = { "Fiyat": f"{price:.2f} ₺", "SMA 20": f"{s20:.2f}", "SMA 50": f"{s50:.2f}", "RSI (14)": f"{rsi_v:.1f}", "Hacim Oran": f"{vr:.2f}x" }
        sc = sum(1 for p,_ in criteria.values() if p)
        return sc, 5, criteria, details
    except Exception as e: return 0, 5, {"Hata": (False, str(e))}, {}

def score_claude(df, bm_df, ticker=None):
    try:
        c = _c(df); h = _h(df); l = _l(df); v = _v(df)
        if len(c) < 55: return 0, 7, {}, {}
        bm = _c(bm_df) if not bm_df.empty else pd.Series(dtype=float)

        price = float(c.iloc[-1])
        s50 = float(sma(c, 50).iloc[-1])
        rsi_v = float(rsi_calc(c).iloc[-1])

        lookback_peak = min(len(c), 126)
        high_6m = float(c.iloc[-lookback_peak:].max())
        dist_from_high = ((high_6m - price) / high_6m * 100) if high_6m > 0 else np.nan

        avg_vol_20 = float(v.iloc[-20:].mean()) if len(v) >= 20 else np.nan
        avg_vol_63 = float(v.iloc[-63:].mean()) if len(v) >= 63 else np.nan
        vol_confirm = (not np.isnan(avg_vol_20)) and (not np.isnan(avg_vol_63)) and \
                      avg_vol_63 > 0 and avg_vol_20 >= avg_vol_63
        vr_display = (avg_vol_20 / avg_vol_63) if (not np.isnan(avg_vol_20) and not np.isnan(avg_vol_63) and avg_vol_63 > 0) else np.nan

        ret_63 = (price / float(c.iloc[-64]) - 1) * 100 if len(c) > 64 else np.nan
        daily_rets_63 = c.pct_change().iloc[-63:] if len(c) > 64 else pd.Series(dtype=float)
        vol_63 = float(daily_rets_63.std() * 100) if len(daily_rets_63.dropna()) > 10 else np.nan
        trend_quality = (ret_63 / (vol_63 * (63 ** 0.5))) \
            if (not np.isnan(vol_63) and vol_63 > 0 and not np.isnan(ret_63)) else np.nan

        rs_180 = rs_score(c, bm, 126)

        sector = get_sector(ticker) if ticker else ""
        is_macro_aligned = sector in REGIME_SECTORS

        criteria = {
            "Temel Trend (Fiyat > SMA50)": (price > s50, f"{price:.2f} > {s50:.2f}"),
            "Sağlıklı RSI (40-70)": (not np.isnan(rsi_v) and 40 <= rsi_v <= 70, f"RSI={rsi_v:.1f}"),
            "6 Ay Zirvesine Yakınlık (≤%20)": (not np.isnan(dist_from_high) and dist_from_high <= 20, f"{dist_from_high:.1f}%" if not np.isnan(dist_from_high) else "N/A"),
            "Hacim Teyidi (20g ≥ 3 Aylık Ort.)": (vol_confirm, f"{vr_display:.2f}x" if not np.isnan(vr_display) else "N/A"),
            "Trend Kalitesi (Getiri/Oynaklık)": (not np.isnan(trend_quality) and trend_quality > 0.3, f"{trend_quality:.2f}" if not np.isnan(trend_quality) else "N/A"),
            "6 Aylık Göreceli Güç (vs BIST100)": (not np.isnan(rs_180) and rs_180 > 0, f"{rs_180*100:+.1f}%" if not np.isnan(rs_180) else "N/A"),
            "Faiz Rejimi Uyumu": (is_macro_aligned, f"{sector} ({CURRENT_REGIME})"),
        }
        details = {
            "Fiyat": f"{price:.2f} ₺", "SMA 50": f"{s50:.2f}", "RSI (14)": f"{rsi_v:.1f}",
            "6A Zirveye Uzaklık": f"{dist_from_high:.1f}%" if not np.isnan(dist_from_high) else "N/A",
            "Trend Kalitesi": f"{trend_quality:.2f}" if not np.isnan(trend_quality) else "N/A",
            "6A Göreceli Güç": f"{rs_180*100:+.1f}%" if not np.isnan(rs_180) else "N/A",
        }
        sc = sum(1 for p, _ in criteria.values() if p)
        return sc, 7, criteria, details
    except Exception as e:
        return 0, 7, {"Hata": (False, str(e))}, {}

def score_qwen(df, bm_df, ticker=None, sector_strength_map=None):
    try:
        c = _c(df); v = _v(df)
        if len(c) < 55: return 0, 5, {}, {}
        bm = _c(bm_df) if not bm_df.empty else pd.Series(dtype=float)
        
        sector = get_sector(ticker) if ticker else "Diğer"
        
        sector_rs = sector_strength_map.get(sector, np.nan) if sector_strength_map else np.nan
        top_3_sectors = []
        if sector_strength_map:
            sorted_sectors = sorted(sector_strength_map.items(), key=lambda x: x[1] if not np.isnan(x[1]) else -999, reverse=True)
            top_3_sectors = [s for s, _ in sorted_sectors[:3]]
        
        sector_strong = (not np.isnan(sector_rs)) and (sector_rs > 0) and (sector in top_3_sectors)
        
        obv = calc_obv(c, v)
        if len(obv) >= 11:
            obv_10g_change = (float(obv.iloc[-1]) / float(obv.iloc[-11]) - 1) * 100 if float(obv.iloc[-11]) != 0 else 0
            price_10g_change = (float(c.iloc[-1]) / float(c.iloc[-11]) - 1) * 100 if float(c.iloc[-11]) != 0 else 0
            smart_money = (obv_10g_change > 5) and (-2 <= price_10g_change <= 2)
        else:
            smart_money = False
            obv_10g_change = np.nan
            price_10g_change = np.nan
        
        avg_vol_5 = float(v.iloc[-5:].mean()) if len(v) >= 5 else np.nan
        avg_vol_20 = float(v.iloc[-20:].mean()) if len(v) >= 20 else np.nan
        vol_breakout = (not np.isnan(avg_vol_5)) and (not np.isnan(avg_vol_20)) and (avg_vol_20 > 0) and (avg_vol_5 >= 1.5 * avg_vol_20)
        vol_ratio_val = (avg_vol_5 / avg_vol_20) if (not np.isnan(avg_vol_5) and not np.isnan(avg_vol_20) and avg_vol_20 > 0) else np.nan
        
        rs_20 = rs_score(c, bm, 20)
        rs_strong = (not np.isnan(rs_20)) and (rs_20 > 0.05)
        
        is_macro_aligned = sector in REGIME_SECTORS
        
        criteria = {
            "Sektör Gücü (En Güçlü 3)": (sector_strong, f"{sector} RS:{sector_rs*100:.1f}%" if not np.isnan(sector_rs) else "N/A"),
            "Smart Money (OBV ↑, Fiyat →)": (smart_money, f"OBV:{obv_10g_change:+.1f}%, Fiyat:{price_10g_change:+.1f}%" if not np.isnan(obv_10g_change) else "N/A"),
            "Hacim Kırılımı (5g ≥ 1.5x 20g)": (vol_breakout, f"{vol_ratio_val:.2f}x" if not np.isnan(vol_ratio_val) else "N/A"),
            "Rölatif Güç (20g ≥ %5)": (rs_strong, f"{rs_20*100:+.1f}%" if not np.isnan(rs_20) else "N/A"),
            "Makro Uyumu": (is_macro_aligned, f"{sector} ({CURRENT_REGIME})"),
        }
        
        details = {
            "Sektör": sector,
            "Sektör RS (21g)": f"{sector_rs*100:+.1f}%" if not np.isnan(sector_rs) else "N/A",
            "OBV Değişim (10g)": f"{obv_10g_change:+.1f}%" if not np.isnan(obv_10g_change) else "N/A",
            "Hacim Oran (5g/20g)": f"{vol_ratio_val:.2f}x" if not np.isnan(vol_ratio_val) else "N/A",
            "RS vs BIST (20g)": f"{rs_20*100:+.1f}%" if not np.isnan(rs_20) else "N/A",
        }
        
        sc = sum(1 for p, _ in criteria.values() if p)
        return sc, 5, criteria, details
        
    except Exception as e:
        return 0, 5, {"Hata": (False, str(e))}, {}

STRATEGY_FN = {
    "emre": (score_emre, "Emre'nin Makro Stratejisi"),
    "claude": (score_claude, "Faiz Pusulası Stratejisi"),
    "qwen": (score_qwen, "Qwen'in Alfa Motoru"),
}

STRATEGY_MIN_SCORE = {"claude": 5, "qwen": 4}
STRATEGY_TARGET_RANGE = {"claude": (4, 5), "qwen": (4, 5)}

def _pick_portfolio(sorted_results, strategy, max_n=5, max_per_sector=2):
    def _fill(pool, limit):
        picked, sector_counts = [], {}
        for r in pool:
            sect = r.get('sector') or get_sector(r['ticker'])
            if sector_counts.get(sect, 0) < max_per_sector:
                picked.append(r); sector_counts[sect] = sector_counts.get(sect, 0) + 1
            if len(picked) == limit: break
        return picked

    min_score = STRATEGY_MIN_SCORE.get(strategy)
    if min_score is None:
        return _fill(sorted_results, max_n)

    target_min, target_max = STRATEGY_TARGET_RANGE.get(strategy, (max_n, max_n))
    qualified = [r for r in sorted_results if r['score'] >= min_score]
    picked = _fill(qualified, target_max)
    if len(picked) < target_min:
        relaxed = [r for r in sorted_results if r['score'] >= max(min_score - 1, 0)]
        picked = _fill(relaxed, target_min)
    return picked

# ── 6. GRAFİKLER ──────────────────────────────────────────────────────────────
def build_chart(df, ticker, interval):
    c = _c(df); h = _h(df); l = _l(df); v = _v(df); o = df['Open'].squeeze()
    s20 = sma(c,20); s50 = sma(c,50); ml, sl, hl_s = macd_calc(c)

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.60, 0.20, 0.20], vertical_spacing=0.03)

    fig.add_trace(go.Candlestick(x=df.index, open=o, high=h, low=l, close=c, name="Fiyat", increasing_fillcolor="#10b981", increasing_line_color="#10b981", decreasing_fillcolor="#ef4444", decreasing_line_color="#ef4444"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=s20, name="SMA 20", line=dict(color="#38bdf8",width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=s50, name="SMA 50", line=dict(color="#f59e0b",width=1.5)), row=1, col=1)

    bar_colors = ["#10b981" if x>=0 else "#ef4444" for x in hl_s.fillna(0)]
    fig.add_trace(go.Bar(x=df.index, y=hl_s, name="MACD Hist", marker_color=bar_colors, opacity=0.7), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=ml, name="MACD", line=dict(color="#38bdf8",width=1.5)), row=2, col=1)
    
    vcols = ["#10b981" if float(cv)>=float(ov) else "#ef4444" for cv,ov in zip(c.values, o.reindex(c.index).fillna(c).values)]
    fig.add_trace(go.Bar(x=df.index, y=v, name="Hacim", marker_color=vcols, opacity=0.5), row=3, col=1)

    fig.update_layout(height=600, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="JetBrains Mono", color="#a3a3a3", size=11), margin=dict(l=0,r=0,t=30,b=0), xaxis_rangeslider_visible=False, title=dict(text=f"<b>{ticker.replace('.IS','')}</b>", font=dict(color="#fff",size=14), x=0.01), hovermode="x unified", legend=dict(orientation="h", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"))
    for i in range(1,4):
        fig.update_xaxes(gridcolor="#1e1e1e", showgrid=True, row=i, col=1)
        fig.update_yaxes(gridcolor="#1e1e1e", showgrid=True, row=i, col=1)
    return fig

def build_tlref_chart(df):
    c = _c(df); h = _h(df); l = _l(df); o = df['Open'].squeeze()
    s8 = sma(c, 8); s54 = sma(c, 54)
    adx, p_di, m_di = calc_adx(h, l, c)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.65, 0.35], vertical_spacing=0.04)
    
    fig.add_trace(go.Candlestick(x=df.index, open=o, high=h, low=l, close=c, name="TLREF (Haftalık)", increasing_fillcolor="#10b981", increasing_line_color="#10b981", decreasing_fillcolor="#ef4444", decreasing_line_color="#ef4444"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=s8, name="SMA 8 (Kısa)", line=dict(color="#38bdf8",width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=s54, name="SMA 54 (Uzun)", line=dict(color="#f59e0b",width=1.5)), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=adx, name="ADX (Trend Gücü)", line=dict(color="#fff", width=2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=p_di, name="D+ (Alıcı)", line=dict(color="#10b981", width=1.5, dash="dot")), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=m_di, name="D- (Satıcı)", line=dict(color="#ef4444", width=1.5, dash="dot")), row=2, col=1)
    fig.add_hline(y=20, line_dash="dash", line_color="#555", row=2, col=1, annotation_text="ADX 20 (Trend Eşiği)", annotation_font_color="#888", annotation_font_size=10)
    
    fig.update_layout(height=500, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="JetBrains Mono", color="#a3a3a3", size=11), margin=dict(l=0,r=0,t=30,b=0), xaxis_rangeslider_visible=False, hovermode="x unified", legend=dict(orientation="h", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(gridcolor="#1e1e1e", showgrid=True); fig.update_yaxes(gridcolor="#1e1e1e", showgrid=True)
    return fig

def render_detail(result, strategy, interval):
    ticker_label = result["ticker"].replace(".IS","")
    sector = result.get("sector", get_sector(result["ticker"]))
    
    st.markdown(f"### {ticker_label} <span class='stag'>{sector}</span> `{result['score']}/{result['max_score']}`", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    for i,(k,(passed,val)) in enumerate(result["criteria"].items()):
        icon="✅" if passed else "❌"
        col="pass" if passed else "fail"
        (c1 if i%2==0 else c2).markdown(f'<div class="mc"><div class="ml">{k}</div><div class="mv {col}">{icon} {val}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-title">📈 Grafik Analizi</div>', unsafe_allow_html=True)
    st.plotly_chart(build_chart(result["df"], result["ticker"], interval), use_container_width=True, config={"displayModeBar":False})

# ── 7. UYGULAMA YÜKLEME VE SESSION STATE ──────────────────────────────────────
st.markdown('<div class="main-header">BIST Makro Tarayıcı</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-header">{datetime.now().strftime("%d.%m.%Y")} · {len(BIST100_YF)} Hisse</div>', unsafe_allow_html=True)
if REVISION_WARNING:
    st.warning(f"️ {REVISION_WARNING}")

if "strategy" not in st.session_state: st.session_state.strategy = "emre"
if "selected_ticker" not in st.session_state: st.session_state.selected_ticker = None
if "scan_done" not in st.session_state: st.session_state.scan_done = False
if "results" not in st.session_state: st.session_state.results = []
if "page" not in st.session_state: st.session_state.page = "scanner"
if "bt_done" not in st.session_state: st.session_state.bt_done = False
if "bt_results" not in st.session_state: st.session_state.bt_results = {}

# ── 8. SOL MENÜ (SIDEBAR) ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Ayarlar")
    interval = st.selectbox("Zaman Dilimi", ["1d","1wk"], format_func=lambda x: "Günlük (1D)" if x=="1d" else "Haftalık (1W)")
    period = "9mo" if interval == "1d" else "3y"

    st.markdown("---")
    st.markdown("### 🔍 Hisse Ara")
    search_input = st.text_input("Ticker", placeholder="Örn: GARAN").upper().strip()
    if st.button("Ara", use_container_width=True):
        st.session_state.page = "search"
        st.session_state.search_ticker = search_input
        st.rerun()

    st.markdown("---")
    st.markdown("###  Makro Menü")
    if st.button("🏦 TLREF & Faiz Analizi", use_container_width=True):
        st.session_state.page = "tlref"
        st.rerun()
        
    all_themes = ["— Temalar —"] + list(MACRO_THEMES_PRIMARY.keys()) + ["──────"] + list(MACRO_THEMES_SECONDARY.keys())
    macro_theme = st.selectbox("Tema Seç", all_themes, label_visibility="collapsed")
    if st.button("Temaya Göre Tara", use_container_width=True):
        if macro_theme not in ["— Temalar —","──────"]:
            st.session_state.page = "macro"
            st.session_state.macro_theme = macro_theme
            st.rerun()

    st.markdown("---")
    if st.button("📊 Portföy Backtest", use_container_width=True, type="primary"):
        st.session_state.page = "perf"
        st.rerun()
    if st.button("🏭 Sektör Özeti", use_container_width=True):
        st.session_state.page = "sektor"
        st.rerun()

    st.markdown("---")
    st.markdown("### 🧭 Stratejiler")
    if st.button("🟠 Emre'nin Makro Stratejisi", use_container_width=True):
        st.session_state.strategy = "emre"
        st.session_state.page = "scanner"
        st.session_state.scan_done = False
        st.session_state.results = []
        st.session_state.selected_ticker = None
        st.rerun()
    if st.button("🔵 Faiz Pusulası Stratejisi", use_container_width=True):
        st.session_state.strategy = "claude"
        st.session_state.page = "scanner"
        st.session_state.scan_done = False
        st.session_state.results = []
        st.session_state.selected_ticker = None
        st.rerun()
    if st.button(" Qwen'in Alfa Motoru", use_container_width=True):
        st.session_state.strategy = "qwen"
        st.session_state.page = "scanner"
        st.session_state.scan_done = False
        st.session_state.results = []
        st.session_state.selected_ticker = None
        st.rerun()

# ── 9. SAYFALAR ──────────────────────────────────────────────────────────────

if st.session_state.page == "tlref":
    st.markdown("## 🏦 TLREF & Makroekonomik Faiz Motoru")
    st.markdown("Haftalık periyotta faiz trendini (SMA 8/54) ve yön şiddetini (ADX, D+/D-) analiz eder.")
    st.markdown("---")

    try:
        df_rate, tlref_source = get_tlref_weekly()

        if df_rate.empty or len(df_rate) < 55:
            st.error("❌ Faiz verisi çekilemedi. TCMB kaynağına şu an ulaşılamıyor olabilir, birazdan tekrar dene.")
        else:
            if "Proxy" in tlref_source:
                st.warning(f"️ TCMB faiz verisine ulaşılamadı, yön fikri için yedek gösterge kullanılıyor: **{tlref_source}**.")
            else:
                st.success(f"✅ Veri kaynağı: **{tlref_source}**")

            c1, c2 = st.columns([2, 1])
            with c1:
                st.plotly_chart(build_tlref_chart(df_rate), use_container_width=True, config={"displayModeBar":False})
            with c2:
                m = REGIME_METRICS
                rc = "#10b981" if "On" in CURRENT_REGIME else "#ef4444" if "Off" in CURRENT_REGIME else "#f59e0b"
                if m.get("is_plato"):
                    plato_badge = "🟡 PLATO — YATAY SEYİR"
                elif m.get("sma8", 0) > m.get("sma54", 0):
                    plato_badge = "🔴 FAİZ YÜKSELİŞTE"
                else:
                    plato_badge = "🟢 FAİZ DÜŞÜŞTE"

                st.markdown(f"""<div style='border:1px solid #333; padding:20px; border-radius:8px; background:#111; text-align:center;'>
<h4 style='margin:0; color:#888; font-size:0.9rem;'>Motorun Algıladığı Rejim</h4>
<h2 style='margin:10px 0; color:{rc}; font-size:1.5rem;'>{CURRENT_REGIME}</h2>
<div class='stag'>{plato_badge}</div>
<p style='color:#a3a3a3; font-size:0.8rem; margin-top:10px;'>D+ ve D- kesişimleri, ADX trend gücü ve SMA 8/54 periyotları ile hesaplanır.</p>
</div>""", unsafe_allow_html=True)

                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                mc1, mc2 = st.columns(2)
                mc1.metric("Güncel Faiz", f"%{m.get('last', float('nan')):.2f}" if m.get('last') is not None else "N/A")
                mc2.metric("ADX (Trend Gücü)", f"{m.get('adx', float('nan')):.1f}" if m.get('adx') is not None else "N/A")

                mc3, mc4 = st.columns(2)
                r2m = m.get("ret_2m", np.nan); r1y = m.get("ret_1y", np.nan)
                mc3.metric("2 Aylık Değişim", f"{r2m*100:+.2f}%" if r2m is not None and not np.isnan(r2m) else "N/A")
                mc4.metric("1 Yıllık Değişim", f"{r1y*100:+.2f}%" if r1y is not None and not np.isnan(r1y) else "N/A")

            st.markdown("### 🟢 Mevcut Rejimden Olumlu Etkilenen Hisseler")
            st.markdown(f"**Desteklenen Sektörler:** {', '.join(REGIME_SECTORS) if REGIME_SECTORS else 'Belirlenemedi'}")

            theme_tickers = [t+".IS" for t, s in SECTOR_MAP.items() if s in REGIME_SECTORS]
            with st.spinner("Hisseler taranıyor..."):
                bm_df = fetch_benchmark(period, interval)
                td = fetch_data(theme_tickers, period, interval)
            
            rows = []
            for ticker, df_t in td.items():
                if df_t is None or len(df_t) < 55: continue
                sc_e, mx_e, _, _ = score_emre(df_t, bm_df, ticker)
                c_t = _c(df_t); bm_t = _c(bm_df)
                rs = rs_score(c_t, bm_t, 20)
                rows.append({'Hisse': ticker.replace('.IS',''), 'Sektör': get_sector(ticker), 'Emre Skoru': f"{sc_e}/{mx_e}", 'RS (20g)': f"{rs*100:.1f}%" if not np.isnan(rs) else "N/A", '_es': sc_e})
            
            if rows:
                df_rows = pd.DataFrame(rows).sort_values('_es', ascending=False).drop(columns=['_es'])
                st.dataframe(df_rows, use_container_width=True, height=400)
            else:
                st.info("Bu rejime uygun hisse bulunamadı.")
    except Exception as e:
        st.error(f"TLREF sayfasında hata: {e}")

elif st.session_state.page == "search":
    ticker_q = st.session_state.get("search_ticker","")
    ticker_yf = ticker_q+".IS"
    st.markdown(f"## 🔍 {ticker_q} Analizi")
    sector = get_sector(ticker_yf)
    st.markdown(f"**Sektör:** `{sector}`")

    with st.spinner("Veri çekiliyor..."):
        df_s = fetch_single(ticker_yf, period, interval)
        bm_df = fetch_benchmark(period, interval)

    if df_s is None or len(df_s) < 22:
        st.error("❌ Yeterli veri bulunamadı. Ticker doğru mu?")
        if st.button("Geri Dön"): st.session_state.page = "scanner"; st.rerun()
        st.stop()

    c1, c2, c3 = st.columns(3)
    for col, sk in [(c1, "emre"), (c2, "claude"), (c3, "qwen")]:
        with col:
            fn, label = STRATEGY_FN[sk]
            st.markdown(f"### {label}")
            sector_strength_map = None
            if sk == "qwen":
                sector_strength_map = {}
                for sect in ALL_SECTORS:
                    sector_strength_map[sect] = 0.0
            
            sc, mx, crit, det = fn(df_s, bm_df, ticker_yf, sector_strength_map=sector_strength_map) if sk == "qwen" else fn(df_s, bm_df, ticker_yf)
            color = "#10b981" if sc==mx else ("#f59e0b" if sc>=mx-1 else "#ef4444")
            st.markdown(f"**Skor:** <span style='color:{color};font-size:1.3rem;font-weight:700'>{sc}/{mx}</span>", unsafe_allow_html=True)
            for k,(passed,val) in crit.items():
                icon, cc = ("✅", "pass") if passed else ("❌", "fail")
                st.markdown(f'<div class="mc"><div class="ml">{k}</div><div class="mv {cc}">{icon} {val}</div></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.plotly_chart(build_chart(df_s, ticker_yf, interval), use_container_width=True, config={"displayModeBar":False})

elif st.session_state.page == "sektor":
    st.markdown("## 🏭 BİST Sektörel Özet")
    st.markdown("---")
    with st.spinner("Sektör verileri hesaplanıyor..."):
        stock_s = fetch_data(BIST100_YF,"3mo","1d")

    summary = build_summary(stock_s)
    CAT_STYLE = {
        "🚀 SON KAPANIŞ LİDERİ": ("#064e3b","#10b981"), "⚡ İVME KAZANAN": ("#064e3b","#34d399"),
        "📈 1 HAFTA ZİRVE": ("#064e3b","#6ee7b7"), "🏆 1 AY ZİRVE": ("#064e3b","#a7f3d0"),
        "🔄 TOPARLAYAN": ("#14532d","#86efac"), "📉 SON KAPANIŞTA GERİDE": ("#7f1d1d","#ef4444"),
        "❄️ 1 HAFTA DİP": ("#7f1d1d","#f87171"), " 1 AY DİP": ("#7f1d1d","#fca5a5"),
        "🐌 YAVAŞLAYAN": ("#431407","#fb923c"),
    }

    def cat_card(title, items, bg, border):
        rows=""
        for sect,val in items:
            vc="#10b981" if val.startswith("+") else "#ef4444" if val.startswith("-") else "#a3a3a3"
            rows+=f'<div style="display:flex;justify-content:space-between;padding:.3rem 0;border-bottom:1px solid #262626;font-size:.85rem;"><span style="color:#ededed">{sect}</span><span style="color:{vc};font-family:JetBrains Mono;font-weight:600">{val}</span></div>'
        return f'<div style="background:{bg};border:1px solid {border};border-radius:8px;padding:1rem;margin-bottom:.8rem"><div style="font-size:.75rem;font-weight:700;color:{border};text-transform:uppercase;letter-spacing:.1em;margin-bottom:.6rem;font-family:JetBrains Mono">{title}</div>{rows}</div>'

    st.markdown("### 📰 Günün Manşetleri")
    rows_layout = [["🚀 SON KAPANIŞ LİDERİ","⚡ İVME KAZANAN"], ["📈 1 HAFTA ZİRVE","🏆 1 AY ZİRVE"], ["🔄 TOPARLAYAN","📉 SON KAPANIŞTA GERİDE"], ["❄️ 1 HAFTA DİP","🪨 1 AY DİP"], ["🐌 YAVAŞLAYAN",None]]
    for row_cats in rows_layout:
        cols = st.columns(2)
        for col,cat in zip(cols,row_cats):
            if cat and cat in summary:
                bg, border = CAT_STYLE.get(cat, ("#171717","#333"))
                col.markdown(cat_card(cat, summary[cat], bg, border), unsafe_allow_html=True)

    st.markdown("---")
    bar_chart = build_sector_bar_chart(stock_s)
    if bar_chart: st.plotly_chart(bar_chart, use_container_width=True, config={"displayModeBar":False})
    
    st.markdown("---")
    st.markdown("### 📋 Sektör Detay Tablosu")
    full_df = _sector_returns(stock_s)
    if not full_df.empty:
        full_df = full_df.sort_values('ret_1d',ascending=False).reset_index(drop=True)
        full_df.columns=['Sektör','Son Kapanış %','1 Hafta %','1 Ay %','İvme (5g)','İvme (21g)','Hisse Sayısı']
        for col_name in ['Son Kapanış %','1 Hafta %','1 Ay %']:
            full_df[col_name] = full_df[col_name].apply(lambda x: f"{x:+.2f}%" if not np.isnan(x) else "N/A")
        def color_ret(val):
            if isinstance(val,str) and val.startswith('+'): return 'color:#10b981'
            if isinstance(val,str) and val.startswith('-'): return 'color:#ef4444'
            return ''
        st.dataframe(full_df.style.map(color_ret,subset=['Son Kapanış %','1 Hafta %','1 Ay %']), use_container_width=True, height=500)

elif st.session_state.page == "macro":
    macro_theme = st.session_state.get("macro_theme","")
    if not macro_theme or macro_theme in ["— Temalar —","──────"]: st.session_state.page = "scanner"; st.rerun()

    info = get_theme_info(macro_theme)
    theme_sectors = info.get("sektörler",[])
    st.markdown(f"## 🌍 {macro_theme}")
    st.markdown(f"*{info.get('açıklama','')}*")

    one_cikanlar = info.get("öne_çıkan",[])
    if one_cikanlar:
        st.markdown("**⭐ Öne Çıkan Hisseler:**")
        oc_cols = st.columns(min(len(one_cikanlar),5))
        for col,tkr in zip(oc_cols,one_cikanlar):
            col.markdown(f'<div class="mc" style="text-align:center; padding: 0.5rem;"><div style="font-weight:700;color:#fff">{tkr}</div><div style="font-size:.65rem;color:#888">{get_sector(tkr)}</div></div>', unsafe_allow_html=True)

    st.markdown(f"**İlgili Sektörler:** {' · '.join(theme_sectors)}")
    st.markdown("---")

    theme_tickers = [t+".IS" for t,s in SECTOR_MAP.items() if s in theme_sectors]
    with st.spinner("Veri çekiliyor..."):
        bm_df = fetch_benchmark(period,interval)
        td = fetch_data(theme_tickers,period,interval)

    rows=[]
    for ticker,df in td.items():
        if df is None or len(df)<55: continue
        try:
            sc_e,mx_e,_,_ = score_emre(df,bm_df,ticker)
            c=_c(df); bm=_c(bm_df)
            rs=rs_score(c,bm,20)
            rows.append({'Hisse':ticker.replace('.IS',''),'Sektör':get_sector(ticker), 'Emre':f"{sc_e}/{mx_e}", 'RS (20g)':f"{rs*100:.1f}%" if not np.isnan(rs) else "N/A", 'Fiyat':f"₺{float(c.iloc[-1]):.2f}", '_es':sc_e,'_rs':rs if not np.isnan(rs) else -999})
        except: pass

    if rows:
        df_rows = pd.DataFrame(rows).sort_values(['_es','_rs'],ascending=False)
        st.dataframe(df_rows.drop(columns=['_es','_rs']),use_container_width=True,height=350)
        sel_t = st.selectbox("Detaylı incelemek için hisse seç", df_rows['Hisse'].tolist())
        if sel_t:
            tkr_yf = sel_t+".IS"
            if tkr_yf in td:
                sc,mx,crit,det = score_emre(td[tkr_yf],bm_df,tkr_yf)
                render_detail({"ticker":tkr_yf,"score":sc,"max_score":mx,"criteria":crit,"details":det,"df":td[tkr_yf]},"emre",interval)
    else:
        st.warning("Bu sektörler için veri alınamadı.")

elif st.session_state.page == "perf":
    st.markdown("## 📊 Strateji Performansı — Rebalanslı Log Defteri")
    st.markdown("Haziran 2024'ten itibaren · Her ayın ilk günü kümülatif rebalans · 100.000 ₺ başlangıç")
    st.markdown("---")

    if st.button("▶️ Backtest Çalıştır", type="primary"):
        with st.spinner("Tüm zamanların BIST100 evreni çekiliyor ve simülasyon hesaplanıyor..."):
            bm_df_bt = fetch_benchmark("3y","1d")
            stock_bt = fetch_data(BIST100_ALL_TIME_YF,"3y","1d")
            tlref_bt, tlref_bt_source = get_tlref_weekly()

        st.caption(f"Evren: {len(BIST100_ALL_TIME_YF)} ticker (hiç BIST100'de bulunmuş tüm hisseler) · Makro rüzgar kriteri için kullanılan faiz kaynağı: **{tlref_bt_source}**")

        bt_results={}
        prog=st.progress(0)
        strategies_to_run = ["emre","claude","qwen"]
        for i,sk in enumerate(strategies_to_run):
            prog.progress((i+1)/len(strategies_to_run), text=f"{STRATEGY_FN[sk][1]} hesaplanıyor...")
            pv,bm_n,trades,active,monthly = run_backtest(sk,stock_bt,bm_df_bt,tlref_weekly=tlref_bt)
            bt_results[sk] = {"pv":pv,"bm":bm_n,"trades":trades,"active":active,"monthly":monthly, "stats":calc_stats(pv,bm_n,100_000) if pv is not None else {}}
            gc.collect()
        prog.empty()
        st.session_state.bt_results = bt_results
        st.session_state.bt_done = True

    bt_results = st.session_state.bt_results
    if not bt_results:
        st.info("Simülasyonu başlatmak için 'Backtest Çalıştır' butonuna bas.")
        st.stop()

    st.markdown("### 📌 Bu Ay Aktif Portföyler")
    c1,c2,c3 = st.columns(3)
    for col,sk in zip([c1,c2,c3],["emre","claude","qwen"]):
        with col:
            st.markdown(f"**{STRATEGY_FN[sk][1]}**")
            active_list = bt_results[sk].get("active",[])
            st.caption(f"{len(active_list)} hisse")
            for pos in sorted(active_list,key=lambda x:x['pnl_pct'],reverse=True):
                pnl=pos['pnl_pct']; pc="#10b981" if pnl>=0 else "#ef4444"
                st.markdown(f'<div class="mc"><div style="display:flex;justify-content:space-between"><span style="font-weight:700;color:#fff">{pos["ticker"]}</span><span style="color:{pc};font-family:JetBrains Mono;font-weight:600">{pnl:+.1f}%</span></div><div style="font-size:.75rem;color:#888;margin-top:.2rem">Ort. Maliyet: ₺{pos["buy_price"]:.2f} → Güncel: ₺{pos["current_price"]:.2f}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📈 Portföy Performansı vs BIST 100")
    perf_map = {sk:(bt_results[sk]["pv"],bt_results[sk]["bm"]) for sk in ["emre","claude","qwen"] if bt_results[sk].get("pv") is not None}
    if perf_map: st.plotly_chart(build_perf_chart(perf_map,100_000), use_container_width=True, config={"displayModeBar":False})

    st.markdown("### 📊 Özet İstatistikler")
    stat_cols = st.columns(3)
    for col, sk in zip(stat_cols, ["emre","claude","qwen"]):
        with col:
            st.markdown(f"**{STRATEGY_FN[sk][1]}**")
            stats = bt_results[sk].get("stats", {})
            if stats:
                for k, v in stats.items():
                    st.markdown(f'<div class="mc"><div class="ml">{k}</div><div class="mv">{v}</div></div>', unsafe_allow_html=True)
            else:
                st.info("Veri yok.")

    st.markdown("###  Aylık Portföy ve Getiri Tablosu")
    mt1, mt2, mt3 = st.tabs([STRATEGY_FN["emre"][1], STRATEGY_FN["claude"][1], STRATEGY_FN["qwen"][1]])
    for tab, sk in zip([mt1, mt2, mt3], ["emre", "claude", "qwen"]):
        with tab:
            m_df = bt_results[sk].get("monthly")
            if m_df is not None and not m_df.empty:
                def color_pnl(val):
                    if isinstance(val, str) and val.startswith('+'): return 'color:#10b981'
                    if isinstance(val, str) and val.startswith('-'): return 'color:#ef4444'
                    return ''
                cols_s = ['Aylık P&L'] if 'Aylık P&L' in m_df.columns else []
                st.dataframe(m_df.style.map(color_pnl, subset=cols_s), use_container_width=True, height=350)
            else:
                st.info("Aylık tablo bulunamadı.")

    st.markdown("###  İşlem Log Defteri (Rebalans Geçmişi)")
    lt1,lt2,lt3 = st.tabs([STRATEGY_FN["emre"][1], STRATEGY_FN["claude"][1], STRATEGY_FN["qwen"][1]])
    for tab,sk in zip([lt1,lt2,lt3],["emre","claude","qwen"]):
        with tab:
            trades = bt_results[sk].get("trades")
            if trades is not None and not trades.empty:
                st.dataframe(trades.reset_index(drop=True), use_container_width=True, height=400)
            else:
                st.info("İşlem geçmişi bulunamadı.")

elif st.session_state.page == "scanner":
    strategy = st.session_state.strategy
    strategy_label = STRATEGY_FN[strategy][1]
    
    st.markdown(f"**Aktif Strateji:** `{strategy_label}`")
    st.markdown("---")

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔍 Tüm BIST'i Tara", type="primary"):
            st.session_state.scan_done = False
            st.session_state.results = []
            st.session_state.selected_ticker = None

    if not st.session_state.scan_done:
        with st.spinner("Piyasa verileri işleniyor..."):
            bm_df = fetch_benchmark(period, interval)
            stock_data = fetch_data(BIST100_YF, period, interval)
            
            sector_strength_map = None
            if strategy == "qwen":
                sector_strength_map = {}
                for sect in ALL_SECTORS:
                    sect_tickers = [t for t, s in SECTOR_MAP.items() if s == sect]
                    sect_rs_values = []
                    for tkr in sect_tickers:
                        tkr_yf = tkr + ".IS"
                        if tkr_yf in stock_data:
                            df_t = stock_data[tkr_yf]
                            if df_t is not None and len(df_t) >= 22:
                                c_t = _c(df_t)
                                bm_c = _c(bm_df)
                                rs_val = rs_score(c_t, bm_c, 21)
                                if not np.isnan(rs_val):
                                    sect_rs_values.append(rs_val)
                    if sect_rs_values:
                        sector_strength_map[sect] = np.mean(sect_rs_values)
                    else:
                        sector_strength_map[sect] = np.nan
            
            results = []
            
            for ticker, df in stock_data.items():
                if df is None or len(df)<55: continue
                fn = STRATEGY_FN[strategy][0]
                if strategy == "qwen":
                    sc, mx, crit, det = fn(df, bm_df, ticker, sector_strength_map=sector_strength_map)
                else:
                    sc, mx, crit, det = fn(df, bm_df, ticker)
                c = _c(df); rs = rs_score(c, _c(bm_df), 20)
                results.append({ "ticker": ticker, "score": sc, "max_score": mx, "criteria": crit, "details": det, "df": df, "rs": rs if not np.isnan(rs) else -999, "sector": get_sector(ticker), "in_top5": False })
            
            results.sort(key=lambda x: (x['score'], x['rs']), reverse=True)
            selected = _pick_portfolio(results, strategy)
            selected_tickers = {r['ticker'] for r in selected}
            for r in results:
                r['in_top5'] = r['ticker'] in selected_tickers

            st.session_state.results = results
            st.session_state.scan_done = True
            gc.collect()
            st.rerun()

    results = st.session_state.results
    if not results:
        st.info("👆 Tarama başlatmak için butona bas.")
        st.stop()

    top5_r = [r for r in results if r.get('in_top5')]
    near_r = [r for r in results if not r.get('in_top5')]

    left_col, right_col = st.columns([1, 2.5], gap="large")

    with left_col:
        st.markdown(f'<div class="sec-title">⭐ Portföy ({len(top5_r)})</div>', unsafe_allow_html=True)
        for r in top5_r:
            lbl = r["ticker"].replace(".IS","")
            if st.button(f"⭐ {lbl} ({r['score']}/{r['max_score']})\n{r['sector'][:15]}", key=f"t5_{r['ticker']}", use_container_width=True):
                st.session_state.selected_ticker = r["ticker"]; st.rerun()

        st.markdown(f'<div class="sec-title">⚠️ Diğerleri ({len(near_r)})</div>', unsafe_allow_html=True)
        for r in near_r:
            lbl = r["ticker"].replace(".IS","")
            if st.button(f" {lbl} ({r['score']}/{r['max_score']})\n{r['sector'][:15]}", key=f"nr_{r['ticker']}", use_container_width=True):
                st.session_state.selected_ticker = r["ticker"]; st.rerun()

    with right_col:
        sel = st.session_state.get("selected_ticker")
        if not sel:
            st.markdown("### ← İncelemek için soldan bir hisse seç")
        else:
            sel_result = next((r for r in results if r["ticker"]==sel), None)
            if sel_result: render_detail(sel_result, strategy, interval)
            else: st.warning("Hisse bulunamadı.")
