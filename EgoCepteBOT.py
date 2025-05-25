from dotenv import load_dotenv
load_dotenv()

import requests
from bs4 import BeautifulSoup
import logging
import re
import os
import asyncio
import uuid
import json

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Bot Token'ı ve Cookie'yi Ortam Değişkenlerinden Alın
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
EGO_COOKIE = os.getenv("EGO_WEB_COOKIE", "EGOWEB_Cookie=dvze3m3mdzrwf4zatodx05ic")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", 0))

# Logging Kurulumu
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# EGO Sitesi Bilgileri
BASE_EGO_URL = "https://www.ego.gov.tr/tr/otobusnerede"
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,application/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Cookie": EGO_COOKIE,
    "Host": "www.ego.gov.tr",
    "Referer": "https://www.ego.gov.tr/tr/otobusnerede",
    "Sec-Ch-Ua": '"Google Chrome";v="125", "Not.A/Brand";v="24", "Chromium";v="125"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# Favori Ekleme için State'ler
GET_FAV_STOP_ID, GET_FAV_NAME = range(2)

# Favori Silme için Yeni State'ler
SELECT_FAV_TO_DELETE, CONFIRM_DELETE = range(2, 4)

# Favori Dosyası Tanımı
FAVORITES_FILE = "favorites.json"

# Favori Yükleme ve Kaydetme Fonksiyonları
def load_all_favorites():
    """Tüm kullanıcıların favorilerini dosyadan yükler."""
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Favoriler dosyası okunurken hata oluştu, yeni dosya oluşturulacak: {e}")
            return {}
    return {}

def save_all_favorites(all_favorites_data):
    """Tüm kullanıcıların favorilerini dosyaya kaydeder."""
    try:
        with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_favorites_data, f, indent=4)
    except IOError as e:
        logger.error(f"Favoriler dosyasına yazılırken hata oluştu: {e}")

# Veri Kazıma Fonksiyonu
def scrape_bus_times_from_ego(stop_id: str, hat_no_param: str = None):
    params = {"durak_no": stop_id}
    if hat_no_param: params["hat_no"] = hat_no_param
    response_url_debug = ""
    try:
        request_url_object = requests.Request('GET', BASE_EGO_URL, params=params, headers=HEADERS).prepare()
        response_url_debug = request_url_object.url
        logger.info(f"EGO'dan veri çekiliyor: URL={response_url_debug}")
        response = requests.get(BASE_EGO_URL, params=params, headers=HEADERS, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        otobus_tablosu = soup.find('table', class_='list')
        if not otobus_tablosu:
            logger.warning(f"Durak {stop_id} için otobüs tablosu bulunamadı.")
            return []

        buses_data = []
        all_rows_in_table = otobus_tablosu.find_all('tr')
        if not all_rows_in_table or not all_rows_in_table[0].find('th'): return []
        data_rows = all_rows_in_table[1:]
        if not data_rows: return []

        for i in range(0, len(data_rows), 2):
            if i + 1 >= len(data_rows): break
            hat_info_row = data_rows[i]
            details_row = data_rows[i+1]
            hat_cols = hat_info_row.find_all('td')
            detail_cell_container = details_row.find('td')

            if not (hat_cols and len(hat_cols) >= 2 and detail_cell_container): continue
            
            try:
                hat_no_text = hat_cols[0].get_text(strip=True)
                hat_adi_text = hat_cols[1].get_text(strip=True)
                i_tag = detail_cell_container.find('i')
                kalan_sure_str, arac_no_str, plaka_str, durak_sirasi_str, ozellikler_str = "N/A", "N/A", "N/A", "N/A", "Yok"

                if i_tag:
                    b_tag_varis = i_tag.find('b')
                    if b_tag_varis:
                        kalan_sure_full_text = b_tag_varis.get_text(strip=True)
                        kalan_sure_str = kalan_sure_full_text.replace("Tahmini Varış Süresi:", "").strip()
                    combined_info_line = " ".join(s.strip() for s in i_tag.stripped_strings if s.strip() and s.strip() != kalan_sure_str and "Tahmini Varış Süresi:" not in s)
                    match = re.search(r"Araç No:\s*([\w-]+)", combined_info_line)
                    if match: arac_no_str = match.group(1)
                    match = re.search(r"Plaka:\s*([\dA-Z\s]+?)(?=\s*Bulunduğu Durak Sırası|$|\s*Özellikler:)", combined_info_line, re.IGNORECASE)
                    if match: plaka_str = match.group(1).strip()
                    match = re.search(r"Bulunduğu Durak Sırası:\s*([\d\/]+)", combined_info_line)
                    if match: durak_sirasi_str = match.group(1)
                    ozellikler_match = re.search(r"Özellikler:\s*(.+)", combined_info_line, re.IGNORECASE)
                    if ozellikler_match: ozellikler_str = ozellikler_match.group(1).strip()
                
                buses_data.append({
                    "hat_no": hat_no_text, "hat_adi": hat_adi_text, "kalan_sure": kalan_sure_str,
                    "arac_no": arac_no_str, "plaka": plaka_str, "durak_sirasi": durak_sirasi_str,
                    "ozellikler": ozellikler_str
                })
            except Exception as e:
                logger.error(f"Otobüs {i//2 + 1} işlenirken hata: {e}", exc_info=True)
                continue
        return buses_data
    except requests.exceptions.RequestException as e:
        logger.error(f"EGO isteğinde hata (Durak: {stop_id}): {e}")
        return None
    except Exception as e:
        logger.error(f"scrape_bus_times_from_ego bilinmeyen hata: {e}", exc_info=True)
        return None

async def send_bus_info_message(chat_id: int, context: ContextTypes.DEFAULT_TYPE, stop_id: str, hat_no_filter: str = None, processing_message=None):
    if processing_message:
        await processing_message.edit_text(
            f"⏳ '{stop_id}' numaralı durak için bilgiler alınıyor..." + (f" (Hat: {hat_no_filter})" if hat_no_filter else "")
        )
    else:
        processing_message = await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏳ '{stop_id}' için bilgiler alınıyor..." + (f" (Hat: {hat_no_filter})" if hat_no_filter else "")
        )
    bus_arrival_data = await asyncio.to_thread(scrape_bus_times_from_ego, stop_id, hat_no_filter)
    reply_message_text = ""
    if bus_arrival_data is None:
        reply_message_text = "❌ Veri alınırken bir sorun oluştu. Lütfen daha sonra tekrar deneyin."
    elif not bus_arrival_data:
        reply_message_text = (f"ℹ️ '{stop_id}' numaralı durak için" +
                              (f" (Filtrelenen Hat: {hat_no_filter})" if hat_no_filter else "") +
                              " şu anda gelen otobüs bilgisi bulunamadı.")
    else:
        message_parts = [f"🚌 Durak No: {stop_id}" + (f" (Hat: {hat_no_filter})" if hat_no_filter else "") + "\n\nYaklaşan Otobüsler:\n"]
        for bus in bus_arrival_data:
            hat_no = bus.get('hat_no', 'Bilinmiyor')
            hat_adi = bus.get('hat_adi', '')
            kalan_sure = bus.get('kalan_sure', 'N/A')
            arac_no = bus.get('arac_no', 'N/A')
            plaka = bus.get('plaka', 'N/A')
            durak_sirasi = bus.get('durak_sirasi', 'N/A')
            ozellikler = bus.get('ozellikler', 'Yok')
            message_parts.append(
                f"\n🚍 Hat: {hat_no} ({hat_adi})\n"
                f"  ⏰ Tahmini Süre: *{kalan_sure}*\n" # Kalan süre kalın
                f"  🆔 Araç: {arac_no} | Plaka: {plaka}\n"
                f"  📍 Durak Sırası: {durak_sirasi}"
            )
            if ozellikler and ozellikler.lower() not in ["n/a", "yok", ""]:
                message_parts.append(f"\n  ✨ Özellikler: {ozellikler}")
            message_parts.append("\n--------------------------")
        reply_message_text = "".join(message_parts)

    if len(reply_message_text) > 4096:
        reply_message_text = reply_message_text[:4090] + "\n[Mesaj kısaltıldı...]"
    await processing_message.edit_text(reply_message_text, parse_mode='Markdown') # Markdown desteği eklendi


# Komut Handler'ları
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 Merhaba {user_name}!\n"
        "Ankara EGO otobüs durak bilgilerini almak için `/durak <no>` kullanın.\n\n"
        "Aşağıdaki butonları veya komutları kullanabilirsiniz:\n"
        "➕ Favori Ekle (veya /favori)\n"
        "➖ Favori Sil (veya /sil)\n"
        "⭐ Favorilerim (veya /favorilerim)\n"
        "⌨️ Klavye Gizle (veya /gizle_favoriler)\n"
        "❓ Yardım için /help yazın." # Yeni eklenen satır
    )
    await show_favorites_keyboard(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kullanıcının /help komutuna yanıt verir ve bot hakkında bilgi sunar."""
    help_message = """Merhaba! Ben Ankara EGO Otobüs Durağı Asistanınızım. Amacım, Ankara'daki toplu taşıma deneyiminizi kolaylaştırmak. İşte yapabileceklerim ve kullanabileceğiniz komutlar:

🚌 *Durak Bilgisi Sorgulama:*
   `/durak <durak_no>`: Belirli bir durak numarasındaki otobüslerin tahmini varış sürelerini ve hat bilgilerini öğrenin.
   Örnek: `/durak 11618`
   `/durak <durak_no> <hat_no>`: Belirli bir duraktaki sadece istediğiniz hat numarasına ait otobüs bilgilerini filtreleyin.
   Örnek: `/durak 11618 413`

⭐ *Favori Yönetimi:*
   Favori duraklarınızı kaydederek tek tıkla bilgilere ulaşabilirsiniz.
   `/favori` veya `➕ Favori Ekle`: Yeni bir favori durak eklemek için bu komutu kullanın. Bot size adım adım rehberlik edecektir.
   `/sil` veya `➖ Favori Sil`: Mevcut favori duraklarınızı silmek için bu komutu kullanın. Silmek istediğiniz favoriyi listeden seçebilirsiniz.
   `/favorilerim` veya `⭐ Favorilerim`: Kayıtlı tüm favori duraklarınızı görmek ve hızlıca seçmek için bu komutu kullanın.

⚙️ *Genel Komutlar:*
   `/start`: Bot ile etkileşimi başlatır ve ana menüyü görüntüler.
   `/help`: Bu yardım mesajını gösterir.
   `/gizle_favoriler`: Aktif olan favori klavyesini gizler.

Sizin için en iyi deneyimi sunmak için sürekli geliştiriliyorum. Herhangi bir sorunuz olursa çekinmeden sorun!
"""
    await update.message.reply_text(help_message, parse_mode='Markdown')


async def get_stop_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Lütfen bir durak numarası girin. Örnek: `/durak 11618`")
        return
    stop_id = context.args[0]
    hat_no_filter = context.args[1] if len(context.args) > 1 else None
    if hat_no_filter and not re.fullmatch(r"^\d+(-\d+)?$", hat_no_filter):
        await update.message.reply_text("❌ Hat numarası geçersiz formatta.")
        return
    if not stop_id.isdigit():
        await update.message.reply_text("❌ Durak numarası sadece rakamlardan oluşmalıdır.")
        return
    processing_message = await update.message.reply_text(f"⏳ '{stop_id}' için bilgiler alınıyor...")
    await send_bus_info_message(update.effective_chat.id, context, stop_id, hat_no_filter, processing_message=processing_message)


# Favori Ekleme İşlemleri (ReplyKeyboardMarkup ile)
async def fav_start_command_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ /favori veya '➕ Favori Ekle' butonu ile tetiklenir. """
    await update.message.reply_text(
        "📍 Favori olarak eklemek istediğiniz durağın numarasını girin (İptal için /iptal):",
        reply_markup=ReplyKeyboardRemove()
    )
    return GET_FAV_STOP_ID

async def fav_received_stop_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    stop_id = update.message.text.strip()
    if not stop_id.isdigit():
        await update.message.reply_text("❌ Geçersiz durak numarası. Lütfen sadece rakam girin veya /iptal yazın:")
        return GET_FAV_STOP_ID
    context.user_data['current_fav_stop_id'] = stop_id
    await update.message.reply_text(f"📝 '{stop_id}' durağı için bir favori ismi girin (Örn: Ev Durağı) (İptal için /iptal):")
    return GET_FAV_NAME

async def fav_received_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    fav_name = update.message.text.strip()
    stop_id = context.user_data.pop('current_fav_stop_id', None)
    
    if not stop_id:
        await update.message.reply_text("⚠️ Bir hata oluştu. Lütfen /favori komutuyla tekrar deneyin.")
        await show_favorites_keyboard(update, context)
        return ConversationHandler.END
    
    if not fav_name:
        await update.message.reply_text("⚠️ Favori ismi boş olamaz. Lütfen bir isim girin veya /iptal yazın:")
        context.user_data['current_fav_stop_id'] = stop_id
        return GET_FAV_NAME

    user_id_str = str(update.effective_user.id)
    user_favorites = context.user_data.setdefault('favorites', {}) 

    for existing_fav_id, existing_fav_data in user_favorites.items():
        if existing_fav_data['name'] == fav_name:
            await update.message.reply_text(f"❗ '{fav_name}' isminde bir favoriniz zaten var. Lütfen farklı bir isim seçin veya /iptal yazın.")
            context.user_data['current_fav_stop_id'] = stop_id
            return GET_FAV_NAME
    
    fav_id = uuid.uuid4().hex
    user_favorites[fav_id] = {'stop_id': stop_id, 'name': fav_name}
    
    all_users_favorites = context.bot_data.setdefault('all_users_favorites', {})
    all_users_favorites[user_id_str] = user_favorites
    save_all_favorites(all_users_favorites)

    logger.info(f"Kullanıcı {user_id_str} için yeni favori: {fav_name} ({stop_id})")
    await update.message.reply_text(f"✅ '{fav_name}' ({stop_id}) favorilerinize eklendi! 🎉")
    await show_favorites_keyboard(update, context)
    return ConversationHandler.END

async def fav_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop('current_fav_stop_id', None)
    context.user_data.pop('fav_to_delete_id', None)
    await update.message.reply_text("❌ İşlem iptal edildi.")
    await show_favorites_keyboard(update, context)
    return ConversationHandler.END


async def show_favorites_keyboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/favorilerim komutu için"""
    await show_favorites_keyboard(update, context, show_message_if_empty=True)


async def show_favorites_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE, show_message_if_empty=True) -> None:
    """Kullanıcının favorilerini ve genel komut butonlarını ReplyKeyboardMarkup olarak gösterir."""
    favorites = context.user_data.get('favorites', {})
    
    keyboard_buttons = []
    if favorites:
        row = []
        for fav_data in favorites.values():
            row.append(KeyboardButton(f"🚌 {fav_data['name']}")) # Otobüs emojisi eklendi
            if len(row) == 2:
                keyboard_buttons.append(row)
                row = []
        if row:
            keyboard_buttons.append(row)
    
    keyboard_buttons.append([KeyboardButton("➕ Favori Ekle")])
    keyboard_buttons.append([KeyboardButton("➖ Favori Sil")])

    if not favorites and not show_message_if_empty:
         reply_markup = ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True, one_time_keyboard=False)
         await update.message.reply_text("Favori menüsü:", reply_markup=reply_markup, disable_notification=True)
         return

    if not favorites and show_message_if_empty:
        await update.message.reply_text(
            "⭐ Henüz hiç favori eklemediniz.",
            reply_markup=ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True, one_time_keyboard=False)
        )
        return

    reply_markup = ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True, one_time_keyboard=False)
    message_text = "⭐ Favori Duraklarınız (veya komut seçin):" if favorites else "Favori menüsü:"
    await update.message.reply_text(message_text, reply_markup=reply_markup, disable_notification=True)


# YENİ FAVORİ SİLME İŞLEMLERİ
async def delete_fav_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    '➖ Favori Sil' butonuna basıldığında veya /sil komutuyla tetiklenir.
    Mevcut favorileri butonlar olarak listeler.
    """
    favorites = context.user_data.get('favorites', {})
    if not favorites:
        await update.message.reply_text(
            "🗑️ Silinecek favoriniz bulunmuyor. Önce /favori ile ekleyin.",
            reply_markup=await get_current_reply_keyboard_markup(context)
        )
        return ConversationHandler.END

    keyboard = []
    for fav_id, fav_data in favorites.items():
        keyboard.append([KeyboardButton(f"🗑️ {fav_data['name']}")]) # Silme butonu emojisi
    keyboard.append([KeyboardButton("❌ İptal")])

    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Silmek istediğiniz favoriyi seçin veya '❌ İptal' diyerek çıkın:",
        reply_markup=reply_markup
    )
    return SELECT_FAV_TO_DELETE

async def select_fav_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kullanıcı bir favori butona tıkladığında çalışır."""
    selected_text = update.message.text.strip() # Doğrudan gelen metni al

    # İptal butonu kontrolü
    if selected_text == "❌ İptal": # Emojili tam metni kontrol et
        await fav_cancel(update, context)
        return ConversationHandler.END

    # Favori adı ise emojiyi temizleyerek kontrol et
    selected_name = selected_text.replace("🗑️ ", "")

    favorites = context.user_data.get('favorites', {})
    fav_to_delete_id = None
    fav_to_delete_data = None

    for fav_id, fav_data in favorites.items():
        if fav_data['name'] == selected_name:
            fav_to_delete_id = fav_id
            fav_to_delete_data = fav_data
            break
    
    if fav_to_delete_id:
        context.user_data['fav_to_delete_id'] = fav_to_delete_id
        
        keyboard = [
            [KeyboardButton("✅ Evet, Sil")],
            [KeyboardButton("❌ Hayır, İptal")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"🗑️ '{fav_to_delete_data['name']}' ({fav_to_delete_data['stop_id']}) favorisini silmek istediğinizden emin misiniz?",
            reply_markup=reply_markup
        )
        return CONFIRM_DELETE
    else:
        await update.message.reply_text(
            "❗ Geçersiz favori seçimi. Lütfen listeden bir favori seçin veya '❌ İptal' yazın.",
            reply_markup=await get_delete_fav_keyboard(context)
        )
        return SELECT_FAV_TO_DELETE

async def confirm_delete_fav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kullanıcı silme onayını verdiğinde veya iptal ettiğinde çalışır."""
    choice = update.message.text.strip()
    fav_id_to_delete = context.user_data.pop('fav_to_delete_id', None)

    if choice == "✅ Evet, Sil" and fav_id_to_delete:
        user_favorites = context.user_data.get('favorites', {})
        if fav_id_to_delete in user_favorites:
            deleted_fav_name = user_favorites[fav_id_to_delete]['name']
            del user_favorites[fav_id_to_delete]
            
            user_id_str = str(update.effective_user.id)
            all_users_favorites = context.bot_data.setdefault('all_users_favorites', {})
            all_users_favorites[user_id_str] = user_favorites
            save_all_favorites(all_users_favorites)

            logger.info(f"Kullanıcı {user_id_str} favoriyi sildi: {deleted_fav_name}")
            await update.message.reply_text(f"🗑️ '{deleted_fav_name}' favorilerinizden silindi.")
        else:
            await update.message.reply_text("⚠️ Silinecek favori bulunamadı. Belki daha önce silindi?")
    else:
        await update.message.reply_text("↩️ Favori silme işlemi iptal edildi.")
    
    await show_favorites_keyboard(update, context)
    return ConversationHandler.END

async def get_delete_fav_keyboard(context: ContextTypes.DEFAULT_TYPE) -> ReplyKeyboardMarkup:
    """Silme işlemi sırasında kullanılacak favori listesi klavyesini oluşturur."""
    favorites = context.user_data.get('favorites', {})
    keyboard = []
    for fav_id, fav_data in favorites.items():
        keyboard.append([KeyboardButton(f"🗑️ {fav_data['name']}")])
    keyboard.append([KeyboardButton("❌ İptal")])
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)


# Diğer Yardımcı Fonksiyonlar
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Metin mesajlarını işler: Favori seçimi veya bilinmeyen metin."""
    text = update.message.text

    favorites = context.user_data.get('favorites', {})
    selected_stop_id = None
    selected_fav_name = None

    for fav_id, fav_data in favorites.items():
        # Favori adının başındaki otobüs emojisini dikkate alarak kontrol et
        if f"🚌 {fav_data['name']}" == text or fav_data['name'] == text: 
            selected_stop_id = fav_data['stop_id']
            selected_fav_name = fav_data['name']
            break
            
    if selected_stop_id:
        logger.info(f"Kullanıcı {update.effective_user.id}, favori '{selected_fav_name}' ({selected_stop_id}) seçti.")
        processing_message = await update.message.reply_text(f"⏳ Favori '{selected_fav_name}' ({selected_stop_id}) için bilgiler alınıyor...")
        await send_bus_info_message(update.effective_chat.id, context, selected_stop_id, processing_message=processing_message)
    else:
        await update.message.reply_text("❓ Anlamadım. Kullanılabilir komutlar ve butonlar için /start yazabilirsiniz.")


async def hide_favorites_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⌨️ Favori klavyesi gizlendi.", reply_markup=ReplyKeyboardRemove())

async def get_current_reply_keyboard_markup(context: ContextTypes.DEFAULT_TYPE) -> ReplyKeyboardMarkup:
    """ Yardımcı fonksiyon: Mevcut favorilere göre klavye markup'ı oluşturur. """
    favorites = context.user_data.get('favorites', {})
    keyboard_buttons = []
    if favorites:
        row = []
        for fav_data in favorites.values():
            row.append(KeyboardButton(f"🚌 {fav_data['name']}"))
            if len(row) == 2: keyboard_buttons.append(row); row = []
        if row: keyboard_buttons.append(row)
    keyboard_buttons.append([KeyboardButton("➕ Favori Ekle")])
    keyboard_buttons.append([KeyboardButton("➖ Favori Sil")])
    return ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True, one_time_keyboard=False)

async def post_init(application: Application) -> None:
    """Bot başlatıldıktan sonra admin'e bildirim gönderir."""
    if ADMIN_CHAT_ID != 0:
        try:
            await application.bot.send_message(chat_id=ADMIN_CHAT_ID, text="🚀 Bot başarıyla başlatıldı! (Favoriler kullanıcıya özel olarak favorites.json isimli dosyaya kaydediliyor)")
            logger.info(f"Admin ({ADMIN_CHAT_ID}) botun başlatıldığına dair bilgilendirildi.")
        except Exception as e:
            logger.error(f"Admin'e başlatma mesajı gönderilirken hata oluştu: {e}")
    else:
        logger.warning("Admin Chat ID tanımlı değil, başlatma mesajı gönderilmedi.")

# Her güncelleme öncesi çalışacak ön işleme fonksiyonu
async def pre_process_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        user_id_str = str(update.effective_user.id)
        
        if 'all_users_favorites' not in context.bot_data:
            context.bot_data['all_users_favorites'] = load_all_favorites()
            logger.info(f"Tüm kullanıcı favorileri yüklendi. Toplam kullanıcı: {len(context.bot_data['all_users_favorites'])}")

        context.user_data['favorites'] = context.bot_data['all_users_favorites'].setdefault(user_id_str, {})


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("HATA: TELEGRAM_BOT_TOKEN ortam değişkeni tanımlanmamış!")
        return
    if EGO_COOKIE == "EGOWEB_Cookie=dvze3m3mdzrwf4zatodx05ic":
        logger.warning("UYARI: Varsayılan EGO_WEB_COOKIE kullanılıyor. Sorun yaşarsanız güncelleyin.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    application.add_handler(MessageHandler(filters.ALL, pre_process_update), group=-1)

    fav_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("favori", fav_start_command_entry),
            MessageHandler(filters.Regex('^➕ Favori Ekle$'), fav_start_command_entry)
        ],
        states={
            GET_FAV_STOP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, fav_received_stop_id)],
            GET_FAV_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, fav_received_name)],
        },
        fallbacks=[CommandHandler("iptal", fav_cancel)],
        name="fav_conversation_reply_v2"
    )

    delete_fav_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("sil", delete_fav_start),
            MessageHandler(filters.Regex(r'^➖ Favori Sil$'), delete_fav_start)
        ],
        states={
            SELECT_FAV_TO_DELETE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_fav_to_delete),
                CommandHandler("iptal", fav_cancel)
            ],
            CONFIRM_DELETE: [
                MessageHandler(filters.Regex(r'^(✅ Evet, Sil|❌ Hayır, İptal)$'), confirm_delete_fav),
                CommandHandler("iptal", fav_cancel)
            ],
        },
        fallbacks=[CommandHandler("iptal", fav_cancel)],
        name="delete_fav_conversation"
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command)) # Yeni eklenen satır
    application.add_handler(CommandHandler("durak", get_stop_info_command))
    application.add_handler(fav_conv_handler)
    application.add_handler(delete_fav_conv_handler)
    application.add_handler(CommandHandler("favorilerim", show_favorites_keyboard_command))
    application.add_handler(CommandHandler("gizle_favoriler", hide_favorites_keyboard))
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message))

    logger.info("Bot başlatılıyor...")
    application.run_polling()
    logger.info("Bot durduruldu.")

if __name__ == "__main__":
    main()
