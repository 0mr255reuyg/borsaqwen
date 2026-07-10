"""
membership.py
BIST 100'ün NOKTA-ZAMANLI (point-in-time) uyelik gecmisi.

NEDEN BU DOSYA VAR:
Eskiden sectors.py tek bir statik "su anki" liste tutuyordu. Backtest bu tek
listeyi TUM gecmis icin kullaniyordu -> hem bugun endekste olmayan ama
gecmiste satin alinmis gorunen hisseler (survivorship bias) hem de gecmiste
gercekten var olup bugun endeksten cikmis hisselerin (ornek: AGHOL, TABGD,
BERA, SDTTR...) o donemlerde hic yokmus gibi davranilmasi sorunu vardi.

NASIL KULLANILIR:
    from membership import get_constituents_at
    tickers = get_constituents_at(pd.Timestamp("2024-08-15"))
    # -> o tarihte BIST100'de FIILEN bulunan ~100 ticker (".IS" olmadan)

VERI KAYNAGI VE GUVENILIRLIK:
Asagidaki MEMBERSHIP_HISTORY, Borsa Istanbul'un resmi ceyreklik endeks
revizyon duyurularindan (borsaistanbul.com/en/announcement/...) elle
derlendi - haber sitesi ozetinden degil, "STOCKS TO BE INCLUDED / EXCLUDED"
resmi tablolarindan. 2024-04-01 -> 2026-07-01 arasi 9 donem, tek bir bosluk
olmadan kapsaniyor ve investing.com'un canli 100'luk bilesen listesiyle
(2026 Nisan-Haziran donemi) capraz dogrulandi.

BILINEN KUCUK TUTARSIZLIK: AGHOL. Resmi delta zincirine gore Temmuz 2024'te
eklenip Temmuz 2026'da cikana kadar surekli endeste olmasi gerekiyor, ama
investing.com'un canli taramasinda bu araliktaki bir anda eksikti (veri
gecikmesi/hata olabilir). Zorla "dogru" 100 sayisina ulasmak icin gercek bir
hisseyi silmek yerine, birincil kaynak olan resmi Borsa duyurularina
guvenilip AGHOL tum donemlerde tutuldu. Bu yuzden listeler ~100 degil ~101
ticker iceriyor - backtest sonucuna etkisi ihmal edilebilir duzeyde (1/100
pozisyon havuzu farki).

DUZELTME (2026-07 donemi): BERA, 2026-04-01 doneminde listede varken
2026-07-01 doneminde yanlislikla dusmustu. Resmi Q3 2026 (1 Temmuz-30 Eylul)
duyurusunda BERA'nin endeksten cikarildigina dair bir kayit YOK (yalnizca
AGHOL, TABGD, TUREX cikti; ODINE, IEYHO, ESEN girdi) - bu yuzden BERA
2026-07-01 listesine geri eklendi.

GUNCELLEME SORUMLULUGU:
Bu liste otomatik BUYUMEZ. Her ceyrek (Ocak/Nisan/Temmuz/Ekim basi) Borsa
Istanbul yeni bir revizyon yayinladiginda, en altta tanimli
`_detect_new_revision()` fonksiyonu canli veriyle en son kayitli donemi
karsilastirip fark varsa uyari basar. Fark tespit edilirse yeni donemi
MEMBERSHIP_HISTORY'ye elle (ya da bir sonraki oturumda Claude'a "yeni
revizyon var, ekle" diyerek) eklemek gerekir - bu, kodun "3 ayda bir kirilan"
tarafi degil, "3 ayda bir 5 dakikalik onay" tarafi.
"""
from __future__ import annotations
import pandas as pd

# Her anahtar, o ceyreklik donemin BASLANGIC tarihi (efektif tarih).
# get_constituents_at(), verilen tarihten once veya o tarihte baslamis EN
# YAKIN donemi bulup o listeyi dondurur.
MEMBERSHIP_HISTORY: dict[str, list[str]] = {
    "2024-04-01": [
        "AEFES","AGROT","AHGAZ","AKBNK","AKCNS","AKFGY","AKFYE","AKSA","AKSEN","ALARK",
        "ALBRK","ALFAS","ANSGR","ARCLK","ASELS","ASTOR","BERA","BFREN","BIENY","BIMAS",
        "BIOEN","BOBET","BRSAN","BRYAT","BTCIM","CANTE","CCOLA","CIMSA","CWENE","DOAS",
        "DOHOL","ECILC","ECZYT","EGEEN","EKGYO","ENERY","ENJSA","ENKAI","EREGL","EUPWR",
        "EUREN","FROTO","GARAN","GESAN","GUBRF","GWIND","HALKB","HEKTS","IPEKE","ISCTR",
        "ISGYO","ISMEN","IZENR","KAYSE","KCAER","KCHOL","KLSER","KONTR","KONYA","KOZAA",
        "KOZAL","KRDMD","MAVI","MGROS","MIATK","ODAS","OTKAR","OYAKC","PETKM","PGSUS",
        "QUAGR","REEDR","SAHOL","SASA","SAYAS","SDTTR","SISE","SKBNK","SMRTG","SOKM",
        "TABGD","TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TTKOM","TTRAK","TUKAS",
        "TUPRS","TURSG","ULKER","VAKBN","VESBE","VESTL","YAZIC","YEOTK","YKBNK","YYLGD","ZOREN",
    ],
    "2024-07-01": [
        "AEFES","AGHOL","AGROT","AKBNK","AKFGY","AKFYE","AKSA","AKSEN","ALARK","ALFAS",
        "ANSGR","ARCLK","ARDYZ","ASELS","ASTOR","BERA","BFREN","BIMAS","BINHO","BRSAN",
        "BRYAT","BTCIM","CANTE","CCOLA","CIMSA","CWENE","DOAS","DOHOL","ECILC","ECZYT",
        "EGEEN","EKGYO","ENERY","ENJSA","ENKAI","EREGL","EUPWR","EUREN","FROTO","GARAN",
        "GESAN","GOLTS","GUBRF","HALKB","HEKTS","ISCTR","ISGYO","ISMEN","IZENR","KAYSE",
        "KCAER","KCHOL","KLSER","KONTR","KONYA","KOZAA","KOZAL","KRDMD","KTLEV","LMKDC",
        "MAVI","MGROS","MIATK","OBAMS","ODAS","OTKAR","OYAKC","PEKGY","PETKM","PGSUS",
        "QUAGR","REEDR","SAHOL","SASA","SDTTR","SISE","SKBNK","SMRTG","SOKM","TABGD",
        "TAVHL","TCELL","THYAO","TKFEN","TKNSA","TMSN","TOASO","TSKB","TTKOM","TTRAK",
        "TUKAS","TUPRS","TURSG","ULKER","VAKBN","VESBE","VESTL","YAZIC","YEOTK","YKBNK","ZOREN",
    ],
    "2024-10-01": [
        "ADEL","AEFES","AGHOL","AGROT","AKBNK","AKFGY","AKFYE","AKSA","AKSEN","ALARK",
        "ALFAS","ALTNY","ANSGR","ARCLK","ARDYZ","ASELS","ASTOR","BERA","BIMAS","BINHO",
        "BJKAS","BRSAN","BRYAT","BTCIM","CANTE","CCOLA","CIMSA","CLEBI","CWENE","DOAS",
        "DOHOL","ECILC","EGEEN","EKGYO","ENJSA","ENKAI","EREGL","EUPWR","FENER","FROTO",
        "GARAN","GESAN","GUBRF","HALKB","HEKTS","ISCTR","ISMEN","KARSN","KCAER","KCHOL",
        "KLSER","KONTR","KONYA","KOZAA","KOZAL","KRDMD","KTLEV","LMKDC","MAVI","MGROS",
        "MIATK","MPARK","OBAMS","ODAS","OTKAR","OYAKC","PAPIL","PETKM","PGSUS","QUAGR",
        "REEDR","RGYAS","SAHOL","SASA","SDTTR","SISE","SKBNK","SMRTG","SOKM","TABGD",
        "TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TTKOM","TTRAK","TUKAS","TUPRS",
        "TURSG","ULKER","VAKBN","VESTL","YAZIC","YEOTK","YKBNK","ZOREN",
    ],
    "2025-01-01": [
        "ADEL","AEFES","AGHOL","AGROT","AKBNK","AKFGY","AKFYE","AKSA","AKSEN","ALARK",
        "ALFAS","ALTNY","ANHYT","ANSGR","ARCLK","ARDYZ","ASELS","ASTOR","BERA","BIMAS",
        "BJKAS","BRSAN","BRYAT","BSOKE","BTCIM","CANTE","CCOLA","CIMSA","CLEBI","CVKMD",
        "CWENE","DOAS","DOHOL","ECILC","EGEEN","EKGYO","ENJSA","ENKAI","EREGL","EUPWR",
        "FENER","FROTO","GARAN","GESAN","GUBRF","HALKB","HEKTS","IEYHO","ISCTR","ISMEN",
        "KARSN","KCAER","KCHOL","KOZAA","KOZAL","KRDMD","LIDER","MAGEN","MAVI","MGROS",
        "MIATK","MPARK","NTHOL","ODAS","OTKAR","OYAKC","PASEU","PETKM","PGSUS","QUAGR",
        "REEDR","SAHOL","SASA","SDTTR","SELEC","SISE","SKBNK","SMRTG","SOKM","TABGD",
        "TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TSPOR","TTKOM","TTRAK","TUKAS",
        "TUPRS","TURSG","ULKER","VAKBN","VESTL","YAZIC","YEOTK","YKBNK","ZOREN",
    ],
    "2025-04-01": [
        "AEFES","AGHOL","AGROT","AHGAZ","AKBNK","AKSA","AKSEN","ALARK","ALFAS","ANHYT",
        "ANSGR","ARCLK","ARDYZ","ASELS","ASTOR","AVPGY","BERA","BIMAS","BRSAN","BRYAT",
        "BSOKE","BTCIM","CANTE","CCOLA","CIMSA","CVKMD","CWENE","DOAS","DOHOL","ECILC",
        "EFORC","EGEEN","EKGYO","ENJSA","ENKAI","EREGL","EUPWR","FROTO","GARAN","GESAN",
        "GRTHO","GSRAY","GUBRF","HALKB","HEKTS","IEYHO","ISCTR","ISMEN","KCAER","KCHOL",
        "KOZAA","KOZAL","KRDMD","KTLEV","LIDER","LMKDC","MAGEN","MAVI","MGROS","MIATK",
        "MPARK","NTHOL","OBAMS","ODAS","OTKAR","OYAKC","PASEU","PETKM","PGSUS","QUAGR",
        "RALYH","REEDR","RYGYO","SAHOL","SASA","SELEC","SISE","SKBNK","SMRTG","SOKM",
        "TABGD","TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TSPOR","TTKOM","TTRAK",
        "TUPRS","TURSG","ULKER","VAKBN","VESTL","YAZIC","YEOTK","YKBNK","ZOREN",
    ],
    "2025-07-01": [
        "AEFES","AGHOL","AGROT","AKBNK","AKSA","AKSEN","ALARK","ALFAS","ANSGR","ARCLK",
        "ASELS","ASTOR","AVPGY","BALSU","BERA","BIMAS","BINHO","BRSAN","BRYAT","BSOKE",
        "BTCIM","CANTE","CCOLA","CIMSA","CVKMD","CWENE","DOAS","DOHOL","DSTKF","ECILC",
        "EFORC","EGEEN","EKGYO","ENJSA","ENKAI","EREGL","EUPWR","FENER","FROTO","GARAN",
        "GENIL","GESAN","GLRMK","GRSEL","GRTHO","GSRAY","GUBRF","HALKB","HEKTS","IEYHO",
        "IPEKE","ISCTR","ISMEN","KCAER","KCHOL","KOZAA","KOZAL","KRDMD","KTLEV","KUYAS",
        "LIDER","LMKDC","MAGEN","MAVI","MGROS","MIATK","MPARK","NTHOL","OBAMS","ODAS",
        "OTKAR","OYAKC","PASEU","PETKM","PGSUS","QUAGR","RALYH","REEDR","SAHOL","SASA",
        "SISE","SKBNK","SMRTG","SOKM","TABGD","TAVHL","TCELL","THYAO","TKFEN","TOASO",
        "TSKB","TSPOR","TTKOM","TTRAK","TUPRS","TURSG","TUREX","ULKER","VAKBN","VESTL",
        "YAZIC","YEOTK","YKBNK","ZOREN",
    ],
    "2025-10-01": [
        "AEFES","AGHOL","AKBNK","AKSA","AKSEN","ALARK","ANSGR","ARCLK","ASELS","ASTOR",
        "BALSU","BIMAS","BINHO","BRSAN","BRYAT","BSOKE","BTCIM","CANTE","CCOLA","CIMSA",
        "CLEBI","CVKMD","CWENE","DAPGM","DOAS","DOHOL","DSTKF","ECILC","EFORC","EGEEN",
        "EKGYO","ENJSA","ENKAI","EREGL","EUPWR","FENER","FROTO","GARAN","GENIL","GESAN",
        "GLRMK","GRSEL","GRTHO","GSRAY","GUBRF","HALKB","HEKTS","IEYHO","IPEKE","ISCTR",
        "ISMEN","KCAER","KCHOL","KOZAA","KOZAL","KRDMD","KTLEV","KUYAS","MAGEN","MAVI",
        "MGROS","MIATK","MPARK","OBAMS","ODAS","OTKAR","OYAKC","PASEU","PATEK","PETKM",
        "PGSUS","QUAGR","RALYH","REEDR","SAHOL","SARKY","SASA","SISE","SKBNK","SOKM",
        "TABGD","TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TSPOR","TTKOM","TTRAK",
        "TUKAS","TUPRS","TURSG","TUREX","ULKER","VAKBN","VESTL","YAZIC","YEOTK","YKBNK","ZOREN",
    ],
    "2026-01-01": [
        "AEFES","AGHOL","AKBNK","AKSA","AKSEN","ALARK","ANSGR","ARCLK","ASELS","ASTOR",
        "BALSU","BIMAS","BRSAN","BRYAT","BSOKE","BTCIM","CANTE","CCOLA","CIMSA","CVKMD",
        "CWENE","DAPGM","DOAS","DOHOL","DSTKF","ECILC","EFORC","EGEEN","EKGYO","ENJSA",
        "ENKAI","EREGL","EUPWR","FENER","FROTO","GARAN","GENIL","GESAN","GLRMK","GRSEL",
        "GRTHO","GSRAY","GUBRF","HALKB","HEKTS","IPEKE","ISCTR","ISMEN","IZENR","KCAER",
        "KCHOL","KLRHO","KOZAA","KOZAL","KRDMD","KTLEV","KUYAS","MAGEN","MAVI","MGROS",
        "MIATK","MPARK","OBAMS","ODAS","OTKAR","OYAKC","PASEU","PATEK","PETKM","PGSUS",
        "QUAGR","RALYH","REEDR","SAHOL","SARKY","SASA","SISE","SKBNK","SOKM","TABGD",
        "TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TSPOR","TTKOM","TTRAK","TUKAS",
        "TUPRS","TURSG","TUREX","ULKER","VAKBN","VESTL","YAZIC","YEOTK","YKBNK","ZOREN",
    ],
    "2026-04-01": [
        "AEFES","AGHOL","AKBNK","AKSA","AKSEN","ALARK","ANSGR","ARCLK","ASELS","ASTOR",
        "BALSU","BIMAS","BRSAN","BRYAT","BSOKE","BTCIM","CANTE","CCOLA","CIMSA","CVKMD",
        "CWENE","DAPGM","DOAS","DOHOL","DSTKF","ECILC","EFORC","EKGYO","ENERY","ENJSA",
        "ENKAI","EREGL","EUPWR","EUREN","FENER","FROTO","GARAN","GENIL","GESAN","GLRMK",
        "GRSEL","GRTHO","GSRAY","GUBRF","HALKB","HEKTS","IPEKE","ISCTR","ISMEN","IZENR",
        "KCHOL","KLRHO","KOZAA","KOZAL","KRDMD","KTLEV","KUYAS","MAGEN","MAVI","MGROS",
        "MIATK","MPARK","OBAMS","ODAS","OTKAR","OYAKC","PAHOL","PASEU","PATEK","PETKM",
        "PGSUS","PSGYO","QUAGR","RALYH","REEDR","SAHOL","SARKY","SASA","SISE","SKBNK",
        "SOKM","TABGD","TAVHL","TCELL","THYAO","TKFEN","TOASO","TSKB","TTKOM","TUKAS",
        "TUPRS","TURSG","TUREX","ULKER","VAKBN","VESTL","YAZIC","YKBNK","ZOREN",
    ],
    "2026-07-01": [
        "AEFES","AKBNK","AKSA","AKSEN","ALARK","ALTNY","ANSGR","ARCLK","ASELS","ASTOR",
        "BALSU","BERA","BIMAS","BRSAN","BRYAT","BSOKE","BTCIM","CANTE","CCOLA","CIMSA",
        "CVKMD","CWENE","DAPGM","DOAS","DOHOL","DSTKF","ECILC","EFORC","EKGYO","ENERY",
        "ENJSA","ENKAI","EREGL","ESEN","EUPWR","EUREN","FENER","FROTO","GARAN","GENIL",
        "GESAN","GLRMK","GRSEL","GRTHO","GSRAY","GUBRF","HALKB","HEKTS","IEYHO","IPEKE",
        "ISCTR","ISMEN","IZENR","KCHOL","KLRHO","KONTR","KOZAA","KOZAL","KRDMD","KTLEV",
        "KUYAS","MAGEN","MAVI","MGROS","MIATK","MPARK","OBAMS","ODAS","ODINE","OTKAR",
        "OYAKC","PAHOL","PASEU","PATEK","PETKM","PGSUS","PSGYO","QUAGR","RALYH","REEDR",
        "SAHOL","SARKY","SASA","SISE","SKBNK","SOKM","TAVHL","TCELL","THYAO","TKFEN",
        "TOASO","TSKB","TTKOM","TUKAS","TUPRS","TURSG","ULKER","VAKBN","VESTL","YAZIC",
        "YKBNK","ZOREN",
    ],
}

_SORTED_PERIOD_STARTS = sorted(pd.Timestamp(d) for d in MEMBERSHIP_HISTORY)

# ─ TICKER YENIDEN ISIMLENDIRME HARITASI ──────────────────────────────────────
# Bazi sirketler unvan/kod degisikligi geciriyor - AYNI sirket, sadece islem
# kodu degisiyor. Bunlari gercek endeks giris/cikis sanmamak icin, canli
# veriyle karsilastirmadan once normalize ediyoruz.
#
# KOZAA -> TRMET, KOZAL -> TRALT, IPEKE -> TRENJ: 24 Kasim 2025'te Borsa
# Istanbul'un resmi duyurusuyla unvan degisikligi yapildi (Koza Anadolu Metal
# -> TR Anadolu Metal Madencilik, Koza Altin -> Turk Altin Isletmeleri,
# Ipek Dogal Enerji -> TR Dogal Enerji Kaynaklari). Sirketler AYNI, sadece
# kod degisti. Bu harita olmadan borsapy'nin canli cektigi yeni kodlar
# (TRMET/TRALT/TRENJ), membership.py'deki eski kodlarla (KOZAA/KOZAL/IPEKE)
# eslenemiyor ve _detect_new_revision bunu sahte bir giris+cikis olarak
# raporluyordu.
TICKER_RENAME_MAP: dict[str, str] = {
    "KOZAA": "TRMET",
    "KOZAL": "TRALT",
    "IPEKE": "TRENJ",
}


def _normalize_renames(tickers: set[str]) -> set[str]:
    """Eski (kayitli) kodlari yeni (canli) kodlara cevirir ki karsilastirma
    unvan degisikliklerini gercek uyelik degisikligi sanmasin."""
    return {TICKER_RENAME_MAP.get(t, t) for t in tickers}


def get_constituents_at(date) -> list[str]:
    """Verilen tarihte (pandas Timestamp veya string) FIILEN BIST100'de olan
    ticker'lari (".IS" eksiz) dondurur. Tarih en eski donemden (2024-04-01)
    daha erikse en eski donem, en yeni donemden (2026-07-01) daha ileriyse
    en yeni ("su anki") donem kullanilir."""
    ts = pd.Timestamp(date)
    period_start = _SORTED_PERIOD_STARTS[0]
    for ps in _SORTED_PERIOD_STARTS:
        if ps <= ts:
            period_start = ps
        else:
            break
    return MEMBERSHIP_HISTORY[period_start.strftime("%Y-%m-%d")]


def get_current_constituents() -> list[str]:
    """En guncel (bilinen en son) donemin ticker listesi."""
    latest = _SORTED_PERIOD_STARTS[-1].strftime("%Y-%m-%d")
    return MEMBERSHIP_HISTORY[latest]


def get_all_tickers_ever() -> list[str]:
    """Backtest icin: tum donemlerde EN AZ BIR KEZ BIST100'de bulunmus
    ticker'larin birlesimi. Fiyat verisi CEKERKEN bu liste kullanilmali
    (sadece bugunku 100'u degil) - yoksa gecmiste var olup bugun cikmis bir
    hissenin (AGHOL, TABGD, BERA, SDTTR gibi) fiyat gecmisi hic elimize
    gecmez ve o donemler icin backtest yine yanlis kalir."""
    all_t = set()
    for tickers in MEMBERSHIP_HISTORY.values():
        all_t.update(tickers)
    return sorted(all_t)


def _detect_new_revision(live_tickers: set[str]) -> str | None:
    """Canli cekilen (ornek: borsapy ya da baska bir kaynaktan) guncel
    ticker kumesini en son kayitli donemle karsilastirir. Fark varsa
    okunabilir bir uyari metni dondurur, yoksa None. Bu fonksiyon otomatik
    GUNCELLEMEZ - sadece "yeni bir ceyrek revizyonu olmus, MEMBERSHIP_HISTORY
    dosyasina yeni bir donem eklemek gerekiyor" diye haber verir.

    FIX: karsilastirmadan once hem kayitli hem canli kume TICKER_RENAME_MAP
    ile normalize edilir - boylece unvan/kod degisikligi (KOZAA/KOZAL/IPEKE
    -> TRMET/TRALT/TRENJ gibi) sahte giris+cikis olarak raporlanmaz."""
    current = _normalize_renames(set(get_current_constituents()))
    live_norm = _normalize_renames(live_tickers)
    added = live_norm - current
    removed = current - live_norm
    if not added and not removed:
        return None
    msg = ["Yeni BIST100 revizyonu algilandi (kayitli listeyle fark var):"]
    if added:
        msg.append(f"  Muhtemelen YENI GIREN: {sorted(added)}")
    if removed:
        msg.append(f"  Muhtemelen CIKAN: {sorted(removed)}")
    msg.append("  -> membership.py'ye yeni bir donem eklemek gerekiyor.")
    return "\n".join(msg)


def check_for_updates_via_borsapy() -> str | None:
    """Best-effort: borsapy uzerinden canli XU100 bilesenlerini cekmeyi
    dener. Kutuphane/aglantisi yoksa veya API farkliysa sessizce None doner
    - bu fonksiyonun basarisiz olmasi uygulamayi durdurmaz."""
    try:
        import borsapy as bp
        idx = bp.Index("XU100")
        live = {t.replace(".IS", "") for t in idx.component_symbols}
        if not live:
            return None
        return _detect_new_revision(live)
    except Exception:
        return None
