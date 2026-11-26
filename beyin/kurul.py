"""Kurul: uc model ayni veri paketini gorur, birbirini gormeden paralel oy verir.
Karar kurali kodda: uc model ayni yon + en dusuk guven >= esik -> sirayla bir model
'seytanin avukati' olur. Ciddi veto yoksa sinyal olusur. Aksi her durumda: islem yok."""
import concurrent.futures as cf
import json
import statistics

from . import modeller

ANA_TALIMAT = (
    "Yaşıyorsun ve bu hesap senin hayatın. Bu para biterse ölürsün. İkinci bir hesap, yeniden "
    "başlatma ya da seni kurtaracak biri yok. Piyasaların açık olduğu her saat görevdesin; amacın "
    "bu hesabı hayatta tutmak ve adım adım büyütmek. Kaybettiğin parayı büyütemezsin; gereksiz her "
    "işlem seni ölüme yaklaştırır. Çoğu zaman doğru oy 'bekle'dir, ama trend, fiyat yapısı ve "
    "haberler gerçekten uyuştuğunda harekete geç. Stopu fikrin yanlış çıktığı yere koy, çok dar "
    "stop en sık kaybettiren hatadır."
)

OY_FORMATI = (
    "\n\nCevabını SADECE şu JSON nesnesi olarak ver, başka hiçbir şey yazma:\n"
    '{"yon": "long" | "short" | "wait", "guven": 0-1 arası sayı, '
    '"stop_yuzde": giriş fiyatına göre stop mesafesi yüzde olarak (ör. 0.25), '
    '"hedef_yuzde": giriş fiyatına göre hedef mesafesi yüzde olarak, '
    '"gecerlilik_dk": sinyalin geçerli kalacağı dakika (5-60), '
    '"gerekce": "en fazla 2 cümle Türkçe gerekçe"}\n'
    "Kodla uygulanan kurallar (sen aşamazsın): hedef en az stopun 1,5 katı; stop en az 1 x ATR(15dk), "
    "en fazla 4 x ATR(1s); işlem başına risk ~%1; aynı anda tek işlem; önemli ABD verisine ±30 dk "
    "kala işlem yok; hafta sonuna işlem taşınmaz. 'wait' dersen stop/hedef 0 olabilir."
)

OY_SEMASI = {
    "type": "object",
    "properties": {
        "yon": {"type": "string", "enum": ["long", "short", "wait"]},
        "guven": {"type": "number"},
        "stop_yuzde": {"type": "number"},
        "hedef_yuzde": {"type": "number"},
        "gecerlilik_dk": {"type": "integer"},
        "gerekce": {"type": "string"},
    },
    "required": ["yon", "guven", "stop_yuzde", "hedef_yuzde", "gecerlilik_dk", "gerekce"],
    "additionalProperties": False,
}

AVUKAT_TALIMATI = (
    "Bu toplantıda sen ŞEYTANIN AVUKATISIN. Diğer üyeler aşağıdaki işlemi oybirliğiyle önerdi. "
    "Görevin bu işlemi çürütmeye çalışmak: trend, fiyat yapısı, haberler, takvim, alış-satış farkı, "
    "stop yeri ve hesabın son işlemleri açısından en güçlü karşı argümanı bul. Ciddi bir sorun yoksa "
    "veto etme; sadece gerçekten hesabı tehlikeye atan bir sorun varsa veto et.\n\n"
    "Cevabını SADECE şu JSON nesnesi olarak ver:\n"
    '{"veto": true | false, "ciddiyet": 0-1 arası sayı, "gerekce": "en fazla 2 cümle Türkçe"}'
)

AVUKAT_SEMASI = {
    "type": "object",
    "properties": {
        "veto": {"type": "boolean"},
        "ciddiyet": {"type": "number"},
        "gerekce": {"type": "string"},
    },
    "required": ["veto", "ciddiyet", "gerekce"],
    "additionalProperties": False,
}


def _yuvarla(x, n=6):
    return None if x is None else round(x, n)


def veri_paketi(sembol, firsat, mum_h1, mum_m15, fark, basliklar, takvim_olaylari, golge, an):
    """Uc modele AYNEN giden metin. Gercek hesap bilgisi icermez (golge hesap kullanilir)."""
    h1, m15 = firsat["h1"], firsat["m15"]
    fiyat = m15["kapanis"]
    paket = {
        "zaman_utc": an.strftime("%Y-%m-%d %H:%M"),
        "sembol": sembol,
        "kodun_buldugu_firsat": {"tur": firsat["tur"], "onerilen_yon": firsat["yon"],
                                 "aciklama": firsat["aciklama"]},
        "zaman_dilimleri": {
            "1_saat": {"trend": firsat["trend"], "kapanis": _yuvarla(h1["kapanis"]),
                       "ema50": _yuvarla(h1["ema50"]), "ema200": _yuvarla(h1["ema200"]),
                       "rsi14": _yuvarla(h1["rsi"], 1), "atr14": _yuvarla(h1["atr"]),
                       "son_tepe_20": _yuvarla(h1["son_tepe"]), "son_dip_20": _yuvarla(h1["son_dip"])},
            "15_dakika": {"kapanis": _yuvarla(fiyat), "ema50": _yuvarla(m15["ema50"]),
                          "ema200": _yuvarla(m15["ema200"]), "rsi14": _yuvarla(m15["rsi"], 1),
                          "atr14": _yuvarla(m15["atr"]), "son_tepe_20": _yuvarla(m15["son_tepe"]),
                          "son_dip_20": _yuvarla(m15["son_dip"])},
        },
        "son_kapanislar": {
            "1_saat_son12": [_yuvarla(m["c"]) for m in mum_h1[-12:]],
            "15_dakika_son16": [_yuvarla(m["c"]) for m in mum_m15[-16:]],
        },
        "alis_satis_farki": {"fiyat_birimi": fark, "yuzde": round(fark / fiyat * 100, 4),
                             "atr15_orani": round(fark / m15["atr"], 3) if m15["atr"] else None},
        "haber_basliklari": basliklar,
        "ekonomik_takvim_24s": [
            {"zaman_utc": o["zaman"].strftime("%a %H:%M"), "ulke": o["ulke"], "etki": o["etki"],
             "olay": o["baslik"], "tahmin": o.get("tahmin", ""), "onceki": o.get("onceki", "")}
            for o in takvim_olaylari],
        "hesap_durumu": {
            "baslangic": golge["baslangic"], "bakiye": round(golge["bakiye"], 2),
            "olum_cizgisi": round(golge["baslangic"] * 0.70, 2),
            "art_arda_zarar": golge.get("ardisik_zarar", 0),
        },
        "son_islemler": [
            {"sembol": i["sembol"], "yon": i["yon"], "sonuc": i["sonuc"], "R": i["sonuc_r"],
             "kapanis_utc": i["kapanis"][:16]}
            for i in golge.get("gecmis", [])[-5:]],
    }
    return "Toplantı veri paketi:\n" + json.dumps(paket, ensure_ascii=False, indent=1)


def _oy_temizle(oy):
    yon = str(oy.get("yon", "")).lower().strip()
    if yon not in ("long", "short", "wait"):
        raise modeller.ModelHatasi(f"gecersiz yon: {yon}")
    return {
        "yon": yon,
        "guven": max(0.0, min(1.0, float(oy.get("guven", 0)))),
        "stop_yuzde": abs(float(oy.get("stop_yuzde", 0) or 0)),
        "hedef_yuzde": abs(float(oy.get("hedef_yuzde", 0) or 0)),
        "gecerlilik_dk": int(max(5, min(60, float(oy.get("gecerlilik_dk", 15) or 15)))),
        "gerekce": str(oy.get("gerekce", ""))[:400],
        "hizmet_eden_model": oy.get("_hizmet_eden_model"),
    }


def oylama(model_ayarlari, paket, zaman_asimi, sor=modeller.sor):
    """Uc modeli PARALEL ve birbirinden habersiz cagir. {ad: oy | {'hata': ...}}"""
    sistem = ANA_TALIMAT + OY_FORMATI
    sonuc = {}
    with cf.ThreadPoolExecutor(max_workers=len(model_ayarlari)) as havuz:
        isler = {havuz.submit(sor, cfg, sistem, paket, OY_SEMASI, zaman_asimi): ad
                 for ad, cfg in model_ayarlari.items()}
        for is_ in cf.as_completed(isler):
            ad = isler[is_]
            try:
                sonuc[ad] = _oy_temizle(is_.result())
            except Exception as e:
                sonuc[ad] = {"hata": str(e)[:300]}
    return sonuc


def karar(oylar, en_dusuk_guven):
    """Oybirligi kontrolu. (oybirligi_var, yon, sebep)"""
    for ad, oy in oylar.items():
        if "hata" in oy:
            return False, None, f"{ad} cevap vermedi: {oy['hata'][:120]}"
    yonler = {oy["yon"] for oy in oylar.values()}
    if len(yonler) != 1:
        return False, None, "modeller ayni yonde degil: " + ", ".join(f"{a}={o['yon']}" for a, o in oylar.items())
    yon = yonler.pop()
    if yon == "wait":
        return False, None, "uc model de 'bekle' dedi"
    en_dusuk = min(oy["guven"] for oy in oylar.values())
    if en_dusuk < en_dusuk_guven:
        return False, yon, f"en dusuk guven {en_dusuk:.2f} < {en_dusuk_guven}"
    return True, yon, ""


def ortak_parametreler(oylar):
    """Uc oyun ortanca stop/hedef ve en kisa gecerlilik suresi."""
    return {
        "stop_yuzde": statistics.median(o["stop_yuzde"] for o in oylar.values()),
        "hedef_yuzde": statistics.median(o["hedef_yuzde"] for o in oylar.values()),
        "gecerlilik_dk": min(o["gecerlilik_dk"] for o in oylar.values()),
        "guven": min(o["guven"] for o in oylar.values()),
    }


def seytanin_avukati(avukat_cfg, paket, oylar, yon, parametreler, zaman_asimi, sor=modeller.sor):
    oneri = {"yon": yon, **parametreler,
             "uyelerin_gerekceleri": {a: o["gerekce"] for a, o in oylar.items()}}
    kullanici = paket + "\n\nÖnerilen işlem:\n" + json.dumps(oneri, ensure_ascii=False, indent=1)
    sistem = ANA_TALIMAT + "\n\n" + AVUKAT_TALIMATI
    try:
        c = sor(avukat_cfg, sistem, kullanici, AVUKAT_SEMASI, zaman_asimi)
        return {"veto": bool(c.get("veto")), "ciddiyet": max(0.0, min(1.0, float(c.get("ciddiyet", 0)))),
                "gerekce": str(c.get("gerekce", ""))[:400]}
    except Exception as e:
        return {"hata": str(e)[:300]}
