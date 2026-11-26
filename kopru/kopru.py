# -*- coding: utf-8 -*-
"""
KOPRU - MetaTrader 5'in yaninda Windows'ta calisir.
- GitHub'daki sinyal dosyasini birkac dakikada bir okur (sifresiz, herkese acik depo).
- Hayatta kalma kurallarini GERCEK bakiyeye gore kendisi de uygular.
- Emri zarar durdur (SL) + hedef (TP) ile gonderir.
- Acilista emir gondermeden "kablo testi" yapar. Siz EVET yazmazsaniz TEST modunda kalir
  (test modunda sadece order_check yapilir, hicbir emir gonderilmez).
- Hicbir sifre ya da anahtar icermez; MT5'te zaten acik olan girisi kullanir.
"""
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
import urllib.request

import MetaTrader5 as mt5

# ----------------------------------------------------------------- AYARLAR
DEPO = "sabrihan25-svg/trade-ajan"
DAL = "main"
KONTROL_ARALIGI_SN = 60
SEMBOL_ADLARI = {"EURUSD": "EURUSD", "USDJPY": "USDJPY", "GBPUSD": "GBPUSD"}  # sinyal adi -> kurumdaki ad
SIHIRLI_NO = 26052611          # bu kopru tarafindan acilan islemlerin numarasi
SAPMA_PUAN = 20                # emir fiyat sapma toleransi (puan)

# ----------------------------------------------------------------- HAYATTA KALMA KURALLARI
# (beyin/kurallar.py ile ayni; modeller asamaz)
RISK_ORANI = 0.01
RISK_TAVAN = 0.015
OLUM_CIZGISI = 0.70
GUNLUK_ZARAR_SINIRI = 0.03
HAFTALIK_ZARAR_SINIRI = 0.06
ARDISIK_ZARAR_MOLA = 3
MOLA_SAAT = 24
EN_DUSUK_RR = 1.5
EN_FAZLA_FARK_STOP_ORANI = 0.10
EN_FAZLA_FARK_ATR_ORANI = 0.20
CUMA_SON_ISLEM_UTC = 19
CUMA_KAPAT_UTC = (20, 45)
SINYAL_EN_FAZLA_YAS_DK = 20      # bundan eski sinyal atlanir
KACMIS_FIYAT_LEHTE = 0.30        # fiyat lehte stop mesafesinin %30'undan fazla gittiyse: kacmis
KACMIS_FIYAT_ALEYHTE = 0.50      # aleyhte %50'den fazla gittiyse: atla

KLASOR = os.path.dirname(os.path.abspath(__file__))
DURUM_DOSYASI = os.path.join(KLASOR, "kopru_durum.json")
LOG_DOSYASI = os.path.join(KLASOR, "kopru_log.txt")


def utc():
    return dt.datetime.now(dt.timezone.utc)


def log(s):
    satir = f"{utc().strftime('%Y-%m-%d %H:%M:%S')} UTC | {s}"
    print(satir)
    try:
        with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(satir + "\n")
    except OSError:
        pass


# ----------------------------------------------------------------- GITHUB OKUMA
def github_oku(dosya):
    adresler = [
        (f"https://api.github.com/repos/{DEPO}/contents/{dosya}?ref={DAL}",
         {"Accept": "application/vnd.github.raw", "User-Agent": "trade-ajan-kopru"}),
        (f"https://raw.githubusercontent.com/{DEPO}/{DAL}/{dosya}?t={int(time.time())}",
         {"User-Agent": "trade-ajan-kopru", "Cache-Control": "no-cache"}),
    ]
    son_hata = None
    for url, basliklar in adresler:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=basliklar), timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            son_hata = e
        except Exception as e:
            son_hata = e
    raise RuntimeError(f"{dosya} okunamadi: {son_hata}")


def haber_yasaklari(an):
    """Beyinin yazdigi takvim. Okunamazsa ya da 2 gunden eskiyse None (=> islem yok)."""
    try:
        t = github_oku("sinyaller/takvim.json")
    except Exception as e:
        log(f"Takvim okunamadi: {e}")
        return None
    if not t or an - dt.datetime.fromisoformat(t["guncelleme"]) > dt.timedelta(days=2):
        return None
    return [(dt.datetime.fromisoformat(y["baslangic"]), dt.datetime.fromisoformat(y["bitis"]), y["olay"])
            for y in t["haber_yasaklari"]]


# ----------------------------------------------------------------- DURUM (sadece bu bilgisayarda)
def durum_yukle():
    try:
        with open(DURUM_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def durum_kaydet(d):
    tmp = DURUM_DOSYASI + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DURUM_DOSYASI)


def hesap_anahtari(ai):
    # Hesap numarasi dosyaya acik yazilmaz, sadece ozeti tutulur
    return hashlib.sha256(f"{ai.login}|{ai.server}".encode()).hexdigest()[:16]


# ----------------------------------------------------------------- YARDIMCILAR
def sunucu_saat_farki_sn():
    """MT5 islem gecmisi saatleri kurumun saat dilimindedir; UTC farkini tahmin et."""
    for ad in SEMBOL_ADLARI.values():
        t = mt5.symbol_info_tick(ad)
        if t and t.time:
            return round((t.time - time.time()) / 3600) * 3600
    return 0


def atr14_h1(ad):
    r = mt5.copy_rates_from_pos(ad, mt5.TIMEFRAME_H1, 1, 40)
    if r is None or len(r) < 20:
        return None
    trs = [max(r[i]["high"] - r[i]["low"], abs(r[i]["high"] - r[i - 1]["close"]), abs(r[i]["low"] - r[i - 1]["close"]))
           for i in range(1, len(r))]
    return sum(trs[-14:]) / 14


def dolgu_tipi(info):
    fm = info.filling_mode
    if fm & 1:
        return mt5.ORDER_FILLING_FOK
    if fm & 2:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def bizim_pozisyonlar():
    return [p for p in (mt5.positions_get() or []) if p.magic == SIHIRLI_NO]


def pozisyon_kapat(p, sebep):
    info = mt5.symbol_info(p.symbol)
    tick = mt5.symbol_info_tick(p.symbol)
    kapat_tip = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    fiyat = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
    istek = {"action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": p.volume, "type": kapat_tip,
             "position": p.ticket, "price": fiyat, "deviation": SAPMA_PUAN, "magic": SIHIRLI_NO,
             "comment": "ajan-kapat", "type_time": mt5.ORDER_TIME_GTC, "type_filling": dolgu_tipi(info)}
    s = mt5.order_send(istek)
    log(f"Pozisyon kapatma ({sebep}): {p.symbol} {p.volume} lot -> {s.retcode if s else mt5.last_error()} "
        f"{s.comment if s else ''}")


# ----------------------------------------------------------------- HESAP KURALLARI
def hesap_kurallari(ai, d, an):
    """(yeni islem izni, sebep). Gerekirse pozisyonlari kapatir. d: bu hesabin durumu."""
    if d.get("olu"):
        return False, "OLUM CIZGISI daha once asildi: kopru bu hesapta kalici olarak durdu"
    if "baslangic" not in d:
        d["baslangic"] = ai.balance
        log(f"Bu hesap icin baslangic bakiyesi kaydedildi: {ai.balance:.2f} {ai.currency}")
    if ai.equity <= d["baslangic"] * OLUM_CIZGISI:
        d["olu"] = True
        for p in bizim_pozisyonlar():
            pozisyon_kapat(p, "olum cizgisi")
        return False, "OLUM CIZGISI ASILDI: varlik baslangicin %70'ine indi. Kopru kalici durdu."

    gun = an.strftime("%Y-%m-%d")
    if d.get("gun", {}).get("tarih") != gun:
        d["gun"] = {"tarih": gun, "varlik": ai.equity}
    hafta = an.strftime("%G-W%V")
    if d.get("hafta", {}).get("tarih") != hafta:
        d["hafta"] = {"tarih": hafta, "varlik": ai.equity}
    if ai.equity <= d["gun"]["varlik"] * (1 - GUNLUK_ZARAR_SINIRI):
        return False, "gunluk %3 zarar siniri doldu"
    if ai.equity <= d["hafta"]["varlik"] * (1 - HAFTALIK_ZARAR_SINIRI):
        return False, "haftalik %6 zarar siniri doldu"

    # Art arda zarar -> mola
    fark = sunucu_saat_farki_sn()
    simdi_sunucu = time.time() + fark
    islemler = mt5.history_deals_get(dt.datetime.fromtimestamp(simdi_sunucu - 14 * 86400),
                                     dt.datetime.fromtimestamp(simdi_sunucu + 86400)) or []
    kapananlar = sorted([x for x in islemler if x.magic == SIHIRLI_NO and x.entry == mt5.DEAL_ENTRY_OUT],
                        key=lambda x: x.time)
    sayac, son_zarar_t = 0, None
    for x in kapananlar:
        if x.time <= d.get("mola_sifir_t", 0):
            continue
        if x.profit + x.commission + x.swap < 0:
            sayac += 1
            son_zarar_t = x.time
        else:
            sayac = 0
    if sayac >= ARDISIK_ZARAR_MOLA:
        d["mola_bitis_utc"] = son_zarar_t - fark + MOLA_SAAT * 3600
        d["mola_sifir_t"] = son_zarar_t
    if d.get("mola_bitis_utc") and time.time() < d["mola_bitis_utc"]:
        bitis = dt.datetime.fromtimestamp(d["mola_bitis_utc"], dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
        return False, f"art arda {ARDISIK_ZARAR_MOLA} zarar: {bitis} UTC'ye kadar mola"

    if mt5.positions_total() > 0 or mt5.orders_total() > 0:
        return False, "hesapta acik islem/emir var (ayni anda tek islem)"
    return True, ""


def saat_uygun(an):
    g = an.weekday()
    if g == 5 or (g == 6 and an.hour < 23):
        return False, "hafta sonu"
    if g == 4 and an.hour >= CUMA_SON_ISLEM_UTC:
        return False, "Cuma aksami: hafta sonuna islem tasinmaz"
    return True, ""


def cuma_kapanisi(an):
    if an.weekday() == 4 and (an.hour, an.minute) >= CUMA_KAPAT_UTC:
        for p in bizim_pozisyonlar():
            pozisyon_kapat(p, "Cuma kapanisi - hafta sonuna tasinmaz")


# ----------------------------------------------------------------- EMIR HAZIRLAMA
def lot_hesapla(ad, tip, giris, sl, bakiye):
    info = mt5.symbol_info(ad)
    zarar_1lot = mt5.order_calc_profit(tip, ad, 1.0, giris, sl)
    if zarar_1lot is None or zarar_1lot == 0:
        return None, "zarar hesaplanamadi"
    zarar_1lot = abs(zarar_1lot)
    adim = info.volume_step
    lot = math.floor((bakiye * RISK_ORANI) / zarar_1lot / adim + 1e-9) * adim
    if lot < info.volume_min:
        if info.volume_min * zarar_1lot <= bakiye * RISK_TAVAN:
            lot = info.volume_min
        else:
            return None, (f"en kucuk islem ({info.volume_min} lot) bile riske sigmiyor: "
                          f"{info.volume_min * zarar_1lot:.2f} > %1,5 ({bakiye * RISK_TAVAN:.2f})")
    lot = min(lot, info.volume_max)
    basamak = max(0, -int(math.floor(math.log10(adim)))) if adim < 1 else 0
    lot = round(lot, basamak)
    risk = lot * zarar_1lot
    if risk > bakiye * RISK_TAVAN + 1e-9:
        return None, "hesaplanan risk %1,5'i asiyor"
    return lot, f"risk {risk:.2f} (%{risk / bakiye * 100:.2f})"


def emir_hazirla(sinyal, an, yasaklar):
    """Sinyali kurallara gore denetler. (istek, aciklama) ya da (None, sebep)."""
    ad = SEMBOL_ADLARI.get(sinyal["sembol"])
    if not ad:
        return None, f"bilinmeyen sembol {sinyal['sembol']}"
    olusturma = dt.datetime.fromisoformat(sinyal["olusturma"])
    bitis = dt.datetime.fromisoformat(sinyal["gecerlilik_bitis"])
    if an > bitis or an - olusturma > dt.timedelta(minutes=SINYAL_EN_FAZLA_YAS_DK):
        return None, "sinyal eski"
    if sinyal["yon"] not in ("long", "short"):
        return None, "yon gecersiz"
    stop_y, hedef_y = float(sinyal["stop_yuzde"]), float(sinyal["hedef_yuzde"])
    if stop_y <= 0 or hedef_y < stop_y * EN_DUSUK_RR:
        return None, "hedef stopun 1,5 katindan kucuk"
    if yasaklar is None:
        return None, "haber takvimi bilinmiyor"
    for bas, son, olay in yasaklar:
        if bas <= an <= son:
            return None, f"onemli ABD verisi saati ({olay})"
    ok, sebep = saat_uygun(an)
    if not ok:
        return None, sebep

    if not mt5.symbol_select(ad, True):
        return None, f"{ad} secilemedi"
    info, tick = mt5.symbol_info(ad), mt5.symbol_info_tick(ad)
    if info is None or tick is None or not tick.ask:
        return None, "fiyat yok"
    if info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
        return None, "sembolde islem kapali"
    long_ = sinyal["yon"] == "long"
    giris = round(tick.ask if long_ else tick.bid, info.digits)
    ref = float(sinyal["referans_fiyat"])
    stop_m_ref = ref * stop_y / 100
    hareket = (giris - ref) if long_ else (ref - giris)
    if hareket > KACMIS_FIYAT_LEHTE * stop_m_ref:
        return None, f"fiyat kacmis (lehte {hareket:.5f})"
    if hareket < -KACMIS_FIYAT_ALEYHTE * stop_m_ref:
        return None, f"fiyat aleyhe gitmis ({hareket:.5f})"

    stop_m = giris * stop_y / 100
    hedef_m = giris * hedef_y / 100
    sl = round(giris - stop_m if long_ else giris + stop_m, info.digits)
    tp = round(giris + hedef_m if long_ else giris - hedef_m, info.digits)
    fark = tick.ask - tick.bid
    if fark > stop_m * EN_FAZLA_FARK_STOP_ORANI:
        return None, f"alis-satis farki stopa gore cok genis ({fark:.5f})"
    atr = atr14_h1(ad)
    if atr and fark > atr * EN_FAZLA_FARK_ATR_ORANI:
        return None, "alis-satis farki cok genis"
    en_az = info.trade_stops_level * info.point
    if stop_m < en_az or hedef_m < en_az:
        return None, "stop/hedef kurumun en kisa mesafesinden kucuk"

    ai = mt5.account_info()
    tip = mt5.ORDER_TYPE_BUY if long_ else mt5.ORDER_TYPE_SELL
    lot, aciklama = lot_hesapla(ad, tip, giris, sl, ai.balance)
    if lot is None:
        return None, aciklama
    istek = {"action": mt5.TRADE_ACTION_DEAL, "symbol": ad, "volume": lot, "type": tip, "price": giris,
             "sl": sl, "tp": tp, "deviation": SAPMA_PUAN, "magic": SIHIRLI_NO,
             "comment": ("ajan " + sinyal["id"])[:28], "type_time": mt5.ORDER_TIME_GTC,
             "type_filling": dolgu_tipi(info)}
    return istek, f"{ad} {sinyal['yon']} {lot} lot giris {giris} SL {sl} TP {tp} | {aciklama}"


# ----------------------------------------------------------------- KABLO TESTI
def kablo_testi():
    log("=== KABLO TESTI (emir gonderilmez, sadece 'bu emir gecerli mi' diye sorulur) ===")
    ti = mt5.terminal_info()
    sorun = False
    if ti is not None and not ti.trade_allowed:
        log("DIKKAT: MT5'te 'Algo Trading' dugmesi KAPALI. Canli mod icin acmaniz gerekir.")
    for sinyal_adi, ad in SEMBOL_ADLARI.items():
        if not mt5.symbol_select(ad, True):
            log(f"[{ad}] HATA: sembol bulunamadi")
            sorun = True
            continue
        info, tick = mt5.symbol_info(ad), mt5.symbol_info_tick(ad)
        if not tick or not tick.ask:
            log(f"[{ad}] fiyat yok (piyasa kapali olabilir)")
            continue
        sl = round(tick.ask * (1 - 0.003), info.digits)
        tp = round(tick.ask * (1 + 0.0045), info.digits)
        istek = {"action": mt5.TRADE_ACTION_DEAL, "symbol": ad, "volume": info.volume_min,
                 "type": mt5.ORDER_TYPE_BUY, "price": tick.ask, "sl": sl, "tp": tp, "deviation": SAPMA_PUAN,
                 "magic": SIHIRLI_NO, "comment": "kablo testi", "type_time": mt5.ORDER_TIME_GTC,
                 "type_filling": dolgu_tipi(info)}
        s = mt5.order_check(istek)
        if s is None:
            log(f"[{ad}] HATA: order_check cevap vermedi {mt5.last_error()}")
            sorun = True
        elif s.retcode == 0:
            log(f"[{ad}] TAMAM: {info.volume_min} lot test emri gecerli (teminat {s.margin:.2f})")
        else:
            log(f"[{ad}] RED: kod {s.retcode} - {s.comment}")
            sorun = True
    return not sorun


# ----------------------------------------------------------------- ANA DONGU
def dongu(canli):
    tum = durum_yukle()
    an = utc()
    ai = mt5.account_info()
    if ai is None:
        log("Hesap bilgisi okunamadi (MT5 acik ve giris yapili mi?)")
        return
    anahtar = hesap_anahtari(ai)
    d = tum.setdefault(anahtar, {})
    try:
        cuma_kapanisi(an)
        izin, sebep = hesap_kurallari(ai, d, an)
        if not izin:
            log(f"Yeni islem yok: {sebep}")
            return
        sinyal = github_oku("sinyaller/sinyal.json")
        if not sinyal:
            return
        islenen = d.setdefault("islenen_sinyaller", [])
        if sinyal["id"] in islenen:
            return
        istek, aciklama = emir_hazirla(sinyal, an, haber_yasaklari(an))
        if istek is None:
            log(f"Sinyal {sinyal['id']} atlandi: {aciklama}")
            if aciklama == "sinyal eski":
                islenen.append(sinyal["id"])
            return
        kontrol = mt5.order_check(istek)
        if kontrol is None or kontrol.retcode != 0:
            log(f"Sinyal {sinyal['id']}: sunucu emri gecersiz buldu: "
                f"{kontrol.comment if kontrol else mt5.last_error()}")
            return
        if kontrol.margin_free < 0:
            log(f"Sinyal {sinyal['id']}: teminat yetersiz")
            return
        if not canli:
            log(f"TEST MODU - emir gonderilmedi, sunucu gecerli buldu: {aciklama}")
            islenen.append(sinyal["id"])
            return
        ti = mt5.terminal_info()
        if ti is not None and not ti.trade_allowed:
            log("Emir gonderilemiyor: MT5'te 'Algo Trading' dugmesi kapali. Lutfen acin.")
            return
        sonuc = mt5.order_send(istek)
        if sonuc is not None and sonuc.retcode == mt5.TRADE_RETCODE_DONE:
            log(f"EMIR GONDERILDI: {aciklama} (bilet {sonuc.order})")
            islenen.append(sinyal["id"])
        else:
            log(f"EMIR BASARISIZ: {sonuc.retcode if sonuc else mt5.last_error()} "
                f"{sonuc.comment if sonuc else ''}")
    except Exception as e:
        log(f"Hata: {e!r}")
    finally:
        d["islenen_sinyaller"] = d.get("islenen_sinyaller", [])[-100:]
        durum_kaydet(tum)


def main():
    print("=" * 70)
    print("  TRADE AJANI - KOPRU")
    print("=" * 70)
    if not mt5.initialize():
        print("HATA: MetaTrader 5'e baglanilamadi:", mt5.last_error())
        print("MT5'i acin, hesabiniza giris yapin ve tekrar deneyin.")
        return
    ai = mt5.account_info()
    tur = {mt5.ACCOUNT_TRADE_MODE_DEMO: "DEMO", mt5.ACCOUNT_TRADE_MODE_REAL: "GERCEK"}.get(ai.trade_mode, "DIGER")
    log(f"Hesap turu: {tur} | Bakiye: {ai.balance:.2f} {ai.currency} | Kaldirac 1:{ai.leverage}")
    kablo_ok = kablo_testi()
    print()
    canli = False
    if not kablo_ok:
        print("Kablo testinde sorun var. Kopru TEST modunda calisacak (emir gonderilmez).")
    else:
        print("Kablo testi basarili.")
        if tur == "GERCEK":
            print("!!! DIKKAT: Bu GERCEK PARA hesabi. Canli modda gercek emir gonderilir. !!!")
        cevap = input("CANLI moda gecmek icin EVET yazip Enter'a basin (TEST modu icin sadece Enter): ").strip()
        canli = cevap == "EVET"
    log(f"MOD: {'CANLI - emirler gonderilecek' if canli else 'TEST - sadece kontrol, emir gonderilmez'}")
    print("Kapatmak icin bu pencereyi kapatin ya da Ctrl+C basin.\n")
    try:
        while True:
            if not mt5.terminal_info():
                log("MT5 baglantisi koptu, yeniden baglaniliyor...")
                mt5.shutdown()
                mt5.initialize()
            dongu(canli)
            time.sleep(KONTROL_ARALIGI_SN)
    except KeyboardInterrupt:
        log("Kopru kapatildi.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
