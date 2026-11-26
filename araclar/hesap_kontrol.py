# -*- coding: utf-8 -*-
"""
MT5 HESAP KONTROLU - SADECE OKUR.
Bu dosya hicbir emir gondermez, hicbir ayari degistirmez.
Sadece acik olan MetaTrader 5'ten bilgi okur ve rapor yazar.
Rapor hesap numarasini, sifreyi veya kurum sunucu adini ICERMEZ.
"""
import sys
import os
import datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    print("HATA: MetaTrader5 paketi yuklu degil. Lutfen .bat dosyasini kullanin.")
    sys.exit(1)

# Taranacak semboller (kurumdaki adi farkli olabilir: EURUSD.m, XAUUSDm, GOLD vb.)
ADAYLAR = {
    "EURUSD": ["EURUSD"],
    "GBPUSD": ["GBPUSD"],
    "USDJPY": ["USDJPY"],
    "AUDUSD": ["AUDUSD"],
    "USDCAD": ["USDCAD"],
    "USDCHF": ["USDCHF"],
    "EURJPY": ["EURJPY"],
    "XAUUSD (Altin)": ["XAUUSD", "GOLD"],
    "XAGUSD (Gumus)": ["XAGUSD", "SILVER"],
    "US30 (Dow)": ["US30", "DJ30", "DOW30", "USA30", "WS30", "DJI"],
    "US500 (S&P)": ["US500", "SPX500", "SP500", "USA500", "SPX"],
    "NAS100 (Nasdaq)": ["NAS100", "USTEC", "NDX100", "US100", "USTECH", "NQ100"],
    "GER40 (DAX)": ["GER40", "DE40", "DAX40", "GER30", "DE30"],
    "USOIL (Petrol)": ["USOIL", "WTI", "XTIUSD", "CRUDE", "OIL"],
    "BTCUSD": ["BTCUSD", "BITCOIN"],
    "ETHUSD": ["ETHUSD", "ETHEREUM"],
}

RISK_HEDEF = 0.01   # %1
RISK_TAVAN = 0.015  # %1,5
ATR_STOP_KAT = 1.5  # varsayilan stop mesafesi = 1,5 x ATR14 (1 saatlik)

satirlar = []


def yaz(s=""):
    print(s)
    satirlar.append(s)


def temiz(ad):
    return "".join(ch for ch in ad.upper() if ch.isalnum())


def sembol_bul(tum_semboller, anahtarlar):
    """Kurumdaki gercek sembol adini bul (son ek/on ek olabilir)."""
    bulunan = []
    for s in tum_semboller:
        t = temiz(s.name)
        for a in anahtarlar:
            if t == a or t.startswith(a) or (t.endswith(a) and len(t) - len(a) <= 2):
                # Asiri uzun adlari (ornegin EURUSDJPY sepetleri) ele
                if len(t) - len(a) <= 4:
                    bulunan.append(s)
                break
    if not bulunan:
        return None
    # Tam eslesme > islem acik olan > gorunur olan > kisa ad
    def puan(s):
        t = temiz(s.name)
        tam = any(t == a for a in anahtarlar)
        acik = s.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL
        return (not acik, not tam, not s.visible, len(s.name))
    bulunan.sort(key=puan)
    return bulunan[0]


def atr14_h1(ad):
    rates = mt5.copy_rates_from_pos(ad, mt5.TIMEFRAME_H1, 0, 60)
    if rates is None or len(rates) < 20:
        return None
    trs = []
    for i in range(1, len(rates)):
        h, l, pc = rates[i]["high"], rates[i]["low"], rates[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    son = trs[-14:]
    return sum(son) / len(son)


def para(x, cur):
    if x is None:
        return "-"
    return f"{x:,.2f} {cur}"


def main():
    yaz("=" * 70)
    yaz("  MT5 HESAP KONTROL RAPORU (sadece okuma - hicbir emir gonderilmedi)")
    yaz("  Tarih: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    yaz("=" * 70)

    if not mt5.initialize():
        yaz("HATA: MetaTrader 5'e baglanilamadi. Hata kodu: " + str(mt5.last_error()))
        yaz("Cozum: MT5'i acin, hesabiniza giris yapin, sonra bu dosyayi tekrar calistirin.")
        return

    try:
        ti = mt5.terminal_info()
        ai = mt5.account_info()
        if ai is None:
            yaz("HATA: Hesap bilgisi okunamadi. MT5'te hesaba giris yapili mi?")
            return

        tur = {
            mt5.ACCOUNT_TRADE_MODE_DEMO: "DEMO",
            mt5.ACCOUNT_TRADE_MODE_CONTEST: "YARISMA",
            mt5.ACCOUNT_TRADE_MODE_REAL: "GERCEK",
        }.get(ai.trade_mode, "bilinmiyor")
        marjin_modu = {
            mt5.ACCOUNT_MARGIN_MODE_RETAIL_NETTING: "Netting",
            mt5.ACCOUNT_MARGIN_MODE_EXCHANGE: "Borsa",
            mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING: "Hedging",
        }.get(ai.margin_mode, "bilinmiyor")
        cur = ai.currency

        yaz("")
        yaz("[HESAP]")
        yaz(f"  Hesap turu        : {tur}")
        yaz(f"  Para birimi       : {cur}")
        yaz(f"  Bakiye            : {para(ai.balance, cur)}")
        yaz(f"  Varlik (equity)   : {para(ai.equity, cur)}")
        yaz(f"  Serbest teminat   : {para(ai.margin_free, cur)}")
        yaz(f"  Kaldirac          : 1:{ai.leverage}")
        yaz(f"  Pozisyon modu     : {marjin_modu}")
        yaz(f"  Hesapta islem izni: {'EVET' if ai.trade_allowed else 'HAYIR'}")
        yaz(f"  Uzman/robot izni  : {'EVET' if ai.trade_expert else 'HAYIR'}")
        if ti is not None:
            yaz(f"  MT5 'Algo Trading' butonu: {'ACIK' if ti.trade_allowed else 'KAPALI'}")
            yaz(f"  MT5 surumu        : {ti.build}")
        yaz(f"  Acik pozisyon     : {mt5.positions_total()}")
        yaz(f"  Bekleyen emir     : {mt5.orders_total()}")

        bakiye = ai.balance
        risk1 = bakiye * RISK_HEDEF
        risk15 = bakiye * RISK_TAVAN
        yaz("")
        yaz(f"  Islem basina %1 risk   = {para(risk1, cur)}")
        yaz(f"  Islem basina %1,5 tavan = {para(risk15, cur)}")

        tum = mt5.symbols_get() or []
        yaz(f"  Kurumdaki toplam sembol sayisi: {len(tum)}")

        yaz("")
        yaz("[SEMBOLLER]")
        yaz("  Aciklama: 'En kucuk lot' ile acilan islemde;")
        yaz("   - Teminat  = islem icin bloke edilecek para")
        yaz("   - %1 hareket = fiyat %1 oynarsa kar/zarar")
        yaz(f"   - Ornek stop = 1 saatlik ATR14 x {ATR_STOP_KAT} mesafesinde stop olursa zarar")
        yaz("   - SIGAR MI? = ornek stop zarari bakiyenin %1'ine (veya %1,5'ine) sigiyor mu")
        yaz("")

        ozet_uygun = []
        for etiket, anahtarlar in ADAYLAR.items():
            s = sembol_bul(tum, anahtarlar)
            if s is None:
                yaz(f"- {etiket}: kurumda bulunamadi")
                continue
            ad = s.name
            onceden_gorunur = s.visible
            if not onceden_gorunur:
                mt5.symbol_select(ad, True)  # fiyat almak icin gecici
            try:
                info = mt5.symbol_info(ad)
                tick = mt5.symbol_info_tick(ad)
                if info is None or tick is None or not tick.ask:
                    yaz(f"- {etiket} [{ad}]: fiyat alinamadi (piyasa kapali olabilir)")
                    continue
                islem = {
                    mt5.SYMBOL_TRADE_MODE_DISABLED: "KAPALI",
                    mt5.SYMBOL_TRADE_MODE_LONGONLY: "sadece alis",
                    mt5.SYMBOL_TRADE_MODE_SHORTONLY: "sadece satis",
                    mt5.SYMBOL_TRADE_MODE_CLOSEONLY: "sadece kapatma",
                    mt5.SYMBOL_TRADE_MODE_FULL: "acik",
                }.get(info.trade_mode, "?")
                ask, bid = tick.ask, tick.bid
                vmin, vstep, vmax = info.volume_min, info.volume_step, info.volume_max
                teminat = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, ad, vmin, ask)
                yuzde1 = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, ad, vmin, ask, ask * 1.01)
                spread = ask - bid
                spread_yuzde = spread / ask * 100 if ask else 0
                atr = atr14_h1(ad)
                stop_zarar = None
                stop_yuzde = None
                atr_spread = None
                if atr:
                    stop_mesafe = atr * ATR_STOP_KAT
                    stop_yuzde = stop_mesafe / ask * 100
                    z = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, ad, vmin, ask, ask - stop_mesafe)
                    stop_zarar = abs(z) if z is not None else None
                    atr_spread = spread / atr * 100 if atr else None

                if stop_zarar is None:
                    sigar = "?"
                elif stop_zarar <= risk1:
                    sigar = "EVET (%1)"
                elif stop_zarar <= risk15:
                    sigar = "SINIRDA (%1,5)"
                else:
                    sigar = "HAYIR"
                if teminat is not None and teminat > ai.margin_free * 0.5:
                    sigar += " / teminat yuksek"

                yaz(f"- {etiket}  ->  kurumdaki adi: {ad}   (islem: {islem})")
                yaz(f"    Fiyat: {ask}   Alis-satis farki: {spread:.{info.digits}f} (%{spread_yuzde:.3f})")
                yaz(f"    Lot: en kucuk {vmin}, adim {vstep}, en buyuk {vmax}   Sozlesme: {info.trade_contract_size}")
                yaz(f"    En kucuk lotta teminat: {para(teminat, cur)}   %1 hareket: {para(yuzde1, cur)}")
                if atr:
                    yaz(f"    ATR14(1s): {atr:.{info.digits}f}  ornek stop: %{stop_yuzde:.2f}  "
                        f"-> zarar: {para(stop_zarar, cur)}   fark/ATR: %{atr_spread:.1f}")
                yaz(f"    SIGAR MI? {sigar}")
                if sigar.startswith("EVET") and info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
                    ozet_uygun.append(f"{etiket} [{ad}]")
            finally:
                if not onceden_gorunur:
                    mt5.symbol_select(ad, False)  # Market Watch'i eski haline getir

        yaz("")
        yaz("[OZET] %1 riske sigan ve islemi acik semboller:")
        if ozet_uygun:
            for u in ozet_uygun:
                yaz("   + " + u)
        else:
            yaz("   (hicbiri - bakiye kucuk olabilir, raporu Claude'a gonderin)")
    finally:
        mt5.shutdown()

    yaz("")
    yaz("Bitti. Hicbir emir gonderilmedi. Hesap numarasi rapora yazilmadi.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # beklenmeyen hata
        yaz("BEKLENMEYEN HATA: " + repr(e))
    finally:
        yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rapor.txt")
        try:
            with open(yol, "w", encoding="utf-8") as f:
                f.write("\n".join(satirlar) + "\n")
            print("")
            print("Rapor kaydedildi: " + yol)
        except Exception as e:
            print("Rapor dosyasi yazilamadi: " + repr(e))
