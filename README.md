# EgoCepteBOT Ego Cep'te Telegram Botu

EgoCepteBOT, Ankara Büyükşehir Belediyesi EGO Genel Müdürlüğü'nün otobüs takip sisteminden veri çekerek kullanıcılara gerçek zamanlı otobüs durağı ve hat bilgileri sunan bir Telegram botudur. Bu bot sayesinde, favori duraklarınızı kaydedebilir, otobüslerin tahmini varış sürelerini öğrenebilir ve toplu taşıma deneyiminizi kolaylaştırabilirsiniz.

## Özellikler

* **Gerçek Zamanlı Durak Bilgisi:** Belirli bir durak numarasındaki tüm otobüslerin veya filtrelenmiş bir hattın tahmini varış sürelerini, araç numaralarını, plakalarını ve durak sıralarını gösterir.
* **Favori Durak Yönetimi:** Sık kullandığınız durakları favorilerinize ekleyebilir, favorilerinize özel isimler verebilir ve tek tıkla bu durakların bilgilerine ulaşabilirsiniz.
* **Kolay Favori Silme:** Kayıtlı favorilerinizi kolayca silebilirsiniz.
* **Kullanışlı Klavye:** Favori duraklarınıza ve ana komutlara hızlı erişim sağlayan özel bir klavye sunar.
* **Kullanıcı Dostu Arayüz:** Telegram botu arayüzü sayesinde kolay ve hızlı kullanım imkanı sunar.

## Kurulum

EgoCepteBOT'u kendi sunucunuzda çalıştırmak için aşağıdaki adımları izleyin:

### Önkoşullar

* Python 3.8 veya üzeri
* `pip` paket yöneticisi
* Telegram Bot API Token'ı
* EGO Web Sitesi Cookie'si (otobüs verilerini çekmek için gereklidir)

### Adımlar

1.  **Depoyu Klonlayın:**
    ```bash
    git clone https://github.com/kullanici_adiniz/EgoCepteBOT.git
    cd EgoCepteBOT
    ```

2.  **Sanal Ortam Oluşturun (Önerilir):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # veya
    .\venv\Scripts\activate    # Windows
    ```

3.  **Gerekli Kütüphaneleri Yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```
    (Eğer `requirements.txt` dosyanız yoksa, aşağıdaki paketleri manuel olarak yükleyebilirsiniz: `python-dotenv`, `requests`, `beautifulsoup4`, `python-telegram-bot`)

4.  **Ortam Değişkenlerini Ayarlayın:**
    Botun çalışması için gerekli olan hassas bilgileri `.env` dosyasına kaydedin. Proje dizininizde `.env` adında bir dosya oluşturun ve aşağıdaki bilgileri ekleyin:

    ```env
    TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    EGO_WEB_COOKIE="EGOWEB_Cookie=YOUR_EGO_COOKIE_VALUE"
    ADMIN_CHAT_ID="YOUR_ADMIN_TELEGRAM_CHAT_ID" # İsteğe bağlı, bot başlatıldığında bildirim almak için
    DEBUG_MODE="False" # Geliştirme için "True" olarak ayarlanabilir
    ```
    * `TELEGRAM_BOT_TOKEN`: BotFather'dan aldığınız Telegram bot token'ınızı buraya yapıştırın.
    * `EGO_WEB_COOKIE`: EGO'nun otobüs nerede sayfasından ([https://www.ego.gov.tr/tr/otobusnerede](https://www.ego.gov.tr/tr/otobusnerede)) bir tarayıcıda geliştirici araçlarını kullanarak `EGOWEB_Cookie` değerini bulun ve buraya yapıştırın. Bu çerez zaman zaman değişebilir, bu durumda botun çalışması için güncellenmesi gerekir.
    * `ADMIN_CHAT_ID`: Botun başlatıldığında size bildirim göndermesini istediğiniz Telegram sohbet ID'nizi girin. İsteğe bağlıdır, 0 olarak bırakılabilir.

5.  **Botu Çalıştırın:**
    ```bash
    python EgoCepteBOT.py
    ```

Botunuz artık çalışıyor olmalı ve Telegram üzerinden erişilebilir durumda olmalıdır.

## Kullanım

Botu Telegram'da başlattıktan sonra aşağıdaki komutları ve butonları kullanabilirsiniz:

* **`/start`**: Bot ile etkileşimi başlatır ve ana menüyü görüntüler.
* **`/help`**: Botun tüm komutları ve özellikleri hakkında detaylı bilgi verir.

### Durak Bilgisi Sorgulama

* **`/durak <durak_no>`**: Belirli bir durak numarasındaki otobüslerin tahmini varış sürelerini ve hat bilgilerini öğrenin.
    * Örnek: `/durak 11618`
* **`/durak <durak_no> <hat_no>`**: Belirli bir duraktaki sadece istediğiniz hat numarasına ait otobüs bilgilerini filtreleyin.
    * Örnek: `/durak 11618 413`

### Favori Yönetimi

Favori duraklarınızı kaydederek tek tıkla bilgilere ulaşabilirsiniz.

* **`/favori`** veya **`➕ Favori Ekle`**: Yeni bir favori durak eklemek için bu komutu kullanın. Bot size adım adım rehberlik edecektir:
    1.  Durağın numarasını girin.
    2.  Favori için bir isim girin (örn: "Ev Durağı").
* **`/sil`** veya **`➖ Favori Sil`**: Mevcut favori duraklarınızı silmek için bu komutu kullanın. Silmek istediğiniz favoriyi listeden seçebilirsiniz.
* **`/favorilerim`** veya **`⭐ Favorilerim`**: Kayıtlı tüm favori duraklarınızı görmek ve hızlıca seçmek için bu komutu kullanın.
* **`/gizle_favoriler`**: Aktif olan favori klavyesini gizler.

### Örnek Etkileşimler

* Kullanıcı: `/start`
    * Bot: "👋 Merhaba [Kullanıcı Adı]! Ankara EGO otobüs durak bilgilerini almak için `/durak <no>` kullanın..."
* Kullanıcı: `/durak 11618`
    * Bot: "⏳ '11618' için bilgiler alınıyor..." (Ardından otobüs bilgileri listelenir)
* Kullanıcı: `➕ Favori Ekle`
    * Bot: "📍 Favori olarak eklemek istediğiniz durağın numarasını girin (İptal için /iptal):"
    * Kullanıcı: `11618`
    * Bot: "📝 '11618' durağı için bir favori ismi girin (Örn: Ev Durağı) (İptal için /iptal):"
    * Kullanıcı: `Kızılay Durağı`
    * Bot: "✅ 'Kızılay Durağı' (11618) favorilerinize eklendi! 🎉"

## Geliştirme

* **Logging:** Bot, çalışma sırasında önemli bilgileri ve hataları konsola kaydeder. Sorun giderme için bu logları takip edebilirsiniz.
* **Hata Yönetimi:** Web sitesinden veri çekme veya API isteklerinde oluşabilecek hatalar için temel hata yönetimi mevcuttur.
* **Favori Verileri:** Favori duraklar, `favorites.json` adlı bir dosyada JSON formatında saklanır. Bu dosya, botun her başlatılışında yüklenir ve güncellemeler otomatik olarak kaydedilir.

## Katkıda Bulunma

Geliştirmeye katkıda bulunmak isterseniz, lütfen bir pull request açmaktan çekinmeyin. Yeni özellikler, hata düzeltmeleri veya iyileştirmeler her zaman memnuniyetle karşılanır.

## Lisans

Bu proje MIT Lisansı altında lisanslanmıştır. Daha fazla bilgi için `LICENSE` dosyasına bakın.

---
