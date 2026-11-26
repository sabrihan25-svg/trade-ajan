"""BEYIN - tek gecis. GitHub Actions bunu ~3 dakikada bir calistirir.
1) Golge hesabi ve hayalet islemleri guncelle  2) Takvimi yaz  3) Hayatta kalma kurallari
4) Firsat tara  5) Gerekirse kurul topla  6) Sinyal dosyasini yaz
Calistirma: python -m beyin.ana"""
import datetime as dt
import json
import os
import sys

from . import firsat as firsat_mod
from . import golge, kurallar, kurul, modeller, veri

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def yol(*parca):
    # Testler kendi gecici klasorunu TRADE_AJAN_KOK ile verir
    return os.path.join(os.environ.get("TRADE_AJAN_KOK", KOK), *parca)


def json_oku(p, varsayilan):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return varsayilan


def json_yaz(p, veri_):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(veri_, f, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, p)


def satir_ekle(p, kayit):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False, default=str) + "\n")


def varsayilan_durum(ayar):
    b = ayar["golge_hesap"]["baslangic"]
    return {
        "golge": {"baslangic": b, "bakiye": b, "acik_islem": None, "gecmis": [], "ardisik_zarar": 0,
                  "mola_bitis": None, "olu": False},
        "kurul": {"tarih": None, "bugun": 0, "toplam": 0, "son_tetik": {}},
        "karne": {},
        "hayaletler": [],
    }


class Veri:
    """Gercek veri kaynagi (testte sahtesiyle degistirilir)."""

    def __init__(self, ayar):
        self.ayar = ayar
        self._onbellek = {}

    def mumlar(self, sembol, aralik):
        anahtar = (sembol, aralik)
        if anahtar not in self._onbellek:
            kod = self.ayar["semboller"][sembol]["veri_kodu"]
            donem = "5d" if aralik == "15m" else "3mo"
            self._onbellek[anahtar] = veri.mumlar(kod, aralik, donem)
        return self._onbellek[anahtar]

    def haberler(self):
        return veri.haber_basliklari()

    def takvim(self):
        return veri.takvim()


def ozet_yaz(durum, rapor, an):
    """Telefondan bile okunabilen basit durum sayfasi: DURUM.md"""
    g, k = durum["golge"], durum["kurul"]
    tr = an + dt.timedelta(hours=3)
    s = [f"# Ajan durumu", "", f"Son kontrol: **{tr.strftime('%d.%m.%Y %H:%M')}** (Turkiye saati)", "",
         "## Son kontrolde ne oldu", ""]
    s += [f"- {r}" for r in rapor] or ["- (kayit yok)"]
    s += ["", "## Golge (kagit) hesap", "",
          f"- Bakiye: **{g['bakiye']:.2f} $** (baslangic {g['baslangic']:.0f} $, olum cizgisi {g['baslangic'] * 0.7:.0f} $)",
          f"- Durum: {'OLDU - ajan kalici durdu' if g.get('olu') else 'hayatta'}",
          f"- Art arda zarar: {g.get('ardisik_zarar', 0)}"]
    a = g.get("acik_islem")
    if a:
        s.append(f"- Acik islem: {a['sembol']} {a['yon']} giris {a['giris']:.5g}, stop {a['stop']:.5g}, hedef {a['hedef']:.5g}")
    else:
        s.append("- Acik islem: yok")
    s += ["", f"## Kurul", "", f"- Bugun toplanan: {k.get('bugun', 0)} / 6", f"- Toplam toplanti: {k.get('toplam', 0)}"]
    aktif = json_oku(yol("sinyaller", "sinyal.json"), {})
    if aktif:
        s.append(f"- Son sinyal: {aktif['sembol']} {aktif['yon']} ({aktif['olusturma'][:16]} UTC)")
    s += ["", "## Model karnesi", "", "| Model | Toplanti | Long | Short | Bekle | Cevapsiz | Kazanan | Kaybeden | Toplam R |",
          "|---|---|---|---|---|---|---|---|---|"]
    for ad, v in durum["karne"].items():
        s.append(f"| {ad} | {v['toplanti']} | {v['long']} | {v['short']} | {v['bekle']} | {v['cevapsiz']} | "
                 f"{v['kazanan']} | {v['kaybeden']} | {v['toplam_R']} |")
    s += ["", "## Son golge islemler", ""]
    for i in reversed(g.get("gecmis", [])[-10:]):
        s.append(f"- {i['kapanis'][:16]} {i['sembol']} {i['yon']}: {i['sonuc']} ({i['sonuc_r']}R, {i['tutar']:+.2f} $)")
    if not g.get("gecmis"):
        s.append("- henuz yok")
    s += ["", "Kurul kayitlari: [durum/kurullar](durum/kurullar)"]
    with open(yol("DURUM.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(s) + "\n")


def calistir(an=None, kaynak=None, sor=modeller.sor):
    ayar = json_oku(yol("config", "ayarlar.json"), None)
    durum = json_oku(yol("durum", "durum.json"), None) or varsayilan_durum(ayar)
    an = an or kurallar.utc_simdi()
    kaynak = kaynak or Veri(ayar)
    rapor = []

    def log(s):
        rapor.append(s)
        print(s)

    if not ayar.get("beyin_acik", False):
        log("Beyin kapali (config/ayarlar.json -> beyin_acik: false). Kurul testi gectikten sonra acilacak.")
        return rapor
    if durum["golge"].get("olu"):
        log("OLUM CIZGISI daha once asildi. Ajan kalici olarak durdu. Hicbir sey yapilmiyor.")
        return rapor

    def mum15(sembol):
        return kaynak.mumlar(sembol, "15m")[0]

    # 1) Golge hesap ve hayaletler
    try:
        kapanan = golge.golge_guncelle(durum, mum15, an)
        if kapanan:
            log(f"Golge islem kapandi: {kapanan['sembol']} {kapanan['yon']} -> {kapanan['sonuc']} "
                f"({kapanan['sonuc_r']}R), bakiye {durum['golge']['bakiye']:.2f} $")
        golge.hayaletleri_guncelle(durum, mum15, an)
    except Exception as e:
        log(f"Golge guncellenemedi: {e}")

    # 2) Takvim (kopru de bunu okur)
    try:
        olaylar = kaynak.takvim()
        takvim_ok = True
    except Exception as e:
        olaylar, takvim_ok = [], False
        log(f"Takvim alinamadi: {e}")
    yasaklar = [{"baslangic": (o["zaman"] - dt.timedelta(minutes=kurallar.HABER_PENCERE_DK)).isoformat(),
                 "bitis": (o["zaman"] + dt.timedelta(minutes=kurallar.HABER_PENCERE_DK)).isoformat(),
                 "olay": o["baslik"]}
                for o in olaylar if o["ulke"] == "USD" and o["etki"] == "High"]
    if takvim_ok:
        json_yaz(yol("sinyaller", "takvim.json"), {"guncelleme": an.isoformat(), "haber_yasaklari": yasaklar})

    def bitir():
        json_yaz(yol("durum", "durum.json"), durum)
        ozet_yaz(durum, rapor, an)
        return rapor

    # 3) Hayatta kalma kurallari
    izin, sebep = kurallar.hesap_kontrol(durum["golge"], an)
    if not izin:
        log(f"Islem yok: {sebep}")
        return bitir()
    izin, sebep = kurallar.yeni_islem_saati_uygun_mu(an)
    if not izin:
        log(f"Islem yok: {sebep}")
        return bitir()
    if not takvim_ok:
        log("Islem yok: takvim okunamadi (haber saatleri bilinmeden islem acilmaz)")
        return bitir()
    yasak, olay = kurallar.haber_yasagi(an, olaylar)
    if yasak:
        log(f"Islem yok: onemli ABD verisi yakin ({olay})")
        return bitir()
    aktif = json_oku(yol("sinyaller", "sinyal.json"), {})
    if aktif.get("gecerlilik_bitis") and dt.datetime.fromisoformat(aktif["gecerlilik_bitis"]) > an:
        log("Islem yok: hala gecerli bir sinyal var (ayni anda tek islem)")
        return bitir()

    k = durum["kurul"]
    bugun = an.strftime("%Y-%m-%d")
    if k.get("tarih") != bugun:
        k["tarih"], k["bugun"] = bugun, 0
    if k["bugun"] >= ayar["kurul"]["gunluk_en_fazla_toplanti"]:
        log("Islem yok: gunluk kurul toplanti siniri doldu (maliyet siniri)")
        return bitir()

    # 4) Firsat tara
    secilen = None
    for sembol, s_ayar in ayar["semboller"].items():
        try:
            m_h1, _ = kaynak.mumlar(sembol, "60m")
            m_15, anlik = kaynak.mumlar(sembol, "15m")
        except Exception as e:
            log(f"{sembol}: veri alinamadi ({e})")
            continue
        f = firsat_mod.tara(m_h1, m_15)
        if not f:
            continue
        anahtar = f"{sembol}:{f['yon']}"
        son = k["son_tetik"].get(anahtar)
        if son and an - dt.datetime.fromisoformat(son) < dt.timedelta(hours=ayar["kurul"]["ayni_firsat_bekleme_saat"]):
            log(f"{sembol}: {f['tur']} firsati var ama yakin zamanda kurul toplandi")
            continue
        fark = s_ayar["tipik_fark"]
        if f["h1"]["atr"] and fark > f["h1"]["atr"] * kurallar.EN_FAZLA_FARK_ATR_ORANI:
            log(f"{sembol}: alis-satis farki cok genis, atlandi")
            continue
        secilen = (sembol, f, m_h1, m_15, anlik or m_15[-1]["c"], fark)
        break
    if not secilen:
        log("Firsat yok, kurul toplanmadi.")
        return bitir()

    sembol, f, m_h1, m_15, fiyat, fark = secilen
    log(f"FIRSAT: {sembol} {f['yon']} - {f['aciklama']}. Kurul toplaniyor.")
    k["bugun"] += 1
    k["toplam"] += 1
    k["son_tetik"][f"{sembol}:{f['yon']}"] = an.isoformat()

    # 5) Kurul
    try:
        basliklar = kaynak.haberler()
    except Exception:
        basliklar = []
    pb = set(ayar["semboller"][sembol]["para_birimleri"]) | {"USD"}
    yakin = [o for o in olaylar if o["ulke"] in pb and o["etki"] in ("High", "Medium")
             and an - dt.timedelta(hours=2) <= o["zaman"] <= an + dt.timedelta(hours=24)]
    paket = kurul.veri_paketi(sembol, f, m_h1, m_15, fark, basliklar, yakin, durum["golge"], an)
    modeller_ = ayar["modeller"]
    zaman_asimi = ayar["kurul"]["model_zaman_asimi_sn"]
    oylar = kurul.oylama(modeller_, paket, zaman_asimi, sor=sor)
    for ad, oy in oylar.items():
        golge.karne_oy_kaydet(durum, ad, oy)
        if "hata" in oy:
            log(f"  {ad}: CEVAP YOK ({oy['hata'][:100]})")
            continue
        log(f"  {ad}: {oy['yon']} guven={oy['guven']:.2f} stop=%{oy['stop_yuzde']} hedef=%{oy['hedef_yuzde']} - {oy['gerekce']}")
        if oy["yon"] in ("long", "short") and oy["stop_yuzde"] > 0 and oy["hedef_yuzde"] > 0:
            golge.hayalet_ekle(durum, ad, golge.islem_olustur(
                sembol, oy["yon"], fiyat, oy["stop_yuzde"], oy["hedef_yuzde"], fark, an, "hayalet"))

    kayit = {"zaman": an.isoformat(), "sembol": sembol, "firsat": f["tur"], "kod_yonu": f["yon"],
             "oylar": oylar, "sonuc": None}
    oybirligi, yon, sebep = kurul.karar(oylar, ayar["kurul"]["en_dusuk_guven"])
    sinyal = None
    if not oybirligi:
        kayit["sonuc"] = f"islem yok: {sebep}"
    else:
        par = kurul.ortak_parametreler(oylar)
        gecerli, sebep = kurallar.sinyal_dogrula(yon, par["stop_yuzde"], par["hedef_yuzde"], fiyat, fark,
                                                 f["m15"]["atr"], f["h1"]["atr"])
        if not gecerli:
            kayit["sonuc"] = f"islem yok (kural): {sebep}"
        else:
            sira = list(modeller_)
            avukat_ad = sira[(k["toplam"] - 1) % len(sira)]
            avukat = kurul.seytanin_avukati(modeller_[avukat_ad], paket, oylar, yon, par, zaman_asimi, sor=sor)
            kayit["seytanin_avukati"] = {"model": avukat_ad, **avukat}
            esik = ayar["kurul"]["veto_ciddiyet_esigi"]
            if "hata" in avukat:
                kayit["sonuc"] = f"islem yok: seytanin avukati ({avukat_ad}) cevap vermedi"
            elif avukat["veto"] and avukat["ciddiyet"] >= esik:
                kayit["sonuc"] = f"islem yok: {avukat_ad} ciddi veto ({avukat['gerekce']})"
            else:
                bitis = an + dt.timedelta(minutes=min(par["gecerlilik_dk"], ayar["kurul"]["en_uzun_gecerlilik_dk"]))
                sonraki = kurallar.sonraki_haber_yasagi_baslangici(an, olaylar)
                if sonraki and sonraki < bitis:
                    bitis = sonraki
                if an.weekday() == 4:
                    cuma = an.replace(hour=kurallar.CUMA_SON_SINYAL_UTC, minute=0, second=0, microsecond=0)
                    bitis = min(bitis, cuma)
                if bitis - an < dt.timedelta(minutes=5):
                    kayit["sonuc"] = "islem yok: gecerlilik suresi cok kisa (haber/hafta sonu)"
                else:
                    islem = golge.islem_olustur(sembol, yon, fiyat, par["stop_yuzde"], par["hedef_yuzde"],
                                                fark, an, "kurul")
                    golge.golge_ac(durum, islem, an)
                    sinyal = {
                        "id": f"{an.strftime('%Y%m%d%H%M')}-{sembol}-{yon}",
                        "sembol": sembol, "yon": yon,
                        "referans_fiyat": round(fiyat, 6),
                        "stop_yuzde": round(par["stop_yuzde"], 4),
                        "hedef_yuzde": round(par["hedef_yuzde"], 4),
                        "olusturma": an.isoformat(), "gecerlilik_bitis": bitis.isoformat(),
                        "en_dusuk_guven": round(par["guven"], 3),
                        "gerekceler": {a: o["gerekce"] for a, o in oylar.items()},
                        "seytanin_avukati": kayit["seytanin_avukati"],
                    }
                    json_yaz(yol("sinyaller", "sinyal.json"), sinyal)
                    satir_ekle(yol("durum", "sinyal_gecmisi.jsonl"), sinyal)
                    kayit["sonuc"] = f"SINYAL: {sinyal['id']}"
    log("KARAR: " + kayit["sonuc"])
    satir_ekle(yol("durum", "kurullar", an.strftime("%Y-%m") + ".jsonl"), kayit)
    return bitir()


if __name__ == "__main__":
    calistir()
    sys.exit(0)
