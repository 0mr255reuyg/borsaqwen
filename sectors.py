"""
sectors.py
BIST 100 bileşen listesi ve Makro Tema eşleştirmeleri.
"""
import requests
from bs4 import BeautifulSoup
import streamlit as st

FALLBACK_SECTOR_MAP = {
    "AKBNK": "Banka", "ALBRK": "Banka", "GARAN": "Banka", "HALKB": "Banka", 
    "ISCTR": "Banka", "SKBNK": "Banka", "TSKB": "Banka", "VAKBN": "Banka", "YKBNK": "Banka",
    "DSTKF": "Faktoring ve Finansal Kiralama", "LIDER": "Faktoring ve Finansal Kiralama",
    "KTLEV": "Tasarruf Finansman",
    "ANHYT": "Sigorta", "ANSGR": "Sigorta", "TURSG": "Sigorta",
    "AVPGY": "GYO", "DAPGM": "GYO", "EKGYO": "GYO", "ISGYO": "GYO", 
    "KUYAS": "GYO", "PEKGY": "GYO", "PSGYO": "GYO", "RGYAS": "GYO", "RYGYO": "GYO",
    "AGHOL": "Holding", "ALARK": "Holding", "BERA": "Holding", "BINHO": "Holding", 
    "BRYAT": "Holding", "DOHOL": "Holding", "ECZYT": "Holding", "ENKAI": "Holding", 
    "GRTHO": "Holding", "IEYHO": "Holding", "ISMEN": "Holding", "KCHOL": "Holding", 
    "NTHOL": "Holding", "PAHOL": "Holding", "RALYH": "Holding", "SAHOL": "Holding", 
    "TKFEN": "Holding", "YAZIC": "Holding",
    "AHGAZ": "Enerji", "AKFYE": "Enerji", "AKSEN": "Enerji", "ALFAS": "Enerji", 
    "ASTOR": "Enerji", "BIOEN": "Enerji", "CANTE": "Enerji", "CWENE": "Enerji", 
    "EFORC": "Enerji", "ENJSA": "Enerji", "ENERY": "Enerji", "ESEN": "Enerji", 
    "EUPWR": "Enerji", "GESAN": "Enerji", "GWIND": "Enerji", "IPEKE": "Enerji", 
    "IZENR": "Enerji", "MAGEN": "Enerji", "ODAS": "Enerji", "SAYAS": "Enerji", 
    "SMRTG": "Enerji", "TUPRS": "Enerji", "YEOTK": "Enerji", "ZOREN": "Enerji",
    "BFREN": "Otomotiv", "DOAS": "Otomotiv", "EGEEN": "Otomotiv", "FROTO": "Otomotiv", 
    "KARSN": "Otomotiv", "OTKAR": "Otomotiv", "TMSN": "Otomotiv", "TOASO": "Otomotiv", "TTRAK": "Otomotiv",
    "AEFES": "Gıda ve Perakende", "BALSU": "Gıda ve Perakende", "BIMAS": "Gıda ve Perakende", 
    "CCOLA": "Gıda ve Perakende", "KAYSE": "Gıda ve Perakende", "KLRHO": "Gıda ve Perakende", 
    "MGROS": "Gıda ve Perakende", "OBAMS": "Gıda ve Perakende", "SOKM": "Gıda ve Perakende", 
    "TABGD": "Gıda ve Perakende", "TKNSA": "Gıda ve Perakende", "TUKAS": "Gıda ve Perakende", 
    "ULKER": "Gıda ve Perakende", "YYLGD": "Gıda ve Perakende",
    "CLEBI": "Ulaşım ve Turizm", "PASEU": "Ulaşım ve Turizm", "PGSUS": "Ulaşım ve Turizm", 
    "TAVHL": "Ulaşım ve Turizm", "THYAO": "Ulaşım ve Turizm", "TUREX": "Ulaşım ve Turizm",
    "TCELL": "İletişim", "TTKOM": "İletişim",
    "ECILC": "Sağlık", "GENIL": "Sağlık", "LMKDC": "Sağlık", "MPARK": "Sağlık", "SELEC": "Sağlık",
    "ALTNY": "Savunma", "ASELS": "Savunma", "PAPIL": "Savunma", "SDTTR": "Savunma",
    "ARDYZ": "Teknoloji", "KONTR": "Teknoloji", "MIATK": "Teknoloji", 
    "ODINE": "Teknoloji", "PATEK": "Teknoloji", "REEDR": "Teknoloji",
    "BRSAN": "Çelik ve Metal", "CVKMD": "Çelik ve Metal", "EREGL": "Çelik ve Metal", 
    "KCAER": "Çelik ve Metal", "KOZAA": "Çelik ve Metal", "KOZAL": "Çelik ve Metal", 
    "KRDMD": "Çelik ve Metal", "SARKY": "Çelik ve Metal",
    "AKCNS": "İnşaat Malzemeleri", "BIENY": "İnşaat Malzemeleri", "BOBET": "İnşaat Malzemeleri", 
    "BSOKE": "İnşaat Malzemeleri", "BTCIM": "İnşaat Malzemeleri", "CIMSA": "İnşaat Malzemeleri", 
    "GLRMK": "İnşaat Malzemeleri", "GOLTS": "İnşaat Malzemeleri", "KLSER": "İnşaat Malzemeleri", 
    "KONYA": "İnşaat Malzemeleri", "OYAKC": "İnşaat Malzemeleri", "QUAGR": "İnşaat Malzemeleri",
    "AGROT": "Sanayi ve Kimya", "ARCLK": "Sanayi ve Kimya", "EUREN": "Sanayi ve Kimya", 
    "GUBRF": "Sanayi ve Kimya", "HEKTS": "Sanayi ve Kimya", "PETKM": "Sanayi ve Kimya", 
    "SASA": "Sanayi ve Kimya", "SISE": "Sanayi ve Kimya", "VESBE": "Sanayi ve Kimya", "VESTL": "Sanayi ve Kimya",
    "BJKAS": "Spor Kulüpleri", "FENER": "Spor Kulüpleri", "GSRAY": "Spor Kulüpleri", "TSPOR": "Spor Kulüpleri",
    "ADEL": "Tüketim", "GRSEL": "Tüketim", "MAVI": "Tüketim",
}

@st.cache_data(ttl=86400, show_spinner=False)
def get_live_bist100_and_sectors():
    try:
        live_map = FALLBACK_SECTOR_MAP.copy()
        return sorted(set(live_map.keys())), live_map
    except Exception:
        return sorted(set(FALLBACK_SECTOR_MAP.keys())), FALLBACK_SECTOR_MAP

BIST100_OFFICIAL, SECTOR_MAP = get_live_bist100_and_sectors()

def get_sector(ticker):
    t = ticker.replace(".IS", "")
    return SECTOR_MAP.get(t, "Diğer")

MACRO_THEMES_PRIMARY = {
    "💰 Yüksek Faiz": {
        "sektörler": ["Banka", "Sigorta", "Tasarruf Finansman"],
        "açıklama": "Faiz oranları yüksekken bankaların net faiz marjı, sigortaların yatırım geliri artar.",
        "öne_çıkan": ["AKBNK", "GARAN", "ISCTR", "TURSG", "ANSGR", "KTLEV"],
    },
    "📉 Faiz İndirim Dönemi": {
        "sektörler": ["Banka", "GYO", "İnşaat Malzemeleri"],
        "açıklama": "Faizlerin düşmesi kredi hacmini büyütür; konut/GYO sektörüne talep artar.",
        "öne_çıkan": ["GARAN", "AKBNK", "ISCTR", "EKGYO", "OYAKC", "CIMSA"],
    },
    "🔋 Teşvik Dönemi / Enerji": {
        "sektörler": ["Enerji", "İnşaat Malzemeleri"],
        "açıklama": "Kamu teşvikleri enerji dönüşümünü ve altyapı inşasını besler.",
        "öne_çıkan": ["AKSEN", "ASTOR", "ZOREN", "OYAKC", "CIMSA"],
    },
    "📉 Lira Değer Kaybı / İhracatçı": {
        "sektörler": ["Otomotiv", "Çelik ve Metal", "Sanayi ve Kimya"],
        "açıklama": "Güçlü döviz geliri olan ihracatçılar TL'nin değer kaybettiği senaryodan fayda sağlar.",
        "öne_çıkan": ["FROTO", "TOASO", "EREGL", "ARCLK", "SISE"],
    },
}

MACRO_THEMES_SECONDARY = {
    "⚔️ Jeopolitik Gerilim": {
        "sektörler": ["Savunma"],
        "açıklama": "Savunma bütçelerinin artması yerli savunma sanayisini ön plana çıkarır.",
        "öne_çıkan": ["ASELS", "SDTTR"],
    },
    "🪨 Emtia Güçlü": {
        "sektörler": ["Çelik ve Metal", "Sanayi ve Kimya", "Enerji"],
        "açıklama": "Küresel emtia fiyatları yükseldiğinde ana üretici marjları genişler.",
        "öne_çıkan": ["EREGL", "KRDMD", "PETKM", "TUPRS"],
    },
    "🛡️ Piyasa Çalkantılı / Defansif": {
        "sektörler": ["Gıda ve Perakende", "İletişim", "Sağlık"],
        "açıklama": "Belirsizlik ve yüksek volatilite dönemlerinde zorunlu tüketim sektörleri portföyü korur.",
        "öne_çıkan": ["BIMAS", "MGROS", "TCELL", "TTKOM"],
    },
    "🚀 Risk İştahı Yüksek": {
        "sektörler": ["Teknoloji", "Otomotiv", "Sanayi ve Kimya"],
        "açıklama": "Büyüme beklentisinin güçlü olduğu piyasalarda teknoloji ve döngüsel hisseler ralli yapar.",
        "öne_çıkan": ["MIATK", "ARDYZ", "FROTO", "TOASO", "VESTL"],
    },
    "🏥 Sağlık": {
        "sektörler": ["Sağlık"],
        "açıklama": "Sağlık harcamalarının ve sektörel yatırımların artışıyla istikrarlı büyüme sağlar.",
        "öne_çıkan": ["MPARK", "GENIL", "ECILC"],
    },
    "✈️ Turizm & Ulaşım": {
        "sektörler": ["Ulaşım ve Turizm"],
        "açıklama": "Turizm sezonu ve artan yolcu/kargo talebiyle havayolları güçlenir.",
        "öne_çıkan": ["THYAO", "PGSUS", "TAVHL"],
    },
}

MACRO_THEMES = {**MACRO_THEMES_PRIMARY, **MACRO_THEMES_SECONDARY}

def get_theme_sectors(theme):
    return MACRO_THEMES.get(theme, {}).get("sektörler", [])

def get_theme_info(theme):
    return MACRO_THEMES.get(theme, {})

ALL_SECTORS = sorted(set(SECTOR_MAP.values()))
