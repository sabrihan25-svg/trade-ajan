"""Golge (kagit) hesap ve model isabet karnesi.
- Golge hesap 100 $ ile baslar; her kurul sinyalini %1 riskle kagit uzerinde takip eder.
- Karne: her modelin long/short oyu, kendi stop/hedefiyle 'hayalet islem' olarak takip edilir
  (sinyal olussa da olusmasa da). Boylece hangi modelin daha isabetli oldugu gorulur.
Sonuclar R cinsinden: +R = hedef, -1 = stop. Ayni mumda ikisi de degerse once stop sayilir (temkinli)."""
import datetime as dt

from . import kurallar


def _mum_zamani(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc)


def islem_ilerlet(islem, mumlar, an):
    """Acik islemi yeni mumlarla ilerlet. Kapandiysa (sonuc, sonuc_r, kapanis_zamani) dondurur."""
    giris_t = dt.datetime.fromisoformat(islem["acilis"]).timestamp()
    for m in mumlar:
        if m["t"] < giris_t or m["t"] <= islem.get("son_mum_t", 0):
            continue
        islem["son_mum_t"] = m["t"]
        if islem["yon"] == "long":
            stop_vurdu = m["l"] <= islem["stop"]
            hedef_vurdu = m["h"] >= islem["hedef"]
        else:
            stop_vurdu = m["h"] >= islem["stop"]
            hedef_vurdu = m["l"] <= islem["hedef"]
        kapanis = (_mum_zamani(m["t"]) + dt.timedelta(minutes=15)).isoformat()
        if stop_vurdu:
            return "zarar", -1.0, kapanis
        if hedef_vurdu:
            return "kar", round(islem["rr"], 3), kapanis
        # Cuma kapanisi: hafta sonuna tasinmaz, mum kapanisindan cik
        if kurallar.cuma_kapanis_mi(_mum_zamani(m["t"]) + dt.timedelta(minutes=15)):
            hareket = (m["c"] - islem["giris"]) if islem["yon"] == "long" else (islem["giris"] - m["c"])
            r = round(hareket / abs(islem["giris"] - islem["stop"]), 3)
            return ("kar" if r >= 0 else "zarar"), r, kapanis
    return None


def islem_olustur(sembol, yon, giris, stop_yuzde, hedef_yuzde, fark, an, kaynak):
    stop_m = giris * stop_yuzde / 100
    hedef_m = giris * hedef_yuzde / 100
    # Alis-satis farki maliyeti: girisi aleyhte kaydir
    if yon == "long":
        giris_gercek = giris + fark
        stop, hedef = giris_gercek - stop_m, giris_gercek + hedef_m
    else:
        giris_gercek = giris - fark
        stop, hedef = giris_gercek + stop_m, giris_gercek - hedef_m
    return {"sembol": sembol, "yon": yon, "giris": giris_gercek, "stop": stop, "hedef": hedef,
            "rr": hedef_yuzde / stop_yuzde if stop_yuzde else 0, "acilis": an.isoformat(),
            "kaynak": kaynak}


def golge_ac(durum, islem, an):
    g = durum["golge"]
    islem["risk_tutar"] = round(g["bakiye"] * kurallar.RISK_ORANI, 4)
    g["acik_islem"] = islem


def golge_guncelle(durum, mum_getir, an):
    """Acik golge islemini ilerlet; kapandiysa bakiyeyi ve kurallari guncelle."""
    g = durum["golge"]
    islem = g.get("acik_islem")
    if not islem:
        return None
    sonuc = islem_ilerlet(islem, mum_getir(islem["sembol"]), an)
    if not sonuc:
        return None
    ad, r, kapanis = sonuc
    tutar = round(islem["risk_tutar"] * r, 4)
    g["bakiye"] = round(g["bakiye"] + tutar, 4)
    kayit = {**islem, "sonuc": ad, "sonuc_r": r, "tutar": tutar, "kapanis": kapanis,
             "bakiye_sonra": g["bakiye"]}
    g.setdefault("gecmis", []).append(kayit)
    g["gecmis"] = g["gecmis"][-200:]
    g["acik_islem"] = None
    kurallar.zarar_sonrasi_guncelle(g, r, an)
    if g["bakiye"] <= g["baslangic"] * kurallar.OLUM_CIZGISI:
        g["olu"] = True
    return kayit


def karne_oy_kaydet(durum, ad, oy):
    k = durum["karne"].setdefault(ad, {"toplanti": 0, "long": 0, "short": 0, "bekle": 0, "cevapsiz": 0,
                                        "kazanan": 0, "kaybeden": 0, "toplam_R": 0.0})
    k["toplanti"] += 1
    if "hata" in oy:
        k["cevapsiz"] += 1
    elif oy["yon"] == "wait":
        k["bekle"] += 1
    else:
        k[oy["yon"]] += 1


def hayalet_ekle(durum, ad, islem):
    islem["model"] = ad
    durum.setdefault("hayaletler", []).append(islem)


def hayaletleri_guncelle(durum, mum_getir, an):
    kalan = []
    for h in durum.get("hayaletler", []):
        try:
            sonuc = islem_ilerlet(h, mum_getir(h["sembol"]), an)
        except Exception:
            kalan.append(h)
            continue
        if not sonuc:
            # 5 gunden eski hayaletleri kapat (sonucsuz)
            if an - dt.datetime.fromisoformat(h["acilis"]) > dt.timedelta(days=5):
                continue
            kalan.append(h)
            continue
        ad, r, _ = sonuc
        k = durum["karne"].get(h["model"])
        if k is not None:
            k["kazanan" if r > 0 else "kaybeden"] += 1
            k["toplam_R"] = round(k["toplam_R"] + r, 3)
    durum["hayaletler"] = kalan
