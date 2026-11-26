"""Uc yapay zeka saglayicisinin istemcileri.
Anahtarlar SADECE ortam degiskenlerinden okunur (GitHub Secrets):
ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY. Koda hicbir anahtar yazilmaz."""
import json
import os
import re

DEEPSEEK_ADRES = "https://api.deepseek.com"


class ModelHatasi(Exception):
    pass


def json_ayikla(metin):
    """Model cevabindan ilk JSON nesnesini cikar."""
    if not metin:
        raise ModelHatasi("bos cevap")
    metin = metin.strip()
    metin = re.sub(r"^```(?:json)?\s*|\s*```$", "", metin)
    try:
        return json.loads(metin)
    except json.JSONDecodeError:
        pass
    bas = metin.find("{")
    son = metin.rfind("}")
    if bas >= 0 and son > bas:
        try:
            return json.loads(metin[bas:son + 1])
        except json.JSONDecodeError as e:
            raise ModelHatasi(f"JSON okunamadi: {e}")
    raise ModelHatasi("cevapta JSON yok")


def _anthropic(cfg, sistem, kullanici, sema, zaman_asimi):
    import anthropic
    istemci = anthropic.Anthropic(timeout=zaman_asimi, max_retries=2)
    ortak = dict(
        model=cfg["model"],
        max_tokens=16000,
        system=sistem,
        messages=[{"role": "user", "content": kullanici}],
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # guvenlik reddinde sunucu tarafi yedek model
    )
    efor = cfg.get("efor", "medium")
    try:
        cevap = istemci.beta.messages.create(
            **ortak, output_config={"effort": efor, "format": {"type": "json_schema", "schema": sema}})
    except anthropic.BadRequestError:
        # Yapilandirilmis cikti desteklenmezse duz JSON talimatiyla tekrar dene
        cevap = istemci.beta.messages.create(**ortak, output_config={"effort": efor})
    if cevap.stop_reason == "refusal":
        raise ModelHatasi("model cevap vermeyi reddetti")
    metin = "".join(b.text for b in cevap.content if b.type == "text")
    sonuc = json_ayikla(metin)
    sonuc["_hizmet_eden_model"] = cevap.model
    return sonuc


def _openai_uyumlu(cfg, sistem, kullanici, zaman_asimi, deepseek):
    import openai
    if deepseek:
        istemci = openai.OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY"), base_url=DEEPSEEK_ADRES,
                                timeout=zaman_asimi, max_retries=2)
    else:
        istemci = openai.OpenAI(timeout=zaman_asimi, max_retries=2)
    mesajlar = [{"role": "system", "content": sistem}, {"role": "user", "content": kullanici}]
    try:
        cevap = istemci.chat.completions.create(
            model=cfg["model"], messages=mesajlar, response_format={"type": "json_object"},
            max_completion_tokens=16000)
    except openai.BadRequestError:
        cevap = istemci.chat.completions.create(model=cfg["model"], messages=mesajlar, max_completion_tokens=16000)
    sonuc = json_ayikla(cevap.choices[0].message.content)
    sonuc["_hizmet_eden_model"] = cevap.model
    return sonuc


def sor(cfg, sistem, kullanici, sema, zaman_asimi=240):
    """cfg: ayarlar.json'daki model kaydi. JSON sozluk dondurur ya da ModelHatasi firlatir."""
    try:
        if cfg["saglayici"] == "anthropic":
            return _anthropic(cfg, sistem, kullanici, sema, zaman_asimi)
        if cfg["saglayici"] == "openai":
            return _openai_uyumlu(cfg, sistem, kullanici, zaman_asimi, deepseek=False)
        if cfg["saglayici"] == "deepseek":
            return _openai_uyumlu(cfg, sistem, kullanici, zaman_asimi, deepseek=True)
    except ModelHatasi:
        raise
    except Exception as e:  # ag, kimlik, model adi vb.
        raise ModelHatasi(f"{type(e).__name__}: {str(e)[:300]}")
    raise ModelHatasi("bilinmeyen saglayici")


def model_listesi(saglayici):
    """Saglayicinin sundugu model adlari (kurul testinde ad dogrulamak icin)."""
    if saglayici == "anthropic":
        import anthropic
        return [m.id for m in anthropic.Anthropic().models.list()]
    import openai
    if saglayici == "deepseek":
        istemci = openai.OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY"), base_url=DEEPSEEK_ADRES)
    else:
        istemci = openai.OpenAI()
    return [m.id for m in istemci.models.list()]
