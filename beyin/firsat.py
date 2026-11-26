"""Firsat tarayici: kod, modelleri cagirmadan once uygun bir kurulum arar.
1 saatlik trend + 15 dakikalik giris (geri cekilmenin bitmesi ya da seviye kirilimi)."""
from . import gostergeler as g


def trend(h1):
    """h1: gostergeler.ozet() ciktisi. 'yukari' / 'asagi' / None"""
    if None in (h1["ema50"], h1["ema200"], h1["ema50_once"]):
        return None
    if h1["ema50"] > h1["ema200"] and h1["kapanis"] > h1["ema200"] and h1["ema50"] >= h1["ema50_once"]:
        return "yukari"
    if h1["ema50"] < h1["ema200"] and h1["kapanis"] < h1["ema200"] and h1["ema50"] <= h1["ema50_once"]:
        return "asagi"
    return None


def tara(mum_h1, mum_m15):
    """Bir firsat varsa sozluk, yoksa None dondurur."""
    if len(mum_h1) < 210 or len(mum_m15) < 60:
        return None
    h1 = g.ozet(mum_h1)
    m15 = g.ozet(mum_m15)
    yon_trend = trend(h1)
    if yon_trend is None or m15["atr"] is None or m15["ema50"] is None or m15["rsi"] is None:
        return None

    son, onceki = mum_m15[-1], mum_m15[-2]
    atr15 = m15["atr"]
    e50 = m15["seriler"]["ema50"]
    rsis = m15["seriler"]["rsi"]
    son8 = range(len(mum_m15) - 9, len(mum_m15) - 1)
    tepe, dip = m15["son_tepe"], m15["son_dip"]
    bar_boyu = son["h"] - son["l"]
    if bar_boyu > 2.5 * atr15:
        return None  # ani sicrama mumu: girme

    temel = {"h1": h1, "m15": m15, "trend": yon_trend}

    if yon_trend == "yukari":
        # Geri cekilme bitti mi: son 8 mumda EMA50'ye yaklasti ya da RSI < 45, simdi yukari dondu
        cekildi = any(
            (e50[i] is not None and mum_m15[i]["l"] <= e50[i] + 0.3 * atr15) or (rsis[i] is not None and rsis[i] < 45)
            for i in son8)
        dondu = son["c"] > son["o"] and son["c"] > onceki["h"] and son["c"] > m15["ema50"] and m15["rsi"] > (m15["rsi_once"] or 0)
        if cekildi and dondu:
            return {**temel, "tur": "geri_cekilme_bitti", "yon": "long",
                    "aciklama": "1s trend yukari; 15dk'da EMA50'ye geri cekilme sonrasi yukari donus mumu"}
        if tepe and son["c"] > tepe and onceki["c"] <= tepe:
            return {**temel, "tur": "seviye_kirilimi", "yon": "long", "seviye": tepe,
                    "aciklama": f"1s trend yukari; 15dk'da son 20 mumun tepesi ({tepe:.5g}) yukari kirildi"}
    else:
        cekildi = any(
            (e50[i] is not None and mum_m15[i]["h"] >= e50[i] - 0.3 * atr15) or (rsis[i] is not None and rsis[i] > 55)
            for i in son8)
        dondu = son["c"] < son["o"] and son["c"] < onceki["l"] and son["c"] < m15["ema50"] and m15["rsi"] < (m15["rsi_once"] or 100)
        if cekildi and dondu:
            return {**temel, "tur": "geri_cekilme_bitti", "yon": "short",
                    "aciklama": "1s trend asagi; 15dk'da EMA50'ye geri cekilme sonrasi asagi donus mumu"}
        if dip and son["c"] < dip and onceki["c"] >= dip:
            return {**temel, "tur": "seviye_kirilimi", "yon": "short", "seviye": dip,
                    "aciklama": f"1s trend asagi; 15dk'da son 20 mumun dibi ({dip:.5g}) asagi kirildi"}
    return None
