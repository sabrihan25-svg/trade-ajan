# Trade Ajanı

Üç yapay zeka modelinin (Claude Fable 5.2, GPT-6 Astra, DeepSeek V4 Pro) birlikte karar verdiği,
MetaTrader 5'te işlem yapan bir sistem.

> **Uyarı:** Bu sistem gerçek parayla risk alır. Kâr garantisi yoktur. Yapay zeka maliyeti
> ayda yaklaşık 20-40 $'dır. Önce demo hesapla deneyin.

## İki parça

**1. Beyin** (bu depo, GitHub Actions ile ~3 dakikada bir çalışır)
- EURUSD, USDJPY ve GBPUSD mumlarını tarar: 1 saatlik trend + 15 dakikalık giriş.
- Göstergeleri kod hesaplar: EMA50/200, RSI14, ATR14, son tepe/dip.
- Bir fırsat görünce (geri çekilmenin bitmesi ya da seviye kırılımı) üç modele aynı veri paketi gider.
- Modeller birbirini görmeden, paralel oy verir.
- Üçü de aynı yönü derse ve en düşük güven ≥ 0,6 ise sırayla bir model "şeytanın avukatı" olur.
  Ciddi veto yoksa `sinyaller/sinyal.json` yazılır. Aksi her durumda işlem yok.
- Günde en fazla 6 kurul toplantısı yapılır.
- 100 $'lık gölge (kâğıt) hesap her sinyali takip eder. Her modelin karnesi `durum/durum.json` içinde tutulur.

**2. Köprü** (`kopru/kopru.py`, Windows'ta MT5'in yanında)
- Sinyal dosyasını dakikada bir okur. Eski ya da fiyatı kaçmış sinyali atlar.
- Kuralları gerçek bakiyeye göre kendisi de uygular. Emri zarar durdur + hedefle gönderir.
- Açılışta "kablo testi" yapar. EVET yazılmazsa TEST modunda kalır ve emir göndermez.
- Hiçbir şifre ya da anahtar içermez.

## Hayatta kalma kuralları (kodda; hem beyinde hem köprüde)
- İşlem başına risk ~%1 (en fazla %1,5). En küçük işlem bile sığmıyorsa işlem açılmaz.
- Ölüm çizgisi: hesap başlangıcın %70'ine inerse ajan kalıcı durur.
- Günlük %3, haftalık %6 zarar sınırı.
- Aynı anda tek açık işlem. Art arda 3 zarardan sonra 24 saat mola.
- Hedef, stopun en az 1,5 katı olmalı. Alış-satış farkı çok genişse işlem yok.
- Önemli ABD veri saatlerinde (±30 dk) işlem yok. Hafta sonuna işlem taşınmaz.

## Kullanım
1. **Anahtarlar:** Settings → Secrets and variables → Actions bölümüne şunları ekleyin:
   `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`.
2. **Kurul testi:** Actions → "Kurul testi" → Run workflow. Üç modelin cevap verdiğini doğrular.
3. **Beyni açmak:** `config/ayarlar.json` içinde `"beyin_acik": true` yapın.
4. **Köprü:** `kopru/kopru.py` ve `kopru/KOPRU_BASLAT.bat` dosyalarını aynı klasöre indirin.
   MT5'i açın ve `KOPRU_BASLAT.bat` dosyasına çift tıklayın.

## Klasörler
- `beyin/`: beyin kodu
- `kopru/`: köprü
- `config/ayarlar.json`: semboller, model adları, kurul ayarları
- `sinyaller/`: köprünün okuduğu sinyal ve haber takvimi
- `durum/`: gölge hesap, model karnesi, kurul kayıtları
- `testler/`: sahte verilerle testler (`python -m unittest discover -s testler -t .`)
- `araclar/`: MT5 hesap kontrol aracı (sadece okur)

Depoya gerçek hesap numarası, bakiye ya da kurum bilgisi **yazılmaz**.
