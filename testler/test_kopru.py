"""Kopru testleri: sahte MT5 ve sahte GitHub ile. Hicbir yere baglanmaz."""
import datetime as dt
import os
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace as N

from testler import sahte_mt5

sys.modules["MetaTrader5"] = sahte_mt5
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kopru"))
import kopru  # noqa: E402


def sinyal(an, **kw):
    s = {"id": "T1", "sembol": "EURUSD", "yon": "long", "referans_fiyat": 1.1, "stop_yuzde": 0.2,
         "hedef_yuzde": 0.4, "olusturma": (an - dt.timedelta(minutes=2)).isoformat(),
         "gecerlilik_bitis": (an + dt.timedelta(minutes=20)).isoformat()}
    s.update(kw)
    return s


class KopruTest(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        kopru.DURUM_DOSYASI = os.path.join(self.dizin, "d.json")
        kopru.LOG_DOSYASI = os.path.join(self.dizin, "log.txt")
        sahte_mt5.sifirla()
        kopru.DENEME_BAKIYESI = None
        self.an = dt.datetime(2026, 11, 26, 14, 0, tzinfo=dt.timezone.utc)  # Persembe
        kopru.utc = lambda: self.an
        self.dosyalar = {"sinyaller/takvim.json": {"guncelleme": self.an.isoformat(), "haber_yasaklari": []}}
        kopru.github_oku = lambda d: self.dosyalar.get(d)

    def calistir(self, canli, s=None):
        if s is not None:
            self.dosyalar["sinyaller/sinyal.json"] = s
        kopru.dongu(canli)

    def test_test_modu_emir_gondermez(self):
        self.calistir(False, sinyal(self.an))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])
        self.assertEqual(len(sahte_mt5.DURUM["kontrol_edilen"]), 1)

    def test_canli_emir_sl_tp_ve_risk(self):
        self.calistir(True, sinyal(self.an))
        g = sahte_mt5.DURUM["gonderilen"]
        self.assertEqual(len(g), 1)
        e = g[0]
        self.assertLess(e["sl"], e["price"])
        self.assertGreater(e["tp"], e["price"])
        risk = abs(e["price"] - e["sl"]) * e["volume"] * 100000
        self.assertLessEqual(risk, 1000 * 0.015 + 0.01)
        self.assertGreaterEqual(risk, 1000 * 0.005)
        # Ayni sinyal ikinci kez islenmez
        self.calistir(True)
        self.assertEqual(len(sahte_mt5.DURUM["gonderilen"]), 1)

    def test_kucuk_bakiye_islem_yok(self):
        sahte_mt5.sifirla(bakiye=100.0, vmin=0.05)
        self.calistir(True, sinyal(self.an))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_eski_sinyal(self):
        s = sinyal(self.an, olusturma=(self.an - dt.timedelta(minutes=40)).isoformat())
        self.calistir(True, s)
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_kacmis_fiyat(self):
        sahte_mt5.DURUM["fiyat"] = 1.1012  # stop 0.0022, lehte %30 = 0.00066 asildi
        self.calistir(True, sinyal(self.an))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_rr_yetersiz(self):
        self.calistir(True, sinyal(self.an, hedef_yuzde=0.25))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_genis_fark(self):
        sahte_mt5.DURUM["fark"] = 0.0005
        self.calistir(True, sinyal(self.an))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_haber_saati(self):
        self.dosyalar["sinyaller/takvim.json"]["haber_yasaklari"] = [
            {"baslangic": (self.an - dt.timedelta(minutes=10)).isoformat(),
             "bitis": (self.an + dt.timedelta(minutes=50)).isoformat(), "olay": "CPI"}]
        self.calistir(True, sinyal(self.an))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_takvim_yoksa_islem_yok(self):
        del self.dosyalar["sinyaller/takvim.json"]
        self.calistir(True, sinyal(self.an))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_acik_pozisyon_varken_yok(self):
        sahte_mt5.DURUM["pozisyonlar"] = [N(magic=1, ticket=1, symbol="GBPUSD", volume=0.01, type=0)]
        self.calistir(True, sinyal(self.an))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_olum_cizgisi(self):
        self.calistir(False, sinyal(self.an, id="ilk"))  # baslangic 1000 kaydedilir
        sahte_mt5.DURUM["varlik"] = 690.0
        self.calistir(True, sinyal(self.an, id="T2"))
        sahte_mt5.DURUM["varlik"] = 1000.0
        self.calistir(True, sinyal(self.an, id="T3"))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_gunluk_zarar(self):
        self.calistir(False, sinyal(self.an, id="ilk"))
        sahte_mt5.DURUM["varlik"] = 969.0
        self.calistir(True, sinyal(self.an, id="T2"))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_uc_zarar_mola(self):
        t = int(time.time()) - 3600
        sahte_mt5.DURUM["islemler"] = [N(magic=kopru.SIHIRLI_NO, entry=1, time=t + i, profit=-10, commission=0, swap=0)
                                       for i in range(3)]
        self.calistir(True, sinyal(self.an))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_cuma_aksami(self):
        self.an = dt.datetime(2026, 11, 27, 19, 30, tzinfo=dt.timezone.utc)
        self.dosyalar["sinyaller/takvim.json"]["guncelleme"] = self.an.isoformat()
        self.calistir(True, sinyal(self.an))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_cuma_kapanisi_pozisyon_kapatir(self):
        self.an = dt.datetime(2026, 11, 27, 20, 50, tzinfo=dt.timezone.utc)
        sahte_mt5.DURUM["pozisyonlar"] = [N(magic=kopru.SIHIRLI_NO, ticket=7, symbol="EURUSD", volume=0.05, type=0)]
        self.calistir(True)
        self.assertEqual(sahte_mt5.DURUM["gonderilen"][0]["position"], 7)

    def test_algo_kapaliysa_gondermez(self):
        sahte_mt5.DURUM["algo"] = False
        self.calistir(True, sinyal(self.an))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_deneme_bakiyesi_risk(self):
        kopru.DENEME_BAKIYESI = 1000.0
        sahte_mt5.sifirla(bakiye=100000.0)
        self.calistir(True, sinyal(self.an))
        e = sahte_mt5.DURUM["gonderilen"][0]
        risk = abs(e["price"] - e["sl"]) * e["volume"] * 100000
        self.assertLessEqual(risk, 15.01)  # 1000 $'in %1,5'i, 100.000'in degil

    def test_deneme_bakiyesi_olum_cizgisi(self):
        kopru.DENEME_BAKIYESI = 1000.0
        sahte_mt5.sifirla(bakiye=100000.0)
        self.calistir(False, sinyal(self.an, id="ilk"))
        sahte_mt5.DURUM["varlik"] = 100000.0 - 301  # sanal varlik 699 < 700
        self.calistir(True, sinyal(self.an, id="T2"))
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])

    def test_kablo_testi(self):
        self.assertTrue(kopru.kablo_testi())
        self.assertEqual(sahte_mt5.DURUM["gonderilen"], [])


if __name__ == "__main__":
    unittest.main()
