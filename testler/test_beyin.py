"""Sahte verilerle testler. Internet ve API anahtari gerekmez.
Calistirma: python -m unittest discover -s testler -v"""
import datetime as dt
import json
import math
import os
import shutil
import tempfile
import unittest

from beyin import ana, firsat, golge, gostergeler, kurallar, kurul

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERS = dt.datetime(2026, 11, 26, 14, 0, tzinfo=dt.timezone.utc)  # Persembe


def sahte_mumlar(an, adim_dk, adet, egim, dalga=0.0, son_ozel=None, baz=1.10):
    """Duzenli trend + dalga. son_ozel(listedeki son mumlari degistiren fonksiyon)."""
    mumlar = []
    bas = int(an.timestamp()) - adet * adim_dk * 60
    fiyat = baz
    for i in range(adet):
        o = fiyat
        c = o + egim + dalga * math.sin(i / 3)
        h, l = max(o, c) + abs(egim) * 0.5 + 0.0001, min(o, c) - abs(egim) * 0.5 - 0.0001
        mumlar.append({"t": bas + i * adim_dk * 60, "o": o, "h": h, "l": l, "c": c})
        fiyat = c
    if son_ozel:
        son_ozel(mumlar)
    return mumlar


def geri_cekilme_sonrasi_donus(m):
    """Son 8 mumda asagi cekilme, son mumda guclu yukari donus."""
    for i in range(-8, -1):
        o = m[i - 1]["c"]
        c = o - 0.00025
        m[i].update({"o": o, "c": c, "h": o + 0.00005, "l": c - 0.00005})
    o = m[-2]["c"]
    c = o + 0.0009
    m[-1].update({"o": o, "c": c, "h": c + 0.00005, "l": o - 0.00005})


class SahteKaynak:
    def __init__(self, an, firsatli=True):
        self.an = an
        self.h1 = sahte_mumlar(an, 60, 300, 0.0003)
        self.m15 = sahte_mumlar(an, 15, 200, 0.0001,
                                son_ozel=geri_cekilme_sonrasi_donus if firsatli else None,
                                baz=self.h1[-1]["c"] - 0.02)
        self.olaylar = []

    def mumlar(self, sembol, aralik):
        if sembol != "EURUSD":
            # Diger semboller: yatay piyasa, firsat yok
            return sahte_mumlar(self.an, 15 if aralik == "15m" else 60, 300, 0.0, dalga=0.0002), 1.1
        if aralik == "60m":
            return self.h1, self.h1[-1]["c"]
        return self.m15, self.m15[-1]["c"]

    def haberler(self):
        return ["test basligi"]

    def takvim(self):
        return self.olaylar


def sahte_sor(yonler, guven=0.75, veto=False):
    """Model cagrisinin sahtesi. yonler: {model_adi: yon}"""
    def sor(cfg, sistem, kullanici, sema, zaman_asimi):
        if "veto" in sema["properties"]:
            return {"veto": veto, "ciddiyet": 0.8 if veto else 0.2, "gerekce": "test avukat"}
        ad = {"anthropic": "claude", "openai": "gpt", "deepseek": "deepseek"}[cfg["saglayici"]]
        y = yonler.get(ad, "wait")
        if y == "hata":
            raise RuntimeError("zaman asimi")
        return {"yon": y, "guven": guven, "stop_yuzde": 0.2, "hedef_yuzde": 0.4,
                "gecerlilik_dk": 30, "gerekce": "test"}
    return sor


class GostergeTest(unittest.TestCase):
    def test_ema_sabit(self):
        self.assertAlmostEqual(gostergeler.ema([2.0] * 60, 50)[-1], 2.0)

    def test_rsi_yukselen(self):
        self.assertEqual(gostergeler.rsi([float(i) for i in range(30)], 14)[-1], 100.0)

    def test_atr(self):
        m = [{"o": 1, "h": 1.5, "l": 0.5, "c": 1} for _ in range(30)]
        self.assertAlmostEqual(gostergeler.atr(m, 14)[-1], 1.0)


class KuralTest(unittest.TestCase):
    def golge(self, bakiye=100.0):
        return {"baslangic": 100.0, "bakiye": bakiye, "acik_islem": None, "ardisik_zarar": 0}

    def test_rr_yetersiz(self):
        ok, s = kurallar.sinyal_dogrula("long", 0.2, 0.25, 1.1, 0.00008, 0.0004, 0.0009)
        self.assertFalse(ok)
        self.assertIn("1.5", s)

    def test_dar_stop(self):
        ok, _ = kurallar.sinyal_dogrula("long", 0.01, 0.05, 1.1, 0.00001, 0.0004, 0.0009)
        self.assertFalse(ok)

    def test_genis_fark(self):
        ok, s = kurallar.sinyal_dogrula("long", 0.1, 0.3, 1.1, 0.0003, 0.0004, 0.0009)
        self.assertFalse(ok)

    def test_gecerli(self):
        ok, s = kurallar.sinyal_dogrula("long", 0.1, 0.2, 1.1, 0.00008, 0.0004, 0.0009)
        self.assertTrue(ok, s)

    def test_olum_cizgisi(self):
        g = self.golge(69.9)
        ok, s = kurallar.hesap_kontrol(g, PERS)
        self.assertFalse(ok)
        self.assertTrue(g["olu"])

    def test_gunluk_sinir(self):
        g = self.golge(100.0)
        kurallar.hesap_kontrol(g, PERS)
        g["bakiye"] = 96.9
        ok, s = kurallar.hesap_kontrol(g, PERS)
        self.assertFalse(ok)
        self.assertIn("gunluk", s)

    def test_haftalik_sinir(self):
        g = self.golge(100.0)
        kurallar.hesap_kontrol(g, PERS - dt.timedelta(days=3))  # Pazartesi
        g["bakiye"] = 97.5
        kurallar.hesap_kontrol(g, PERS - dt.timedelta(days=1))
        g["bakiye"] = 93.9
        g["gun"] = {"tarih": PERS.strftime("%Y-%m-%d"), "bakiye": 95.0}
        ok, s = kurallar.hesap_kontrol(g, PERS)
        self.assertFalse(ok)
        self.assertIn("haftalik", s)

    def test_uc_zarar_mola(self):
        g = self.golge()
        for _ in range(3):
            kurallar.zarar_sonrasi_guncelle(g, -1, PERS)
        ok, s = kurallar.hesap_kontrol(g, PERS + dt.timedelta(hours=1))
        self.assertFalse(ok)
        self.assertIn("mola", s)
        ok, _ = kurallar.hesap_kontrol(g, PERS + dt.timedelta(hours=25))
        self.assertTrue(ok)

    def test_hafta_sonu(self):
        cmt = dt.datetime(2026, 11, 28, 12, tzinfo=dt.timezone.utc)
        self.assertFalse(kurallar.yeni_islem_saati_uygun_mu(cmt)[0])
        cuma_aksam = dt.datetime(2026, 11, 27, 19, 30, tzinfo=dt.timezone.utc)
        self.assertFalse(kurallar.yeni_islem_saati_uygun_mu(cuma_aksam)[0])
        self.assertTrue(kurallar.yeni_islem_saati_uygun_mu(PERS)[0])

    def test_haber(self):
        olay = [{"zaman": PERS + dt.timedelta(minutes=20), "ulke": "USD", "etki": "High", "baslik": "NFP"}]
        self.assertTrue(kurallar.haber_yasagi(PERS, olay)[0])
        self.assertFalse(kurallar.haber_yasagi(PERS - dt.timedelta(hours=1), olay)[0])


class KurulTest(unittest.TestCase):
    def oy(self, yon, guven=0.7):
        return {"yon": yon, "guven": guven, "stop_yuzde": 0.2, "hedef_yuzde": 0.4, "gecerlilik_dk": 30, "gerekce": ""}

    def test_oybirligi(self):
        ok, yon, _ = kurul.karar({"a": self.oy("long"), "b": self.oy("long"), "c": self.oy("long")}, 0.6)
        self.assertTrue(ok)
        self.assertEqual(yon, "long")

    def test_biri_farkli(self):
        ok, _, _ = kurul.karar({"a": self.oy("long"), "b": self.oy("short"), "c": self.oy("long")}, 0.6)
        self.assertFalse(ok)

    def test_cevapsiz(self):
        ok, _, s = kurul.karar({"a": self.oy("long"), "b": {"hata": "x"}, "c": self.oy("long")}, 0.6)
        self.assertFalse(ok)

    def test_dusuk_guven(self):
        ok, _, _ = kurul.karar({"a": self.oy("long"), "b": self.oy("long", 0.55), "c": self.oy("long")}, 0.6)
        self.assertFalse(ok)

    def test_hepsi_bekle(self):
        ok, _, _ = kurul.karar({"a": self.oy("wait"), "b": self.oy("wait"), "c": self.oy("wait")}, 0.6)
        self.assertFalse(ok)


class FirsatTest(unittest.TestCase):
    def test_geri_cekilme_bulunur(self):
        k = SahteKaynak(PERS)
        f = firsat.tara(k.h1, k.m15)
        self.assertIsNotNone(f)
        self.assertEqual(f["yon"], "long")

    def test_firsatsiz(self):
        k = SahteKaynak(PERS, firsatli=False)
        self.assertIsNone(firsat.tara(k.h1, k.m15))


class TamGecisTest(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        shutil.copytree(os.path.join(KOK, "config"), os.path.join(self.dizin, "config"))
        yol_ = os.path.join(self.dizin, "config", "ayarlar.json")
        with open(yol_, encoding="utf-8") as f:
            ayar = json.load(f)
        ayar["beyin_acik"] = True
        with open(yol_, "w", encoding="utf-8") as f:
            json.dump(ayar, f)
        os.environ["TRADE_AJAN_KOK"] = self.dizin

    def tearDown(self):
        os.environ.pop("TRADE_AJAN_KOK", None)
        shutil.rmtree(self.dizin)

    def oku(self, *p):
        with open(os.path.join(self.dizin, *p), encoding="utf-8") as f:
            return json.load(f)

    def var_mi(self, *p):
        return os.path.exists(os.path.join(self.dizin, *p))

    def test_oybirligi_sinyal_ve_golge(self):
        k = SahteKaynak(PERS)
        ana.calistir(an=PERS, kaynak=k, sor=sahte_sor({"claude": "long", "gpt": "long", "deepseek": "long"}))
        s = self.oku("sinyaller", "sinyal.json")
        self.assertEqual(s["yon"], "long")
        self.assertEqual(s["sembol"], "EURUSD")
        self.assertGreaterEqual(s["hedef_yuzde"], s["stop_yuzde"] * 1.5)
        d = self.oku("durum", "durum.json")
        self.assertIsNotNone(d["golge"]["acik_islem"])
        self.assertEqual(len(d["hayaletler"]), 3)
        self.assertEqual(d["kurul"]["bugun"], 1)
        # Fiyat hedefe gidiyor -> golge kar
        islem = d["golge"]["acik_islem"]
        sonra = PERS + dt.timedelta(minutes=30)
        k2 = SahteKaynak(sonra)
        # Girişten sonraki mumlar: once yatay, sonra hedefe ulasan mum
        k2.m15 = [m for m in k2.m15 if m["t"] < int(PERS.timestamp())]
        k2.m15.append({"t": int(PERS.timestamp()), "o": islem["giris"], "h": islem["giris"] + 0.0001,
                       "l": islem["giris"] - 0.0001, "c": islem["giris"]})
        k2.m15.append({"t": int(PERS.timestamp()) + 900, "o": islem["giris"], "h": islem["hedef"] + 0.001,
                       "l": islem["giris"] - 0.00001, "c": islem["hedef"]})
        ana.calistir(an=sonra, kaynak=k2, sor=sahte_sor({}))
        d = self.oku("durum", "durum.json")
        self.assertIsNone(d["golge"]["acik_islem"])
        self.assertGreater(d["golge"]["bakiye"], 100.0)
        self.assertEqual(d["karne"]["claude"]["kazanan"], 1)

    def test_ayrisma_islem_yok(self):
        ana.calistir(an=PERS, kaynak=SahteKaynak(PERS),
                     sor=sahte_sor({"claude": "long", "gpt": "short", "deepseek": "long"}))
        self.assertFalse(self.var_mi("sinyaller", "sinyal.json"))

    def test_model_cevapsiz_islem_yok(self):
        ana.calistir(an=PERS, kaynak=SahteKaynak(PERS),
                     sor=sahte_sor({"claude": "long", "gpt": "hata", "deepseek": "long"}))
        self.assertFalse(self.var_mi("sinyaller", "sinyal.json"))
        self.assertEqual(self.oku("durum", "durum.json")["karne"]["gpt"]["cevapsiz"], 1)

    def test_veto_islem_yok(self):
        ana.calistir(an=PERS, kaynak=SahteKaynak(PERS),
                     sor=sahte_sor({"claude": "long", "gpt": "long", "deepseek": "long"}, veto=True))
        self.assertFalse(self.var_mi("sinyaller", "sinyal.json"))

    def test_haber_saatinde_kurul_yok(self):
        k = SahteKaynak(PERS)
        k.olaylar = [{"zaman": PERS + dt.timedelta(minutes=10), "ulke": "USD", "etki": "High", "baslik": "CPI"}]
        cagri = []
        ana.calistir(an=PERS, kaynak=k, sor=lambda *a: cagri.append(1))
        self.assertEqual(cagri, [])
        self.assertEqual(len(self.oku("sinyaller", "takvim.json")["haber_yasaklari"]), 1)

    def test_gunluk_toplanti_siniri(self):
        sor = sahte_sor({"claude": "long", "gpt": "short", "deepseek": "long"})
        an = PERS
        for i in range(8):
            # her seferinde bekleme suresini sifirla ki yeniden tetiklensin
            if self.var_mi("durum", "durum.json"):
                d = self.oku("durum", "durum.json")
                d["kurul"]["son_tetik"] = {}
                with open(os.path.join(self.dizin, "durum", "durum.json"), "w") as f:
                    json.dump(d, f)
            ana.calistir(an=an, kaynak=SahteKaynak(an), sor=sor)
        self.assertEqual(self.oku("durum", "durum.json")["kurul"]["bugun"], 6)

    def test_olum_cizgisi_kalici(self):
        os.makedirs(os.path.join(self.dizin, "durum"))
        d = ana.varsayilan_durum(self.oku("config", "ayarlar.json"))
        d["golge"]["bakiye"] = 69.0
        with open(os.path.join(self.dizin, "durum", "durum.json"), "w") as f:
            json.dump(d, f)
        cagri = []
        ana.calistir(an=PERS, kaynak=SahteKaynak(PERS), sor=lambda *a: cagri.append(1))
        ana.calistir(an=PERS, kaynak=SahteKaynak(PERS), sor=lambda *a: cagri.append(1))
        self.assertEqual(cagri, [])
        self.assertTrue(self.oku("durum", "durum.json")["golge"]["olu"])


if __name__ == "__main__":
    unittest.main()
