"""Piyasa verisi, haber basliklari ve ekonomik takvim. Anahtar gerektirmez."""
import datetime as dt
import time
import xml.etree.ElementTree as ET

import requests

BASLIK = {"User-Agent": "Mozilla/5.0 (trade-ajan)"}
HABER_KAYNAKLARI = [
    "https://www.fxstreet.com/rss/news",
    "https://www.investing.com/rss/news_1.rss",
]
TAKVIM_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def _get(url, **kw):
    son_hata = None
    for deneme in range(3):
        try:
            r = requests.get(url, headers=BASLIK, timeout=20, **kw)
            if r.status_code == 200:
                return r
            son_hata = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            son_hata = repr(e)
        time.sleep(2 * (deneme + 1))
    raise RuntimeError(f"{url}: {son_hata}")


def mumlar(veri_kodu, aralik, donem):
    """Yahoo Finance mumlari. aralik: '15m' veya '60m'.
    (kapanmis_mumlar, anlik_fiyat) dondurur."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{veri_kodu}"
    r = _get(url, params={"interval": aralik, "range": donem})
    sonuc = r.json()["chart"]["result"][0]
    zaman = sonuc["timestamp"]
    q = sonuc["indicators"]["quote"][0]
    adim = {"15m": 900, "60m": 3600}[aralik]
    simdi = time.time()
    liste = []
    for i, t in enumerate(zaman):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        if t + adim > simdi:  # henuz kapanmamis mum
            continue
        liste.append({"t": int(t), "o": o, "h": h, "l": l, "c": c})
    anlik = sonuc.get("meta", {}).get("regularMarketPrice")
    return liste, anlik


def haber_basliklari(en_fazla=10):
    basliklar = []
    for url in HABER_KAYNAKLARI:
        try:
            kok = ET.fromstring(_get(url).content)
            for item in kok.iter("item"):
                b = (item.findtext("title") or "").strip()
                z = (item.findtext("pubDate") or "").strip()
                if b:
                    basliklar.append(f"{z[:22]} | {b}")
                if len(basliklar) >= en_fazla:
                    break
        except Exception:
            continue
        if len(basliklar) >= en_fazla:
            break
    return basliklar[:en_fazla]


def takvim():
    """Bu haftanin ekonomik takvimi. [{"zaman": datetime(UTC), "ulke", "etki", "baslik"}]"""
    veri = _get(TAKVIM_URL).json()
    olaylar = []
    for o in veri:
        try:
            z = dt.datetime.fromisoformat(o["date"]).astimezone(dt.timezone.utc)
        except Exception:
            continue
        olaylar.append({
            "zaman": z, "ulke": o.get("country", ""), "etki": o.get("impact", ""),
            "baslik": o.get("title", ""), "tahmin": o.get("forecast", ""), "onceki": o.get("previous", ""),
        })
    return olaylar
