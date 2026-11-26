"""MetaTrader5 paketinin sahtesi (kopru testleri icin). Gercek MT5 sadece Windows'ta calisir."""
import time
from types import SimpleNamespace as N

ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_TRADE_MODE_CONTEST, ACCOUNT_TRADE_MODE_REAL = 0, 1, 2
SYMBOL_TRADE_MODE_FULL = 4
ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
POSITION_TYPE_BUY, POSITION_TYPE_SELL = 0, 1
TRADE_ACTION_DEAL = 1
ORDER_TIME_GTC = 0
ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
TRADE_RETCODE_DONE = 10009
DEAL_ENTRY_OUT = 1
TIMEFRAME_H1 = 16385

DURUM = {}


def sifirla(bakiye=1000.0, varlik=None, fiyat=1.1, fark=0.00008, vmin=0.01):
    DURUM.clear()
    DURUM.update(bakiye=bakiye, varlik=varlik if varlik is not None else bakiye, fiyat=fiyat, fark=fark,
                 vmin=vmin, pozisyonlar=[], gonderilen=[], kontrol_edilen=[], islemler=[], algo=True)


def initialize(): return True
def shutdown(): pass
def last_error(): return (0, "ok")
def terminal_info(): return N(trade_allowed=DURUM["algo"], build=5000)


def account_info():
    return N(login=123, server="Demo", trade_mode=0, balance=DURUM["bakiye"], equity=DURUM["varlik"],
             margin_free=DURUM["varlik"], currency="USD", leverage=100)


def symbol_select(ad, v=True): return True


def symbol_info(ad):
    return N(trade_mode=4, volume_min=DURUM["vmin"], volume_step=0.01, volume_max=100, digits=5,
             point=0.00001, trade_stops_level=0, filling_mode=1)


def symbol_info_tick(ad):
    return N(ask=DURUM["fiyat"] + DURUM["fark"], bid=DURUM["fiyat"], time=int(time.time()))


def copy_rates_from_pos(ad, tf, bas, adet):
    p = DURUM["fiyat"]
    return [{"high": p + 0.0005, "low": p - 0.0005, "close": p} for _ in range(adet)]


def order_calc_profit(tip, ad, lot, giris, cikis):
    fark = (cikis - giris) if tip == ORDER_TYPE_BUY else (giris - cikis)
    return fark * lot * 100000


def order_check(istek):
    DURUM["kontrol_edilen"].append(istek)
    return N(retcode=0, comment="Done", margin=istek["volume"] * 1100, margin_free=DURUM["varlik"] - 100)


def order_send(istek):
    DURUM["gonderilen"].append(istek)
    return N(retcode=TRADE_RETCODE_DONE, order=555, comment="Done")


def positions_get(): return DURUM["pozisyonlar"]
def positions_total(): return len(DURUM["pozisyonlar"])
def orders_total(): return 0
def history_deals_get(bas, son): return DURUM["islemler"]
