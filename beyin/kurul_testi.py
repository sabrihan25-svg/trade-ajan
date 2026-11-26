"""KURUL TESTI (elle calistirilir): uc modelin adlari saglayicida var mi ve uc model de
ornek bir veri paketine JSON oy veriyor mu? Sinyal yazmaz, durum degistirmez.
Calistirma: python -m beyin.kurul_testi"""
import json
import os
import sys

from . import kurul, modeller

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANAHTAR_ADI = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}
IPUCU = {"anthropic": ["fable"], "openai": ["gpt-6", "astra"], "deepseek": ["v4", "pro", "reasoner", "chat"]}

ORNEK_PAKET = (
    "BU BIR TESTTIR, gercek islem yapilmayacak. Toplantı veri paketi:\n" + json.dumps({
        "zaman_utc": "test", "sembol": "EURUSD",
        "kodun_buldugu_firsat": {"tur": "geri_cekilme_bitti", "onerilen_yon": "long",
                                 "aciklama": "1s trend yukari; 15dk'da EMA50'ye geri cekilme sonrasi yukari donus"},
        "zaman_dilimleri": {"1_saat": {"trend": "yukari", "kapanis": 1.0976, "ema50": 1.0950, "ema200": 1.0900,
                                       "rsi14": 58, "atr14": 0.0009},
                            "15_dakika": {"kapanis": 1.0976, "ema50": 1.0970, "rsi14": 55, "atr14": 0.0004}},
        "alis_satis_farki": {"fiyat_birimi": 0.00008},
        "haber_basliklari": [], "ekonomik_takvim_24s": [],
        "hesap_durumu": {"baslangic": 100, "bakiye": 100, "olum_cizgisi": 70}, "son_islemler": [],
    }, ensure_ascii=False, indent=1))


def main():
    with open(os.path.join(KOK, "config", "ayarlar.json"), encoding="utf-8") as f:
        ayar = json.load(f)
    hata = False
    print("=== 0) Veri kaynaklari ===")
    from . import veri
    for sembol, s_ayar in ayar["semboller"].items():
        try:
            h1, _ = veri.mumlar(s_ayar["veri_kodu"], "60m", "3mo")
            m15, anlik = veri.mumlar(s_ayar["veri_kodu"], "15m", "5d")
            print(f"[{sembol}] TAMAM: 1s mum {len(h1)}, 15dk mum {len(m15)}, anlik fiyat {anlik}")
        except Exception as e:
            print(f"[{sembol}] HATA: mum verisi alinamadi: {str(e)[:200]}")
            hata = True
    try:
        olaylar = veri.takvim()
        print(f"[takvim] TAMAM: bu hafta {len(olaylar)} olay")
    except Exception as e:
        print(f"[takvim] HATA: {str(e)[:200]}")
        hata = True
    print(f"[haberler] {len(veri.haber_basliklari())} baslik alindi")

    print("\n=== 1) Model adlari kontrolu ===")
    for ad, cfg in ayar["modeller"].items():
        s = cfg["saglayici"]
        if not os.environ.get(ANAHTAR_ADI[s]):
            print(f"[{ad}] HATA: {ANAHTAR_ADI[s]} anahtari bulunamadi (GitHub Secrets'a eklenmeli)")
            hata = True
            continue
        try:
            liste = modeller.model_listesi(s)
        except Exception as e:
            print(f"[{ad}] HATA: model listesi alinamadi: {type(e).__name__}: {str(e)[:200]}")
            hata = True
            continue
        if cfg["model"] in liste:
            print(f"[{ad}] TAMAM: '{cfg['model']}' saglayicida mevcut")
        else:
            adaylar = [m for m in liste if any(i in m.lower() for i in IPUCU[s])]
            print(f"[{ad}] DIKKAT: '{cfg['model']}' bulunamadi. Benzer adlar: {adaylar[:15] or liste[:15]}")
            hata = True

    print("\n=== 2) Deneme oylamasi (paralel, birbirini gormeden) ===")
    oylar = kurul.oylama(ayar["modeller"], ORNEK_PAKET, ayar["kurul"]["model_zaman_asimi_sn"])
    for ad, oy in oylar.items():
        if "hata" in oy:
            print(f"[{ad}] CEVAP YOK: {oy['hata']}")
            hata = True
        else:
            print(f"[{ad}] {oy['yon']} guven={oy['guven']:.2f} stop=%{oy['stop_yuzde']} "
                  f"hedef=%{oy['hedef_yuzde']} sure={oy['gecerlilik_dk']}dk (model: {oy['hizmet_eden_model']})")
            print(f"        gerekce: {oy['gerekce']}")
    print("\nSONUC:", "SORUN VAR (yukariya bakin)" if hata else "UC MODEL DE CALISIYOR")
    sys.exit(1 if hata else 0)


if __name__ == "__main__":
    main()
