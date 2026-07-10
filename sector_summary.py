"""
Sektörel Özet Modülü - İYİLEŞTİRİLMİŞ
Sektörlerin getiri, momentum ve toparlanma verilerini hesaplar.
İYİLEŞTİRMELER:
1. Ortalama (mean) yerine ortanca (median) kullanımı - tek bir hissenin aşırı hareketi sektörü yanıltmasın
2. Minimum 3 hisse filtresi - az hisseli niş sektörler tabloyu domine etmesin
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sectors import SECTOR_MAP

def _sector_returns(stock_data):
    valid_dfs = [df for df in stock_data.values() if df is not None and not df.empty]
    if not valid_dfs: return pd.DataFrame()
    
    last_dates = [df.index[-1] for df in valid_dfs]
    common_last_date = pd.Series(last_dates).mode()[0]

    rows = []
    for ticker, df in stock_data.items():
        if df is None or len(df) < 45: continue
        try:
            c = df['Close'].loc[:common_last_date].dropna()
            
            if len(c) < 25 or c.index[-1] != common_last_date:
                continue

            tkr  = ticker.replace(".IS","")
            sect = SECTOR_MAP.get(tkr, "Diğer")

            if float(c.iloc[-2]) == 0 or float(c.iloc[-6]) == 0 or float(c.iloc[-22]) == 0:
                continue

            ret_1d  = (float(c.iloc[-1]) / float(c.iloc[-2])  - 1) * 100
            ret_5d  = (float(c.iloc[-1]) / float(c.iloc[-6])  - 1) * 100
            ret_21d = (float(c.iloc[-1]) / float(c.iloc[-22]) - 1) * 100

            mom_5d_prev = (float(c.iloc[-6]) / float(c.iloc[-11]) - 1) * 100 if float(c.iloc[-11]) != 0 else 0
            mom_5d  = ret_5d - mom_5d_prev

            mom_21d_prev = (float(c.iloc[-22]) / float(c.iloc[-43]) - 1) * 100 if float(c.iloc[-43]) != 0 else 0
            mom_21d = ret_21d - mom_21d_prev

            rows.append({
                'ticker': tkr, 'sector': sect,
                'ret_1d': ret_1d, 'ret_5d': ret_5d, 'ret_21d': ret_21d,
                'mom_5d': mom_5d, 'mom_21d': mom_21d,
            })
        except Exception:
            pass

    if not rows:
        return pd.DataFrame()

    df_all = pd.DataFrame(rows)
    
    # İYİLEŞTİRME 1: mean yerine median kullan (outlier'lardan etkilenme)
    sect_df = df_all.groupby('sector').agg(
        ret_1d=('ret_1d','median'),
        ret_5d=('ret_5d','median'),
        ret_21d=('ret_21d','median'),
        mom_5d=('mom_5d','median'),
        mom_21d=('mom_21d','median'),
        hisse_sayisi=('ticker','count'),
    ).reset_index()

    # İYİLEŞTİRME 2: Minimum 3 hisse filtresi - az hisseli sektörler yanıltmasın
    sect_df = sect_df[sect_df['hisse_sayisi'] >= 3]

    return sect_df

def build_summary(stock_data):
    df = _sector_returns(stock_data)
    if df.empty:
        return {}

    df_clean = df.dropna(subset=['ret_1d', 'ret_5d', 'ret_21d', 'mom_5d'])

    top_1d   = df_clean.nlargest(3, 'ret_1d')[['sector','ret_1d']].values.tolist()
    bot_1d   = df_clean.nsmallest(3, 'ret_1d')[['sector','ret_1d']].values.tolist()
    
    top_5d   = df_clean.nlargest(3, 'ret_5d')[['sector','ret_5d']].values.tolist()
    bot_5d   = df_clean.nsmallest(3, 'ret_5d')[['sector','ret_5d']].values.tolist()
    
    top_21d  = df_clean.nlargest(3, 'ret_21d')[['sector','ret_21d']].values.tolist()
    bot_21d  = df_clean.nsmallest(3, 'ret_21d')[['sector','ret_21d']].values.tolist()
    
    ivme     = df_clean.nlargest(3, 'mom_5d')[['sector','mom_5d']].values.tolist()
    yavas    = df_clean.nsmallest(3, 'mom_5d')[['sector','mom_5d']].values.tolist()
    
    toparlayan = df_clean[(df_clean['ret_5d'] > 0) & (df_clean['ret_21d'] < 0)].nlargest(3,'ret_5d')[['sector','ret_5d']].values.tolist()

    def fmt(val): return f"{val:+.2f}%"

    return {
        " SON KAPANIŞ LİDERİ":   [(s, fmt(v)) for s,v in top_1d],
        "⚡ İVME KAZANAN":        [(s, fmt(v)) for s,v in ivme],
        " 1 HAFTA ZİRVE":       [(s, fmt(v)) for s,v in top_5d],
        "🏆 1 AY ZİRVE":          [(s, fmt(v)) for s,v in top_21d],
        "🔄 TOPARLAYAN":          [(s, fmt(v)) for s,v in toparlayan] or [("—","")],
        "📉 SON KAPANIŞTA GERİDE": [(s, fmt(v)) for s,v in bot_1d],
        "❄️ 1 HAFTA DİP":        [(s, fmt(v)) for s,v in bot_5d],
        " 1 AY DİP":            [(s, fmt(v)) for s,v in bot_21d],
        "🐌 YAVAŞLAYAN":          [(s, fmt(v)) for s,v in yavas],
    }

def build_sector_bar_chart(stock_data):
    df = _sector_returns(stock_data)
    if df.empty: return None

    df = df.dropna(subset=['ret_1d']).sort_values('ret_1d', ascending=True)

    fig = go.Figure()
    
    marker_colors = ['#10b981' if v >= 0 else '#ef4444' for v in df['ret_1d']]
    
    fig.add_trace(go.Bar(
        y=df['sector'], x=df['ret_1d'],
        name='Son Kapanış', orientation='h',
        marker_color=marker_colors,
        opacity=0.9,
    ))
    fig.add_trace(go.Bar(
        y=df['sector'], x=df['ret_5d'],
        name='1 Hafta', orientation='h',
        marker_color='#38bdf8', opacity=0.5, visible='legendonly',
    ))
    fig.add_trace(go.Bar(
        y=df['sector'], x=df['ret_21d'],
        name='1 Ay', orientation='h',
        marker_color='#a78bfa', opacity=0.5, visible='legendonly',
    ))

    fig.update_layout(
        height=max(450, len(df) * 32), 
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='JetBrains Mono', color='#a3a3a3', size=11),
        legend=dict(orientation='h', y=1.02, x=0, bgcolor='rgba(0,0,0,0)', font=dict(color="#fff")),
        margin=dict(l=10, r=10, t=20, b=10),
        barmode='overlay',
        xaxis=dict(ticksuffix='%', gridcolor='#1e1e1e', zeroline=True, zerolinecolor='#333', zerolinewidth=1),
        yaxis=dict(gridcolor='#1e1e1e'),
        title=dict(text='Sektör Getirileri', font=dict(color='#ffffff', size=14), x=0.01),
    )
    return fig
