"""Gostergeler: EMA, RSI, ATR, son tepe/dip. Saf Python, dis paket yok.
Mumlar: [{"t": unix_sn, "o":..., "h":..., "l":..., "c":...}, ...] eskiden yeniye."""


def ema(degerler, periyot):
    if len(degerler) < periyot:
        return [None] * len(degerler)
    k = 2 / (periyot + 1)
    sonuc = [None] * (periyot - 1)
    e = sum(degerler[:periyot]) / periyot
    sonuc.append(e)
    for v in degerler[periyot:]:
        e = v * k + e * (1 - k)
        sonuc.append(e)
    return sonuc


def rsi(kapanislar, periyot=14):
    if len(kapanislar) <= periyot:
        return [None] * len(kapanislar)
    sonuc = [None] * periyot
    kazanc = kayip = 0.0
    for i in range(1, periyot + 1):
        d = kapanislar[i] - kapanislar[i - 1]
        kazanc += max(d, 0)
        kayip += max(-d, 0)
    ort_k, ort_z = kazanc / periyot, kayip / periyot

    def hesap(k, z):
        if z == 0:
            return 100.0
        return 100 - 100 / (1 + k / z)

    sonuc.append(hesap(ort_k, ort_z))
    for i in range(periyot + 1, len(kapanislar)):
        d = kapanislar[i] - kapanislar[i - 1]
        ort_k = (ort_k * (periyot - 1) + max(d, 0)) / periyot
        ort_z = (ort_z * (periyot - 1) + max(-d, 0)) / periyot
        sonuc.append(hesap(ort_k, ort_z))
    return sonuc


def atr(mumlar, periyot=14):
    if len(mumlar) <= periyot:
        return [None] * len(mumlar)
    trs = [mumlar[0]["h"] - mumlar[0]["l"]]
    for i in range(1, len(mumlar)):
        h, l, pc = mumlar[i]["h"], mumlar[i]["l"], mumlar[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    sonuc = [None] * (periyot - 1)
    a = sum(trs[:periyot]) / periyot
    sonuc.append(a)
    for tr in trs[periyot:]:
        a = (a * (periyot - 1) + tr) / periyot
        sonuc.append(a)
    return sonuc


def son_tepe_dip(mumlar, pencere=20, haric_son=1):
    """Son 'pencere' mumdaki en yuksek tepe ve en dusuk dip (son mum(lar) haric)."""
    parca = mumlar[-(pencere + haric_son):-haric_son] if haric_son else mumlar[-pencere:]
    if not parca:
        return None, None
    return max(m["h"] for m in parca), min(m["l"] for m in parca)


def ozet(mumlar):
    """Bir zaman dilimi icin tum gostergeleri hesapla."""
    kap = [m["c"] for m in mumlar]
    e50, e200 = ema(kap, 50), ema(kap, 200)
    r, a = rsi(kap, 14), atr(mumlar, 14)
    tepe, dip = son_tepe_dip(mumlar, 20, 1)
    return {
        "kapanis": kap[-1],
        "ema50": e50[-1], "ema200": e200[-1],
        "ema50_once": e50[-6] if len(e50) >= 6 else None,
        "rsi": r[-1], "rsi_once": r[-2] if len(r) >= 2 else None,
        "atr": a[-1],
        "son_tepe": tepe, "son_dip": dip,
        "seriler": {"ema50": e50, "rsi": r, "atr": a},
    }
