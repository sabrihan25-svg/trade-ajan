"""HAYATTA KALMA KURALLARI (beyin tarafi).
Bu kurallar modellere sorulmaz; kod uygular, modeller asamaz.
Ayni kurallar kopru/kopru.py icinde gercek bakiyeye gore tekrar uygulanir."""
import datetime as dt

RISK_ORANI = 0.01            # islem basina ~%1
RISK_TAVAN = 0.015           # en fazla %1,5
OLUM_CIZGISI = 0.70          # baslangicin %70'i -> kalici dur
GUNLUK_ZARAR_SINIRI = 0.03   # %3
HAFTALIK_ZARAR_SINIRI = 0.06 # %6
ARDISIK_ZARAR_MOLA = 3       # art arda 3 zarar -> 24 saat mola
MOLA_SAAT = 24
EN_DUSUK_RR = 1.5            # hedef >= 1,5 x stop
EN_FAZLA_FARK_STOP_ORANI = 0.10   # alis-satis farki stop mesafesinin %10'unu gecemez
EN_FAZLA_FARK_ATR_ORANI = 0.20    # alis-satis farki 1s ATR'nin %20'sini gecemez
HABER_PENCERE_DK = 30        # onemli ABD verisinde +-30 dk islem yok
CUMA_SON_SINYAL_UTC = 19     # Cuma 19:00 UTC'den sonra yeni islem yok
CUMA_KAPAT_UTC = (20, 45)    # Cuma 20:45 UTC acik islem kapatilir (hafta sonuna tasinmaz)
EN_KUCUK_STOP_ATR15 = 1.0    # stop en az 1 x ATR(15dk) (cok dar stop olmaz)
EN_BUYUK_STOP_ATR1S = 4.0    # stop en fazla 4 x ATR(1s)


def utc_simdi():
    return dt.datetime.now(dt.timezone.utc)


def piyasa_acik_mi(an):
    """Forex: Pazar 22:00 UTC - Cuma 21:00 UTC."""
    g = an.weekday()  # 0=Pzt ... 6=Paz
    if g == 5:
        return False
    if g == 6:
        return an.hour >= 22
    if g == 4:
        return an.hour < 21
    return True


def yeni_islem_saati_uygun_mu(an):
    if not piyasa_acik_mi(an):
        return False, "piyasa kapali"
    if an.weekday() == 4 and an.hour >= CUMA_SON_SINYAL_UTC:
        return False, "Cuma aksami: hafta sonuna islem tasinmaz"
    if an.weekday() == 6 and an.hour < 23:
        return False, "Pazar acilisi: ilk saat bekleniyor"
    return True, ""


def cuma_kapanis_mi(an):
    return an.weekday() == 4 and (an.hour, an.minute) >= CUMA_KAPAT_UTC


def haber_yasagi(an, olaylar):
    """olaylar: [{"zaman": datetime, "ulke": "USD", "etki": "High", "baslik": ...}]"""
    for o in olaylar:
        if o["ulke"] == "USD" and o["etki"] == "High":
            fark = abs((o["zaman"] - an).total_seconds()) / 60
            if fark <= HABER_PENCERE_DK:
                return True, o["baslik"]
    return False, ""


def sonraki_haber_yasagi_baslangici(an, olaylar):
    gelecek = [o["zaman"] - dt.timedelta(minutes=HABER_PENCERE_DK)
               for o in olaylar if o["ulke"] == "USD" and o["etki"] == "High" and o["zaman"] > an]
    return min(gelecek) if gelecek else None


def hesap_kontrol(golge, an):
    """Golge hesap uzerinden genel durumu kontrol eder. (izin, sebep) dondurur.
    golge: durum['golge'] sozlugu. Gerekirse gun/hafta baslangicini gunceller."""
    if golge.get("olu"):
        return False, "OLUM CIZGISI: ajan kalici olarak durduruldu"
    bas = golge["baslangic"]
    bak = golge["bakiye"]
    if bak <= bas * OLUM_CIZGISI:
        golge["olu"] = True
        return False, "OLUM CIZGISI asildi (bakiye baslangicin %70'ine indi). Ajan kalici durdu."

    gun = an.strftime("%Y-%m-%d")
    if golge.get("gun", {}).get("tarih") != gun:
        golge["gun"] = {"tarih": gun, "bakiye": bak}
    hafta = an.strftime("%G-W%V")
    if golge.get("hafta", {}).get("tarih") != hafta:
        golge["hafta"] = {"tarih": hafta, "bakiye": bak}

    if bak <= golge["gun"]["bakiye"] * (1 - GUNLUK_ZARAR_SINIRI):
        return False, "gunluk %3 zarar siniri doldu"
    if bak <= golge["hafta"]["bakiye"] * (1 - HAFTALIK_ZARAR_SINIRI):
        return False, "haftalik %6 zarar siniri doldu"

    mola = golge.get("mola_bitis")
    if mola and an < dt.datetime.fromisoformat(mola):
        return False, f"art arda {ARDISIK_ZARAR_MOLA} zarar: mola {mola} UTC'ye kadar"
    if golge.get("acik_islem"):
        return False, "zaten acik islem var (ayni anda tek islem)"
    return True, ""


def zarar_sonrasi_guncelle(golge, sonuc_r, an):
    if sonuc_r < 0:
        golge["ardisik_zarar"] = golge.get("ardisik_zarar", 0) + 1
        if golge["ardisik_zarar"] >= ARDISIK_ZARAR_MOLA:
            golge["mola_bitis"] = (an + dt.timedelta(hours=MOLA_SAAT)).isoformat()
            golge["ardisik_zarar"] = 0
    else:
        golge["ardisik_zarar"] = 0


def sinyal_dogrula(yon, stop_yuzde, hedef_yuzde, fiyat, fark, atr15, atr1s):
    """Sinyalin parametrelerini kurallara gore denetle. (gecerli, sebep)."""
    if yon not in ("long", "short"):
        return False, "yon gecersiz"
    if not (stop_yuzde and hedef_yuzde) or stop_yuzde <= 0 or hedef_yuzde <= 0:
        return False, "stop/hedef eksik"
    if hedef_yuzde < stop_yuzde * EN_DUSUK_RR - 1e-12:
        return False, f"hedef stopun {EN_DUSUK_RR} katindan kucuk"
    stop_mesafe = fiyat * stop_yuzde / 100
    if atr15 and stop_mesafe < atr15 * EN_KUCUK_STOP_ATR15:
        return False, "stop cok dar (15dk ATR'den kucuk)"
    if atr1s and stop_mesafe > atr1s * EN_BUYUK_STOP_ATR1S:
        return False, "stop cok genis (1s ATR'nin 4 katindan buyuk)"
    if fark > stop_mesafe * EN_FAZLA_FARK_STOP_ORANI:
        return False, "alis-satis farki stopa gore cok genis"
    if atr1s and fark > atr1s * EN_FAZLA_FARK_ATR_ORANI:
        return False, "alis-satis farki cok genis"
    return True, ""
