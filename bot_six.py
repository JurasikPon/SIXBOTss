import telebot
from telebot import types
import json
import os
import threading
import time
from datetime import datetime, timedelta
import random

# Инициализация бота
TOKEN = '7917859781:AAHyDtavlcU2DJL1r2kAny5R2jKCKCd7ijk'
bot = telebot.TeleBot(TOKEN)

# ID группы, где засчитываются сообщения
GROUP_ID = -1002744837263  # Замените на ID вашей группы

# Файлы для хранения данных
DATA_DIR = 'D:/SIXBOT/DATA'
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
TRANSACTIONS_FILE = os.path.join(DATA_DIR, 'transactions.json')
DEPOSITS_FILE = os.path.join(DATA_DIR, 'deposits.json')
SUBSCRIPTIONS_FILE = os.path.join(DATA_DIR, 'subscriptions.json')
PRIVILEGES_FILE = os.path.join(DATA_DIR, 'privileges.json')
USER_STATES_FILE = os.path.join(DATA_DIR, 'user_states.json')

# Блокировки для потокобезопасности
file_locks = {
    USERS_FILE: threading.Lock(),
    TRANSACTIONS_FILE: threading.Lock(),
    DEPOSITS_FILE: threading.Lock(),
    SUBSCRIPTIONS_FILE: threading.Lock(),
    PRIVILEGES_FILE: threading.Lock(),
    USER_STATES_FILE: threading.Lock()
}

# Создание директории и файлов, если их нет
def init_data_storage():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    # Инициализация файлов с пустыми словарями, если их нет
    for file_path in [USERS_FILE, TRANSACTIONS_FILE, DEPOSITS_FILE, 
                     SUBSCRIPTIONS_FILE, PRIVILEGES_FILE, USER_STATES_FILE]:
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

# Функции для работы с JSON
def load_json(file_path):
    """Загрузка данных из JSON файла с блокировкой"""
    lock = file_locks.get(file_path)
    if lock:
        lock.acquire()
    
    data = {}
    try:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
        print(f"Ошибка загрузки файла {file_path}: {e}")
        # Если файл поврежден, создаем резервную копию и новый файл
        try:
            if os.path.exists(file_path):
                backup_path = f"{file_path}.backup_{int(time.time())}"
                os.rename(file_path, backup_path)
                print(f"Создана резервная копия: {backup_path}")
        except:
            pass
        
        # Создаем новый файл с пустым словарем
        data = {}
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    finally:
        if lock:
            lock.release()
    
    # Гарантируем, что возвращаем словарь
    if not isinstance(data, dict):
        print(f"Внимание: файл {file_path} содержит не словарь, возвращаем пустой словарь")
        data = {}
    
    return data

def save_json(file_path, data):
    """Сохранение данных в JSON файл с блокировкой"""
    lock = file_locks.get(file_path)
    if lock:
        lock.acquire()
    
    try:
        # Создаем временный файл для безопасной записи
        temp_file = f"{file_path}.tmp"
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Атомарно заменяем оригинальный файл
        if os.path.exists(file_path):
            os.replace(temp_file, file_path)
        else:
            os.rename(temp_file, file_path)
        
    except Exception as e:
        print(f"Ошибка сохранения файла {file_path}: {e}")
        # Пробуем записать напрямую как запасной вариант
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e2:
            print(f"Критическая ошибка сохранения файла {file_path}: {e2}")
    
    finally:
        if lock:
            lock.release()

def get_next_id(data_dict):
    """Получение следующего ID для словаря"""
    if not data_dict:
        return 1
    
    # Пробуем получить максимальный числовой ключ
    numeric_keys = []
    for k in data_dict.keys():
        try:
            numeric_keys.append(int(k))
        except ValueError:
            continue
    
    return max(numeric_keys) + 1 if numeric_keys else 1

# Функция для получения или создания пользователя
def get_or_create_user(user_id, username=None, first_name=None):
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        users[user_id_str] = {
            'username': username,
            'first_name': first_name or username or f'User_{user_id_str[-4:]}',
            'balance': 0,
            'total_earned': 0,
            'registered_date': datetime.now().isoformat(),
            'last_message_time': None,
            'daily_bonus_date': None,
            'last_group_message_time': None
        }
        save_json(USERS_FILE, users)
    
    return users[user_id_str]

# Обновление данных пользователя
def update_user(user_id, data):
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str in users:
        # Обновляем только существующие ключи или добавляем новые
        for key, value in data.items():
            users[user_id_str][key] = value
        
        save_json(USERS_FILE, users)
        return True
    return False

# Функции для работы с состоянием пользователя
def get_user_state(user_id):
    states = load_json(USER_STATES_FILE)
    user_id_str = str(user_id)
    return states.get(user_id_str, {'page': 1})

def set_user_state(user_id, state_data):
    states = load_json(USER_STATES_FILE)
    user_id_str = str(user_id)
    states[user_id_str] = state_data
    save_json(USER_STATES_FILE, states)

def update_user_state(user_id, key, value):
    state = get_user_state(user_id)
    state[key] = value
    set_user_state(user_id, state)

# Персональное Inline меню
def personal_inline_menu(user_id=None, page=1):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Определяем, какие кнопки показывать на текущей странице
    buttons_per_page = 8
    start_idx = (page - 1) * buttons_per_page
    end_idx = start_idx + buttons_per_page
    
    all_buttons = [
        ('💰 Баланс', 'menu_balance'),
        ('🎰 Орёл/Решка', 'menu_coinflip'),
        ('🏦 Банк', 'menu_bank'),
        ('🛒 Магазин', 'menu_shop'),
        ('👤 Профиль', 'menu_profile'),
        ('💸 Перевести', 'menu_transfer'),
        ('📊 Топ игроков', 'menu_top'),
        ('📈 Мои вклады', 'menu_my_deposits'),
        ('💳 Положить в банк', 'menu_deposit'),
        ('🏧 Снять с банка', 'menu_withdraw'),
        ('🎫 Купить подписку', 'menu_buy_sub'),
        ('⭐ Купить Gold', 'menu_buy_gold'),
        ('⚙️ Настройки', 'menu_settings'),
        ('❓ Помощь', 'menu_help'),
        ('📊 Статистика', 'menu_stats'),
        ('🎁 Бонус', 'menu_bonus')
    ]
    
    # Показываем кнопки для текущей страницы
    for text, callback in all_buttons[start_idx:end_idx]:
        markup.add(types.InlineKeyboardButton(text, callback_data=callback))
    
    # Добавляем кнопки навигации
    nav_buttons = []
    if page > 1:
        nav_buttons.append(types.InlineKeyboardButton('⬅️ Назад', callback_data=f'menu_page_{page-1}'))
    
    if end_idx < len(all_buttons):
        nav_buttons.append(types.InlineKeyboardButton('Вперёд ➡️', callback_data=f'menu_page_{page+1}'))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    # Добавляем кнопку перехода в группу
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    
    return markup

# Меню настроек
def settings_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('📊 Сбросить статистику', callback_data='setting_reset_stats'),
        types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'),
        types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main')
    )
    return markup

# Меню банка (Inline)
def bank_inline_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('💳 Положить в банк', callback_data='bank_deposit'),
        types.InlineKeyboardButton('🏧 Снять с банка', callback_data='bank_withdraw'),
        types.InlineKeyboardButton('📊 Мои вклады', callback_data='bank_my_deposits'),
        types.InlineKeyboardButton('📈 Проценты', callback_data='bank_interest'),
        types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'),
        types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main')
    )
    return markup

# Меню магазина (Inline)
def shop_inline_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('🎫 Подписка + (1M SCT)', callback_data='shop_subscription'),
        types.InlineKeyboardButton('⭐ Gold (1M SCT)', callback_data='shop_gold'),
        types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'),
        types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main')
    )
    return markup

# Меню перевода (Inline)
def transfer_inline_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('💸 Быстрый перевод 100 SCT', callback_data='transfer_quick_100'),
        types.InlineKeyboardButton('💰 Быстрый перевод 500 SCT', callback_data='transfer_quick_500'),
        types.InlineKeyboardButton('💎 Быстрый перевод 1000 SCT', callback_data='transfer_quick_1000'),
        types.InlineKeyboardButton('📝 Ручной ввод суммы', callback_data='transfer_custom'),
        types.InlineKeyboardButton('📋 История переводов', callback_data='transfer_history'),
        types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'),
        types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main')
    )
    return markup

# Меню пагинации для топа
def top_pagination_menu(current_page, total_pages, user_id=None):
    markup = types.InlineKeyboardMarkup()
    
    row = []
    if current_page > 1:
        row.append(types.InlineKeyboardButton('⏪ Первая', callback_data=f'top_page_1'))
        row.append(types.InlineKeyboardButton('⬅️ Назад', callback_data=f'top_page_{current_page-1}'))
    
    if row:
        markup.row(*row)
    
    row = []
    # Показываем номера страниц вокруг текущей
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, current_page + 2)
    
    for page in range(start_page, end_page + 1):
        if page == current_page:
            row.append(types.InlineKeyboardButton(f'[{page}]', callback_data=f'top_page_{page}'))
        else:
            row.append(types.InlineKeyboardButton(str(page), callback_data=f'top_page_{page}'))
    
    if row:
        markup.row(*row)
    
    row = []
    if current_page < total_pages:
        row.append(types.InlineKeyboardButton('Вперёд ➡️', callback_data=f'top_page_{current_page+1}'))
        row.append(types.InlineKeyboardButton('Последняя ⏩', callback_data=f'top_page_{total_pages}'))
    
    if row:
        markup.row(*row)
    
    # Кнопка для перехода к своему месту в топе
    if user_id:
        markup.add(types.InlineKeyboardButton('📍 Мое место в топе', callback_data=f'top_my_position_{user_id}'))
    
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    markup.add(types.InlineKeyboardButton('⬅️ Назад в меню', callback_data='menu_main'))
    
    return markup

# Функция для проверки, является ли чат личным сообщением
def is_private_chat(chat_id):
    return chat_id > 0

# Функция для проверки, является ли чат нужной группой
def is_target_group(chat_id):
    return chat_id == GROUP_ID

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Проверяем, что команда используется в ЛС
    if not is_private_chat(message.chat.id):
        bot.reply_to(message, "⚠️ Команды бота работают только в личных сообщениях!\n\n"
                            "💬 Для заработка SCT пишите сообщения в группе:\n"
                            f"👉 https://t.me/c/{str(GROUP_ID)[4:]}/")
        return
    
    user = get_or_create_user(user_id, username, first_name)
    update_user(user_id, {'first_name': first_name})
    
    # Сбрасываем состояние
    set_user_state(user_id, {'page': 1})
    
    welcome_text = (
        f"👋 Добро пожаловать, {first_name}!\n\n"
        f"💰 За каждое сообщение в группе вы получаете 1 SCT\n"
        f"💬 Группа для заработка: https://t.me/c/{str(GROUP_ID)[4:]}/\n\n"
        f"🎰 Испытайте удачу в игре 'Орёл/Решка'\n"
        f"🏦 Храните SCT в банке под 10% в неделю\n"
        f"🛒 Покупайте подписки и привилегии\n\n"
        f"📱 Выберите действие из меню ниже:"
    )
    
    # Отправляем персональное меню
    bot.send_message(message.chat.id, welcome_text, 
                   reply_markup=personal_inline_menu(user_id, 1))

# Обработчик всех текстовых сообщений
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    current_time = datetime.now()
    
    # Проверяем, является ли сообщение командой
    if message.text.startswith('/'):
        # Обрабатываем команду /start отдельно
        if message.text == '/start':
            start_command(message)
            return
        
        # Для других команд проверяем, что они в ЛС
        if not is_private_chat(chat_id):
            if is_target_group(chat_id):
                # В целевой группе показываем информационное сообщение
                bot.reply_to(message, "⚠️ Команды бота работают только в личных сообщениях!\n\n"
                                    "💬 Напишите мне в ЛС: @sedwc_bot")
            return
        
        # Если команда в ЛС, но не /start, игнорируем
        return
    
    # Проверяем, находится ли сообщение в целевой группе
    if not is_target_group(chat_id):
        return
    
    # Проверяем, что сообщение не от бота
    if message.from_user.is_bot:
        return
    
    # Получаем пользователя
    user = get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)
    
    # Проверяем время последнего сообщения (анти-спам, например, раз в 30 секунд)
    last_group_message_time = user.get('last_group_message_time')
    if last_group_message_time:
        last_time = datetime.fromisoformat(last_group_message_time)
        time_diff = (current_time - last_time).total_seconds()
        
        # Минимальный интервал между начислениями (30 секунд)
        if time_diff < 30:
            return
    
    # Начисляем 1 SCT за сообщение в группе
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str in users:
        users[user_id_str]['balance'] = users[user_id_str].get('balance', 0) + 1
        users[user_id_str]['total_earned'] = users[user_id_str].get('total_earned', 0) + 1
        users[user_id_str]['last_message_time'] = current_time.isoformat()
        users[user_id_str]['last_group_message_time'] = current_time.isoformat()
        save_json(USERS_FILE, users)
        
        # Можно добавить тихое уведомление (опционально)
        # bot.send_message(chat_id, f"+1 SCT для @{message.from_user.username}", 
        #                 reply_to_message_id=message.message_id)

# Обработчик callback-запросов (для inline меню)
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    chat_id = call.message.chat.id
    
    # Проверяем, что callback не устарел
    try:
        # Проверяем, что сообщение не слишком старое (30 секунд для callback)
        message_time = call.message.date
        current_time = time.time()
        if current_time - message_time > 30:
            bot.answer_callback_query(call.id, "⏳ Время действия кнопки истекло. Используйте /start для нового меню.")
            return
    except:
        pass
    
    # Проверяем, что callback пришел из ЛС (команды работают только в ЛС)
    if not is_private_chat(chat_id):
        bot.answer_callback_query(call.id, "⚠️ Команды бота работают только в личных сообщениях!")
        return
    
    # Получаем состояние пользователя
    state = get_user_state(user_id)
    current_page = state.get('page', 1)
    
    # Обработка меню навигации
    if call.data.startswith('menu_page_'):
        page = int(call.data.split('_')[2])
        update_user_state(user_id, 'page', page)
        
        try:
            bot.edit_message_text("📱 Ваше персональное меню:", 
                                chat_id, message_id,
                                reply_markup=personal_inline_menu(user_id, page))
        except Exception as e:
            # Если сообщение не может быть отредактировано, отправляем новое
            bot.send_message(chat_id, "📱 Ваше персональное меню:", 
                           reply_markup=personal_inline_menu(user_id, page))
    
    # Обработка основных кнопок меню
    elif call.data == 'menu_main':
        update_user_state(user_id, 'page', 1)
        try:
            bot.edit_message_text("📱 Главное меню:", 
                                chat_id, message_id,
                                reply_markup=personal_inline_menu(user_id, 1))
        except:
            bot.send_message(chat_id, "📱 Главное меню:", 
                           reply_markup=personal_inline_menu(user_id, 1))
    
    elif call.data == 'menu_balance':
        show_balance_callback(call)
    
    elif call.data == 'menu_coinflip':
        start_coin_flip_callback(call)
    
    elif call.data == 'menu_bank':
        try:
            bot.edit_message_text("🏦 Банковские операции:", 
                                chat_id, message_id,
                                reply_markup=bank_inline_menu())
        except:
            bot.send_message(chat_id, "🏦 Банковские операции:", 
                           reply_markup=bank_inline_menu())
    
    elif call.data == 'menu_shop':
        try:
            bot.edit_message_text("🛒 Магазин SCT:", 
                                chat_id, message_id,
                                reply_markup=shop_inline_menu())
        except:
            bot.send_message(chat_id, "🛒 Магазин SCT:", 
                           reply_markup=shop_inline_menu())
    
    elif call.data == 'menu_profile':
        show_profile_callback(call)
    
    elif call.data == 'menu_transfer':
        try:
            bot.edit_message_text("💸 Перевод SCT:", 
                                chat_id, message_id,
                                reply_markup=transfer_inline_menu())
        except:
            bot.send_message(chat_id, "💸 Перевод SCT:", 
                           reply_markup=transfer_inline_menu())
    
    elif call.data == 'menu_top':
        show_top_callback(call)
    
    elif call.data == 'menu_my_deposits':
        show_my_deposits_callback(call)
    
    elif call.data == 'menu_deposit':
        deposit_to_bank_callback(call)
    
    elif call.data == 'menu_withdraw':
        withdraw_from_bank_callback(call)
    
    elif call.data == 'menu_buy_sub':
        buy_subscription_callback(call)
    
    elif call.data == 'menu_buy_gold':
        buy_gold_privilege_callback(call)
    
    elif call.data == 'menu_settings':
        try:
            bot.edit_message_text("⚙️ Настройки:", 
                                chat_id, message_id,
                                reply_markup=settings_menu())
        except:
            bot.send_message(chat_id, "⚙️ Настройки:", 
                           reply_markup=settings_menu())
    
    elif call.data == 'menu_help':
        show_help_callback(call)
    
    elif call.data == 'menu_stats':
        show_stats_callback(call)
    
    elif call.data == 'menu_bonus':
        give_daily_bonus(call)
    
    # Обработка настроек
    elif call.data == 'setting_reset_stats':
        reset_stats_confirmation(call)
    
    # Обработка банковских операций
    elif call.data == 'bank_deposit':
        deposit_to_bank_callback(call)
    
    elif call.data == 'bank_withdraw':
        withdraw_from_bank_callback(call)
    
    elif call.data == 'bank_my_deposits':
        show_my_deposits_callback(call)
    
    elif call.data == 'bank_interest':
        show_interest_info_callback(call)
    
    # Обработка магазина
    elif call.data == 'shop_subscription':
        buy_subscription_callback(call)
    
    elif call.data == 'shop_gold':
        buy_gold_privilege_callback(call)
    
    # Обработка переводов
    elif call.data.startswith('transfer_quick_'):
        amount = int(call.data.split('_')[2])
        quick_transfer(call, amount)
    
    elif call.data == 'transfer_custom':
        start_custom_transfer(call)
    
    elif call.data == 'transfer_history':
        show_transfer_history(call)
    
    # Обработка топа
    elif call.data.startswith('top_page_'):
        page = int(call.data.split('_')[2])
        show_top_page(call, page)
    
    elif call.data.startswith('top_my_position_'):
        user_id_for_position = int(call.data.split('_')[3])
        show_user_position(call, user_id_for_position)
    
    # Обработка игры "Орёл/Решка"
    elif call.data.startswith('flip_'):
        handle_coin_flip(call)
    
    # Подтверждение сброса статистики
    elif call.data == 'reset_stats_confirm':
        reset_user_stats(call)
    
    elif call.data == 'reset_stats_cancel':
        bot.answer_callback_query(call.id, "❌ Сброс статистики отменен")
        try:
            bot.edit_message_text("⚙️ Настройки:", 
                                chat_id, message_id,
                                reply_markup=settings_menu())
        except:
            bot.send_message(chat_id, "⚙️ Настройки:", 
                           reply_markup=settings_menu())
    
    # Подтверждение покупок
    elif call.data == 'confirm_buy_sub':
        confirm_buy_subscription(call)
    
    elif call.data == 'confirm_buy_gold':
        confirm_buy_gold(call)
    
    # Отвечаем на callback, чтобы убрать часики
    bot.answer_callback_query(call.id)

# Функции для работы с балансом
def show_balance_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str in users:
        balance = users[user_id_str].get('balance', 0)
        total_earned = users[user_id_str].get('total_earned', 0)
        
        # Получаем сумму в банке
        deposits = load_json(DEPOSITS_FILE)
        bank_amount = 0
        active_deposits = 0
        
        for dep_id, deposit in deposits.items():
            if (deposit.get('user_id') == user_id and 
                deposit.get('is_active', True)):
                bank_amount += deposit.get('amount', 0)
                active_deposits += 1
        
        # Получаем статистику по сообщениям в группе
        last_group_msg = users[user_id_str].get('last_group_message_time')
        group_activity = ""
        if last_group_msg:
            last_time = datetime.fromisoformat(last_group_msg)
            days_ago = (datetime.now() - last_time).days
            if days_ago == 0:
                group_activity = "Сегодня"
            elif days_ago == 1:
                group_activity = "Вчера"
            else:
                group_activity = f"{days_ago} дней назад"
        
        response = (
            f"💰 Ваш баланс: {balance:,} SCT\n"
            f"🏦 В банке: {bank_amount:,} SCT ({active_deposits}/5 вкладов)\n"
            f"📊 Всего заработано: {total_earned:,} SCT\n\n"
            f"💬 Активность в группе: {group_activity}\n"
            f"📈 Сообщений в группе: {total_earned:,}\n\n"
            f"💡 Подсказка: Пишите сообщения в группе, чтобы зарабатывать SCT!\n"
            f"👉 https://t.me/c/{str(GROUP_ID)[4:]}/"
        )
    else:
        response = f"❌ Ошибка получения баланса\n\n💬 Присоединяйтесь к группе: https://t.me/c/{str(GROUP_ID)[4:]}/"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    markup.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main'))
    
    try:
        bot.edit_message_text(response, chat_id, message_id,
                            reply_markup=markup)
    except:
        bot.send_message(chat_id, response, reply_markup=markup)

# Игра "Орёл/Решка"
def start_coin_flip_callback(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🦅 Орёл", callback_data="flip_eagle"),
        types.InlineKeyboardButton("🪙 Решка", callback_data="flip_tails"),
        types.InlineKeyboardButton("🎲 Случайно", callback_data="flip_random")
    )
    markup.add(types.InlineKeyboardButton("💬 Перейти в группу", url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    
    try:
        bot.edit_message_text("🎰 Выберите сторону монеты:", 
                            chat_id, message_id,
                            reply_markup=markup)
    except:
        bot.send_message(chat_id, "🎰 Выберите сторону монеты:", 
                        reply_markup=markup)

def handle_coin_flip(call):
    user_id = call.from_user.id
    choice = call.data.split('_')[1]
    
    # Проверяем баланс
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        try:
            bot.answer_callback_query(call.id, "❌ Пользователь не найден!")
        except:
            pass
        return
    
    balance = users[user_id_str].get('balance', 0)
    
    if balance < 1:
        try:
            bot.answer_callback_query(call.id, f"❌ Недостаточно SCT для игры!\n\n💬 Зарабатывайте SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
        except:
            # Если callback устарел, просто отправляем сообщение
            bot.send_message(call.message.chat.id, f"❌ Недостаточно SCT для игры!\n\n💬 Зарабатывайте SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
        return
    
    # Вычитаем 1 SCT за игру
    users[user_id_str]['balance'] = balance - 1
    
    # Определяем результат
    result = random.choice(['eagle', 'tails'])
    result_text = "🦅 Орёл" if result == 'eagle' else "🪙 Решка"
    
    # Определяем выигрыш
    win_amount = 0
    if choice == 'random' or choice == result:
        win_amount = 2  # Выигрыш 2 SCT
        users[user_id_str]['balance'] += win_amount
        win_text = f"🎉 Поздравляем! Вы выиграли {win_amount} SCT!"
    else:
        win_text = "😢 К сожалению, вы проиграли"
    
    save_json(USERS_FILE, users)
    
    # Добавляем транзакцию
    transactions = load_json(TRANSACTIONS_FILE)
    trans_id = get_next_id(transactions)
    transactions[str(trans_id)] = {
        'from_user_id': user_id,
        'to_user_id': 0 if choice == 'random' or choice == result else -1,
        'amount': -1 if win_amount == 0 else win_amount - 1,
        'type': 'coin_flip',
        'timestamp': datetime.now().isoformat(),
        'choice': choice,
        'result': result
    }
    save_json(TRANSACTIONS_FILE, transactions)
    
    # Создаем кнопку для новой игры
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎰 Играть снова", callback_data="menu_coinflip"))
    markup.add(types.InlineKeyboardButton("💬 Заработать SCT", url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    markup.add(types.InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_main"))
    
    # Обновляем сообщение
    response = (
        f"🎰 Результат: {result_text}\n"
        f"{win_text}\n\n"
        f"💎 Ставка: 1 SCT\n"
        f"🏆 Выигрыш: {win_amount} SCT\n"
        f"💰 Новый баланс: {users[user_id_str]['balance']:,} SCT\n\n"
        f"💬 Зарабатывайте больше SCT в группе!\n"
        f"👉 https://t.me/c/{str(GROUP_ID)[4:]}/"
    )
    
    try:
        bot.edit_message_text(response, call.message.chat.id, 
                             call.message.message_id, reply_markup=markup)
    except:
        bot.send_message(call.message.chat.id, response, reply_markup=markup)

# Банковские операции
def deposit_to_bank_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Проверяем количество активных вкладов
    deposits = load_json(DEPOSITS_FILE)
    active_deposits = 0
    
    for dep_id, deposit in deposits.items():
        if (deposit.get('user_id') == user_id and 
            deposit.get('is_active', True)):
            active_deposits += 1
    
    if active_deposits >= 5:
        try:
            bot.answer_callback_query(call.id, "❌ У вас уже 5 активных вкладов. Максимум 5 слотов!")
        except:
            bot.send_message(chat_id, "❌ У вас уже 5 активных вкладов. Максимум 5 слотов!")
        return
    
    # Удаляем сообщение с меню и отправляем новое
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    msg = bot.send_message(chat_id, 
                          f"💳 У вас {active_deposits}/5 активных вкладов.\n"
                          f"💬 Зарабатывайте SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/\n\n"
                          "Введите сумму для депозита (мин. 10 SCT):")
    bot.register_next_step_handler(msg, process_deposit)

def process_deposit(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        amount = int(message.text)
        
        if amount < 10:
            bot.send_message(chat_id, "❌ Минимальная сумма депозита: 10 SCT")
            send_menu_after_action(chat_id, user_id)
            return
        
        # Проверяем баланс
        users = load_json(USERS_FILE)
        user_id_str = str(user_id)
        
        if user_id_str not in users:
            bot.send_message(chat_id, "❌ Пользователь не найден!")
            send_menu_after_action(chat_id, user_id)
            return
        
        balance = users[user_id_str].get('balance', 0)
        
        if balance < amount:
            bot.send_message(chat_id, 
                           f"❌ Недостаточно SCT на балансе!\n\n"
                           f"💬 Зарабатывайте SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
            send_menu_after_action(chat_id, user_id)
            return
        
        # Проверяем количество активных вкладов
        deposits = load_json(DEPOSITS_FILE)
        active_deposits = 0
        
        for dep_id, deposit in deposits.items():
            if (deposit.get('user_id') == user_id and 
                deposit.get('is_active', True)):
                active_deposits += 1
        
        if active_deposits >= 5:
            bot.send_message(chat_id, "❌ У вас уже максимальное количество вкладов (5)!")
            send_menu_after_action(chat_id, user_id)
            return
        
        # Создаем депозит
        deposit_id = get_next_id(deposits)
        deposits[str(deposit_id)] = {
            'user_id': user_id,
            'amount': amount,
            'start_date': datetime.now().isoformat(),
            'end_date': (datetime.now() + timedelta(weeks=52)).isoformat(),
            'weekly_interest': 10,
            'is_active': True,
            'total_interest': 0
        }
        
        # Списываем с баланса
        users[user_id_str]['balance'] = balance - amount
        save_json(USERS_FILE, users)
        save_json(DEPOSITS_FILE, deposits)
        
        # Добавляем транзакцию
        transactions = load_json(TRANSACTIONS_FILE)
        trans_id = get_next_id(transactions)
        transactions[str(trans_id)] = {
            'from_user_id': user_id,
            'to_user_id': 'bank',
            'amount': amount,
            'type': 'deposit',
            'timestamp': datetime.now().isoformat(),
            'deposit_id': deposit_id
        }
        save_json(TRANSACTIONS_FILE, transactions)
        
        bot.send_message(chat_id, 
                        f"✅ Депозит #{deposit_id} на {amount:,} SCT успешно создан!\n"
                        f"📅 Проценты (10%) начисляются каждую неделю\n"
                        f"⏳ Срок: 1 год\n"
                        f"📊 Активных вкладов: {active_deposits + 1}/5\n\n"
                        f"💬 Продолжайте зарабатывать SCT в группе!\n"
                        f"👉 https://t.me/c/{str(GROUP_ID)[4:]}/")
    
    except ValueError:
        bot.send_message(chat_id, "❌ Пожалуйста, введите число!")
    
    send_menu_after_action(chat_id, user_id)

def withdraw_from_bank_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Удаляем сообщение с меню
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    msg = bot.send_message(chat_id, 
                          "🏧 Введите ID депозита для снятия:\n"
                          "(ID можно узнать в 'Мои вклады')\n\n"
                          f"💬 Группа для заработка: https://t.me/c/{str(GROUP_ID)[4:]}/")
    bot.register_next_step_handler(msg, process_withdrawal)

def process_withdrawal(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        deposit_id = int(message.text)
        
        deposits = load_json(DEPOSITS_FILE)
        deposit_id_str = str(deposit_id)
        
        if (deposit_id_str not in deposits or 
            deposits[deposit_id_str].get('user_id') != user_id or
            not deposits[deposit_id_str].get('is_active', True)):
            bot.send_message(chat_id, "❌ Депозит не найден или уже закрыт!")
            send_menu_after_action(chat_id, user_id)
            return
        
        deposit = deposits[deposit_id_str]
        amount = deposit.get('amount', 0)
        start_date = datetime.fromisoformat(deposit.get('start_date'))
        interest_rate = deposit.get('weekly_interest', 10)
        
        # Рассчитываем проценты
        weeks_passed = (datetime.now() - start_date).days // 7
        interest = (amount * interest_rate * weeks_passed) // 100
        
        total_amount = amount + interest
        
        # Возвращаем средства
        users = load_json(USERS_FILE)
        user_id_str = str(user_id)
        
        if user_id_str in users:
            users[user_id_str]['balance'] = users[user_id_str].get('balance', 0) + total_amount
            save_json(USERS_FILE, users)
        
        # Закрываем депозит
        deposits[deposit_id_str]['is_active'] = False
        deposits[deposit_id_str]['withdraw_date'] = datetime.now().isoformat()
        deposits[deposit_id_str]['total_interest'] = interest
        save_json(DEPOSITS_FILE, deposits)
        
        # Добавляем транзакцию
        transactions = load_json(TRANSACTIONS_FILE)
        trans_id = get_next_id(transactions)
        transactions[str(trans_id)] = {
            'from_user_id': 'bank',
            'to_user_id': user_id,
            'amount': total_amount,
            'type': 'withdrawal',
            'timestamp': datetime.now().isoformat(),
            'deposit_id': deposit_id,
            'principal': amount,
            'interest': interest
        }
        save_json(TRANSACTIONS_FILE, transactions)
        
        bot.send_message(chat_id, 
                        f"✅ Депозит #{deposit_id} закрыт!\n"
                        f"💵 Возвращено: {amount:,} SCT\n"
                        f"📈 Проценты: {interest:,} SCT\n"
                        f"💰 Итого: {total_amount:,} SCT\n\n"
                        f"💬 Продолжайте зарабатывать в группе!\n"
                        f"👉 https://t.me/c/{str(GROUP_ID)[4:]}/")
    
    except ValueError:
        bot.send_message(chat_id, "❌ Пожалуйста, введите число!")
    
    send_menu_after_action(chat_id, user_id)

def show_my_deposits_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    deposits = load_json(DEPOSITS_FILE)
    
    user_deposits = []
    for dep_id, deposit in deposits.items():
        if (deposit.get('user_id') == user_id and 
            deposit.get('is_active', True)):
            user_deposits.append((dep_id, deposit))
    
    if not user_deposits:
        response = f"📭 У вас нет активных вкладов\n\n💬 Зарабатывайте SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('💳 Создать вклад', callback_data='bank_deposit'))
        markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
        markup.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main'))
    else:
        response = "📊 Ваши активные вклады:\n\n"
        
        for dep_id, deposit in user_deposits:
            amount = deposit.get('amount', 0)
            start_date = datetime.fromisoformat(deposit.get('start_date'))
            interest_rate = deposit.get('weekly_interest', 10)
            
            # Рассчитываем проценты
            weeks_passed = (datetime.now() - start_date).days // 7
            earned_interest = (amount * interest_rate * weeks_passed) // 100
            
            response += (
                f"🏦 Депозит #{dep_id}\n"
                f"💵 Сумма: {amount:,} SCT\n"
                f"📅 Открыт: {start_date.strftime('%d.%m.%Y')}\n"
                f"📈 Проценты: {interest_rate}% в неделю\n"
                f"💰 Накоплено: {earned_interest:,} SCT\n"
                f"🔢 Всего: {amount + earned_interest:,} SCT\n\n"
            )
        
        response += f"📈 Всего активных вкладов: {len(user_deposits)}/5\n\n💬 Продолжайте зарабатывать в группе!"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('💳 Новый вклад', callback_data='bank_deposit'))
        markup.add(types.InlineKeyboardButton('🏧 Снять средства', callback_data='bank_withdraw'))
        markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
        markup.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main'))
    
    try:
        bot.edit_message_text(response, chat_id, message_id, reply_markup=markup)
    except:
        bot.send_message(chat_id, response, reply_markup=markup)

def show_interest_info_callback(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    info = (
        "📈 Информация о банковских процентах:\n\n"
        "🏦 Ставка: 10% в неделю\n"
        "📅 Начисление: каждую неделю\n"
        "🎯 Максимум вкладов: 5 слотов\n"
        "💵 Минимальный депозит: 10 SCT\n"
        "⏳ Срок вклада: 1 год\n\n"
        "📊 Пример:\n"
        "• Депозит 100 SCT\n"
        "• За неделю: +10 SCT\n"
        "• За месяц: ~40 SCT\n"
        "• За год: ~520 SCT\n\n"
        "💡 Выгоднее хранить SCT в банке!\n\n"
        f"💬 Зарабатывайте SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('💳 Создать вклад', callback_data='bank_deposit'))
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    markup.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main'))
    
    try:
        bot.edit_message_text(info, chat_id, message_id, reply_markup=markup)
    except:
        bot.send_message(chat_id, info, reply_markup=markup)

# Вспомогательная функция для отправки меню после действий
def send_menu_after_action(chat_id, user_id):
    time.sleep(1)  # Небольшая задержка
    bot.send_message(chat_id, "📱 Ваше персональное меню:", 
                   reply_markup=personal_inline_menu(user_id, 1))

# Магазин
def buy_subscription_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    price = 1000000  # 1 млн SCT
    
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        try:
            bot.answer_callback_query(call.id, "❌ Пользователь не найден!")
        except:
            bot.send_message(chat_id, "❌ Пользователь не найден!")
        return
    
    balance = users[user_id_str].get('balance', 0)
    
    if balance < price:
        try:
            bot.answer_callback_query(call.id, 
                                     f"❌ Недостаточно SCT!\n💰 Нужно: {price:,} SCT\n💳 У вас: {balance:,} SCT\n\n💬 Зарабатывайте в группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
        except:
            bot.send_message(chat_id, f"❌ Недостаточно SCT!\n💰 Нужно: {price:,} SCT\n💳 У вас: {balance:,} SCT\n\n💬 Зарабатывайте в группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
        return
    
    # Создаем кнопку подтверждения
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✅ Да, купить', callback_data='confirm_buy_sub'),
        types.InlineKeyboardButton('❌ Нет, отмена', callback_data='menu_shop')
    )
    
    try:
        bot.edit_message_text(
            f"🎫 Подписка +\n💰 Цена: {price:,} SCT\n\n"
            f"Ваш баланс: {balance:,} SCT\n"
            f"После покупки: {balance - price:,} SCT\n\n"
            "Подтвердите покупку:",
            chat_id, message_id,
            reply_markup=markup
        )
    except:
        bot.send_message(chat_id,
            f"🎫 Подписка +\n💰 Цена: {price:,} SCT\n\n"
            f"Ваш баланс: {balance:,} SCT\n"
            f"После покупки: {balance - price:,} SCT\n\n"
            "Подтвердите покупку:",
            reply_markup=markup
        )

def confirm_buy_subscription(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    price = 1000000
    
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    balance = users[user_id_str].get('balance', 0)
    
    # Покупка подписки
    subscriptions = load_json(SUBSCRIPTIONS_FILE)
    sub_id = get_next_id(subscriptions)
    subscriptions[str(sub_id)] = {
        'user_id': user_id,
        'type': 'Подписка +',
        'price': price,
        'purchase_date': datetime.now().isoformat()
    }
    save_json(SUBSCRIPTIONS_FILE, subscriptions)
    
    # Списываем средства
    users[user_id_str]['balance'] = balance - price
    save_json(USERS_FILE, users)
    
    # Добавляем транзакцию
    transactions = load_json(TRANSACTIONS_FILE)
    trans_id = get_next_id(transactions)
    transactions[str(trans_id)] = {
        'from_user_id': user_id,
        'to_user_id': 'shop',
        'amount': price,
        'type': 'subscription_purchase',
        'timestamp': datetime.now().isoformat(),
        'item': 'Подписка +'
    }
    save_json(TRANSACTIONS_FILE, transactions)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('🛒 В магазин', callback_data='menu_shop'))
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    markup.add(types.InlineKeyboardButton('👤 В профиль', callback_data='menu_profile'))
    
    try:
        bot.edit_message_text(
            f"🎉 Поздравляем с покупкой 'Подписка +'!\n"
            f"💰 Списано: {price:,} SCT\n"
            f"✅ Теперь она отображается в вашем профиле\n\n"
            f"💬 Продолжайте зарабатывать в группе!",
            chat_id, message_id,
            reply_markup=markup
        )
    except:
        bot.send_message(chat_id,
            f"🎉 Поздравляем с покупкой 'Подписка +'!\n"
            f"💰 Списано: {price:,} SCT\n"
            f"✅ Теперь она отображается в вашем профиле\n\n"
            f"💬 Продолжайте зарабатывать в группе!",
            reply_markup=markup
        )

def buy_gold_privilege_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    price = 1000000  # 1 млн SCT
    
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        try:
            bot.answer_callback_query(call.id, "❌ Пользователь не найден!")
        except:
            bot.send_message(chat_id, "❌ Пользователь не найден!")
        return
    
    balance = users[user_id_str].get('balance', 0)
    
    if balance < price:
        try:
            bot.answer_callback_query(call.id, 
                                     f"❌ Недостаточно SCT!\n💰 Нужно: {price:,} SCT\n💳 У вас: {balance:,} SCT\n\n💬 Зарабатывайте в группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
        except:
            bot.send_message(chat_id, f"❌ Недостаточно SCT!\n💰 Нужно: {price:,} SCT\n💳 У вас: {balance:,} SCT\n\n💬 Зарабатывайте в группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
        return
    
    # Создаем кнопку подтверждения
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✅ Да, купить', callback_data='confirm_buy_gold'),
        types.InlineKeyboardButton('❌ Нет, отмена', callback_data='menu_shop')
    )
    
    try:
        bot.edit_message_text(
            f"⭐ Привилегия Gold\n💰 Цена: {price:,} SCT\n\n"
            f"Ваш баланс: {balance:,} SCT\n"
            f"После покупки: {balance - price:,} SCT\n\n"
            "Подтвердите покупку:",
            chat_id, message_id,
            reply_markup=markup
        )
    except:
        bot.send_message(chat_id,
            f"⭐ Привилегия Gold\n💰 Цена: {price:,} SCT\n\n"
            f"Ваш баланс: {balance:,} SCT\n"
            f"После покупки: {balance - price:,} SCT\n\n"
            "Подтвердите покупку:",
            reply_markup=markup
        )

def confirm_buy_gold(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    price = 1000000
    
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    balance = users[user_id_str].get('balance', 0)
    
    # Покупка привилегии
    privileges = load_json(PRIVILEGES_FILE)
    priv_id = get_next_id(privileges)
    privileges[str(priv_id)] = {
        'user_id': user_id,
        'type': 'Gold',
        'price': price,
        'purchase_date': datetime.now().isoformat()
    }
    save_json(PRIVILEGES_FILE, privileges)
    
    # Списываем средства
    users[user_id_str]['balance'] = balance - price
    save_json(USERS_FILE, users)
    
    # Добавляем транзакцию
    transactions = load_json(TRANSACTIONS_FILE)
    trans_id = get_next_id(transactions)
    transactions[str(trans_id)] = {
        'from_user_id': user_id,
        'to_user_id': 'shop',
        'amount': price,
        'type': 'privilege_purchase',
        'timestamp': datetime.now().isoformat(),
        'item': 'Gold'
    }
    save_json(TRANSACTIONS_FILE, transactions)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('🛒 В магазин', callback_data='menu_shop'))
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    markup.add(types.InlineKeyboardButton('👤 В профиль', callback_data='menu_profile'))
    
    try:
        bot.edit_message_text(
            f"🎉 Поздравляем с покупкой привилегии 'Gold'!\n"
            f"💰 Списано: {price:,} SCT\n"
            f"⭐ Теперь она отображается в вашем профиле\n\n"
            f"💬 Продолжайте зарабатывать в группе!",
            chat_id, message_id,
            reply_markup=markup
        )
    except:
        bot.send_message(chat_id,
            f"🎉 Поздравляем с покупкой привилегии 'Gold'!\n"
            f"💰 Списано: {price:,} SCT\n"
            f"⭐ Теперь она отображается в вашем профиле\n\n"
            f"💬 Продолжайте зарабатывать в группе!",
            reply_markup=markup
        )

# Профиль
def show_profile_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        try:
            bot.answer_callback_query(call.id, "❌ Пользователь не найден!")
        except:
            bot.send_message(chat_id, "❌ Пользователь не найден!")
        return
    
    user_info = users[user_id_str]
    
    # Подписки
    subscriptions = load_json(SUBSCRIPTIONS_FILE)
    user_subs = []
    for sub_id, sub in subscriptions.items():
        if sub.get('user_id') == user_id:
            user_subs.append(sub)
    
    sub_count = len(user_subs)
    sub_types = ", ".join([sub.get('type', 'Неизвестно') for sub in user_subs]) if user_subs else "Нет"
    
    # Привилегии
    privileges = load_json(PRIVILEGES_FILE)
    user_privs = []
    for priv_id, priv in privileges.items():
        if priv.get('user_id') == user_id:
            user_privs.append(priv)
    
    priv_count = len(user_privs)
    priv_types = ", ".join([priv.get('type', 'Неизвестно') for priv in user_privs]) if user_privs else "Нет"
    
    # Банковские вклады
    deposits = load_json(DEPOSITS_FILE)
    user_deps = []
    total_dep_amount = 0
    
    for dep_id, deposit in deposits.items():
        if (deposit.get('user_id') == user_id and 
            deposit.get('is_active', True)):
            user_deps.append(deposit)
            total_dep_amount += deposit.get('amount', 0)
    
    dep_count = len(user_deps)
    
    # Транзакции
    transactions = load_json(TRANSACTIONS_FILE)
    trans_count = 0
    for trans_id, trans in transactions.items():
        if trans.get('from_user_id') == user_id or trans.get('to_user_id') == user_id:
            trans_count += 1
    
    registered_date = datetime.fromisoformat(user_info.get('registered_date', datetime.now().isoformat()))
    days_registered = (datetime.now() - registered_date).days
    
    # Активность в группе
    last_group_msg = user_info.get('last_group_message_time')
    group_activity = "Никогда"
    if last_group_msg:
        last_time = datetime.fromisoformat(last_group_msg)
        days_ago = (datetime.now() - last_time).days
        if days_ago == 0:
            group_activity = "Сегодня"
        elif days_ago == 1:
            group_activity = "Вчера"
        else:
            group_activity = f"{days_ago} дней назад"
    
    profile_text = (
        f"👤 Профиль: {user_info.get('first_name', 'Пользователь')}\n"
        f"🆔 ID: {user_id}\n"
        f"📅 Зарегистрирован: {days_registered} дней назад\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Баланс: {user_info.get('balance', 0):,} SCT\n"
        f"📊 Всего заработано: {user_info.get('total_earned', 0):,} SCT\n"
        f"🏦 В банке: {total_dep_amount:,} SCT ({dep_count}/5 вкладов)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 Активность в группе: {group_activity}\n"
        f"📈 Сообщений в группе: {user_info.get('total_earned', 0):,}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 Подписок: {sub_count}\n"
        f"📋 Типы: {sub_types}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ Привилегий: {priv_count}\n"
        f"📋 Типы: {priv_types}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Статистика:\n"
        f"• Переводов: {trans_count}\n"
        f"• Вкладов: {dep_count}\n"
        f"• Игр: {sum(1 for t in transactions.values() if t.get('type') == 'coin_flip' and t.get('from_user_id') == user_id)}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 Уровень: {'⭐' * min(priv_count, 5)}\n\n"
        f"💬 Группа для заработка: https://t.me/c/{str(GROUP_ID)[4:]}/"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('💰 Баланс', callback_data='menu_balance'),
        types.InlineKeyboardButton('📊 Статистика', callback_data='menu_stats'),
        types.InlineKeyboardButton('🏦 Мои вклады', callback_data='menu_my_deposits'),
        types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'),
        types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main')
    )
    
    try:
        bot.edit_message_text(profile_text, chat_id, message_id,
                            reply_markup=markup)
    except:
        bot.send_message(chat_id, profile_text, reply_markup=markup)

# Топ игроков с пагинацией
def show_top_callback(call):
    show_top_page(call, 1)

def show_top_page(call, page=1):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    users = load_json(USERS_FILE)
    
    # Создаем список пользователей для сортировки
    user_list = []
    for user_id_str, user_data in users.items():
        if user_data.get('balance', 0) > 0 or user_data.get('total_earned', 0) > 0:
            user_list.append({
                'id': int(user_id_str),
                'username': user_data.get('first_name', f'Аноним_{user_id_str[-4:]}'),
                'balance': user_data.get('balance', 0),
                'total_earned': user_data.get('total_earned', 0),
                'deposits': 0
            })
    
    # Добавляем информацию о вкладах
    deposits = load_json(DEPOSITS_FILE)
    for user in user_list:
        total_deposits = 0
        for dep_id, deposit in deposits.items():
            if deposit.get('user_id') == user['id'] and deposit.get('is_active', True):
                total_deposits += deposit.get('amount', 0)
        user['total_wealth'] = user['balance'] + total_deposits
    
    # Сортируем по общему богатству (баланс + вклады)
    user_list.sort(key=lambda x: x['total_wealth'], reverse=True)
    
    # Пагинация
    items_per_page = 10
    total_users = len(user_list)
    total_pages = max(1, (total_users + items_per_page - 1) // items_per_page)
    
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    
    # Создаем текст для текущей страницы
    response = f"🏆 Топ игроков (страница {page}/{total_pages}):\n\n"
    
    for i, user in enumerate(user_list[start_idx:end_idx], start=start_idx + 1):
        username = user['username']
        balance = user['balance']
        total_wealth = user['total_wealth']
        
        medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"{i}."))
        response += f"{medal} {username}\n💰 {balance:,} SCT | 💎 {total_wealth:,} SCT\n\n"
    
    response += f"👥 Всего игроков: {total_users}\n\n"
    response += f"💬 Зарабатывайте SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/"
    
    # Создаем меню пагинации
    markup = top_pagination_menu(page, total_pages, user_id=user_id)
    
    try:
        bot.edit_message_text(response, chat_id, message_id,
                            reply_markup=markup)
    except:
        bot.send_message(chat_id, response, reply_markup=markup)

def show_user_position(call, user_id_for_position):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    users = load_json(USERS_FILE)
    user_id_str = str(user_id_for_position)
    
    if user_id_str not in users:
        try:
            bot.answer_callback_query(call.id, "❌ Пользователь не найден!")
        except:
            bot.send_message(chat_id, "❌ Пользователь не найден!")
        return
    
    # Получаем все пользователей и сортируем
    user_list = []
    for uid_str, user_data in users.items():
        if user_data.get('balance', 0) > 0 or user_data.get('total_earned', 0) > 0:
            # Рассчитываем общее богатство
            total_deposits = 0
            deposits = load_json(DEPOSITS_FILE)
            for dep_id, deposit in deposits.items():
                if deposit.get('user_id') == int(uid_str) and deposit.get('is_active', True):
                    total_deposits += deposit.get('amount', 0)
            
            user_list.append({
                'id': int(uid_str),
                'total_wealth': user_data.get('balance', 0) + total_deposits
            })
    
    # Сортируем
    user_list.sort(key=lambda x: x['total_wealth'], reverse=True)
    
    # Находим позицию пользователя
    position = None
    for idx, user in enumerate(user_list, 1):
        if user['id'] == user_id_for_position:
            position = idx
            break
    
    if position is None:
        response = f"📊 Вы еще не в рейтинге!\n\n💬 Присоединяйтесь к группе: https://t.me/c/{str(GROUP_ID)[4:]}/"
    else:
        user_data = users[user_id_str]
        total_deposits = 0
        deposits = load_json(DEPOSITS_FILE)
        for dep_id, deposit in deposits.items():
            if deposit.get('user_id') == user_id_for_position and deposit.get('is_active', True):
                total_deposits += deposit.get('amount', 0)
        
        total_wealth = user_data.get('balance', 0) + total_deposits
        
        response = (
            f"📍 Ваше место в рейтинге: #{position}\n\n"
            f"💰 Баланс: {user_data.get('balance', 0):,} SCT\n"
            f"🏦 В банке: {total_deposits:,} SCT\n"
            f"💎 Общее богатство: {total_wealth:,} SCT\n\n"
        )
        
        # Показываем ближайших конкурентов
        if position > 1:
            prev_user = user_list[position-2]
            response += f"⬆️ Выше на #{position-1}: +{prev_user['total_wealth'] - total_wealth:,} SCT\n"
        
        if position < len(user_list):
            next_user = user_list[position]
            response += f"⬇️ Ниже на #{position+1}: -{total_wealth - next_user['total_wealth']:,} SCT\n"
        
        response += f"\n💬 Зарабатывайте больше SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📊 Весь топ', callback_data='menu_top'))
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    markup.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main'))
    
    try:
        bot.edit_message_text(response, chat_id, message_id, reply_markup=markup)
    except:
        bot.send_message(chat_id, response, reply_markup=markup)

# Переводы
def quick_transfer(call, amount):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        try:
            bot.answer_callback_query(call.id, "❌ Пользователь не найден!")
        except:
            bot.send_message(chat_id, "❌ Пользователь не найден!")
        return
    
    balance = users[user_id_str].get('balance', 0)
    
    if balance < amount:
        try:
            bot.answer_callback_query(call.id, f"❌ Недостаточно SCT! У вас: {balance:,} SCT\n\n💬 Зарабатывайте в группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
        except:
            bot.send_message(chat_id, f"❌ Недостаточно SCT! У вас: {balance:,} SCT\n\n💬 Зарабатывайте в группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
        return
    
    # Удаляем сообщение с меню
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    msg = bot.send_message(chat_id, 
                          f"💸 Быстрый перевод {amount:,} SCT\n"
                          f"💬 Зарабатывайте SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/\n\n"
                          "Введите ID пользователя для перевода:")
    bot.register_next_step_handler(msg, lambda m: process_quick_transfer(m, amount))

def process_quick_transfer(message, amount):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        recipient_id = int(message.text)
        
        if recipient_id == user_id:
            bot.send_message(chat_id, "❌ Нельзя переводить самому себе!")
            send_menu_after_action(chat_id, user_id)
            return
        
        users = load_json(USERS_FILE)
        user_id_str = str(user_id)
        recipient_id_str = str(recipient_id)
        
        # Проверяем баланс отправителя
        if user_id_str not in users:
            bot.send_message(chat_id, "❌ Отправитель не найден!")
            send_menu_after_action(chat_id, user_id)
            return
        
        sender_balance = users[user_id_str].get('balance', 0)
        
        if sender_balance < amount:
            bot.send_message(chat_id, 
                           f"❌ Недостаточно SCT для перевода!\n\n"
                           f"💬 Зарабатывайте SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
            send_menu_after_action(chat_id, user_id)
            return
        
        # Проверяем получателя
        if recipient_id_str not in users:
            # Создаем получателя, если его нет
            users[recipient_id_str] = {
                'username': None,
                'first_name': f'Пользователь_{recipient_id_str[-4:]}',
                'balance': 0,
                'total_earned': 0,
                'registered_date': datetime.now().isoformat(),
                'last_message_time': None
            }
        
        # Выполняем перевод
        users[user_id_str]['balance'] = sender_balance - amount
        users[recipient_id_str]['balance'] = users[recipient_id_str].get('balance', 0) + amount
        
        save_json(USERS_FILE, users)
        
        # Записываем транзакцию
        transactions = load_json(TRANSACTIONS_FILE)
        trans_id = get_next_id(transactions)
        transactions[str(trans_id)] = {
            'from_user_id': user_id,
            'to_user_id': recipient_id,
            'amount': amount,
            'type': 'transfer',
            'timestamp': datetime.now().isoformat()
        }
        save_json(TRANSACTIONS_FILE, transactions)
        
        # Уведомляем отправителя
        recipient_name = users[recipient_id_str].get('first_name', 'Аноним')
        bot.send_message(chat_id, 
                        f"✅ Перевод выполнен!\n"
                        f"👤 Кому: {recipient_name}\n"
                        f"💰 Сумма: {amount:,} SCT\n"
                        f"📊 Комиссия: 0%\n\n"
                        f"💬 Продолжайте зарабатывать в группе!\n"
                        f"👉 https://t.me/c/{str(GROUP_ID)[4:]}/")
        
        # Уведомляем получателя
        try:
            sender_name = users[user_id_str].get('first_name', 'Аноним')
            bot.send_message(recipient_id, 
                           f"🎉 Вам перевели {amount:,} SCT!\n"
                           f"👤 От: {sender_name}\n"
                           f"💳 Пополнение баланса\n\n"
                           f"💬 Присоединяйтесь к группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
        except:
            pass  # Пользователь может заблокировать бота
        
    except ValueError:
        bot.send_message(chat_id, "❌ Ошибка! Проверьте введенные данные")
    
    send_menu_after_action(chat_id, user_id)

def start_custom_transfer(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Удаляем сообщение с меню
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    msg = bot.send_message(chat_id, 
                          "💸 Введите ID пользователя и сумму перевода через пробел:\n"
                          "Пример: 123456789 100\n\n"
                          f"💬 Группа для заработка: https://t.me/c/{str(GROUP_ID)[4:]}/")
    bot.register_next_step_handler(msg, process_transfer)

def process_transfer(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(chat_id, "❌ Неверный формат! Используйте: ID СУММА")
            send_menu_after_action(chat_id, user_id)
            return
        
        recipient_id = int(parts[0])
        amount = int(parts[1])
        
        if amount < 1:
            bot.send_message(chat_id, "❌ Минимальная сумма перевода: 1 SCT")
            send_menu_after_action(chat_id, user_id)
            return
        
        if recipient_id == user_id:
            bot.send_message(chat_id, "❌ Нельзя переводить самому себе!")
            send_menu_after_action(chat_id, user_id)
            return
        
        users = load_json(USERS_FILE)
        user_id_str = str(user_id)
        recipient_id_str = str(recipient_id)
        
        # Проверяем баланс отправителя
        if user_id_str not in users:
            bot.send_message(chat_id, "❌ Отправитель не найден!")
            send_menu_after_action(chat_id, user_id)
            return
        
        sender_balance = users[user_id_str].get('balance', 0)
        
        if sender_balance < amount:
            bot.send_message(chat_id, 
                           f"❌ Недостаточно SCT для перевода!\n\n"
                           f"💬 Зарабатывайте SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
            send_menu_after_action(chat_id, user_id)
            return
        
        # Проверяем получателя
        if recipient_id_str not in users:
            # Создаем получателя, если его нет
            users[recipient_id_str] = {
                'username': None,
                'first_name': f'Пользователь_{recipient_id_str[-4:]}',
                'balance': 0,
                'total_earned': 0,
                'registered_date': datetime.now().isoformat(),
                'last_message_time': None
            }
        
        # Выполняем перевод
        users[user_id_str]['balance'] = sender_balance - amount
        users[recipient_id_str]['balance'] = users[recipient_id_str].get('balance', 0) + amount
        
        save_json(USERS_FILE, users)
        
        # Записываем транзакцию
        transactions = load_json(TRANSACTIONS_FILE)
        trans_id = get_next_id(transactions)
        transactions[str(trans_id)] = {
            'from_user_id': user_id,
            'to_user_id': recipient_id,
            'amount': amount,
            'type': 'transfer',
            'timestamp': datetime.now().isoformat()
        }
        save_json(TRANSACTIONS_FILE, transactions)
        
        # Уведомляем отправителя
        recipient_name = users[recipient_id_str].get('first_name', 'Аноним')
        bot.send_message(chat_id, 
                        f"✅ Перевод выполнен!\n"
                        f"👤 Кому: {recipient_name}\n"
                        f"💰 Сумма: {amount:,} SCT\n"
                        f"📊 Комиссия: 0%\n\n"
                        f"💬 Продолжайте зарабатывать в группе!\n"
                        f"👉 https://t.me/c/{str(GROUP_ID)[4:]}/")
        
        # Уведомляем получателя
        try:
            sender_name = users[user_id_str].get('first_name', 'Аноним')
            bot.send_message(recipient_id, 
                           f"🎉 Вам перевели {amount:,} SCT!\n"
                           f"👤 От: {sender_name}\n"
                           f"💳 Пополнение баланса\n\n"
                           f"💬 Присоединяйтесь к группе: https://t.me/c/{str(GROUP_ID)[4:]}/")
        except:
            pass  # Пользователь может заблокировать бота
        
    except ValueError:
        bot.send_message(chat_id, "❌ Ошибка! Проверьте введенные данные")
    
    send_menu_after_action(chat_id, user_id)

def show_transfer_history(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    transactions = load_json(TRANSACTIONS_FILE)
    
    user_transactions = []
    for trans_id, trans in transactions.items():
        if trans.get('from_user_id') == user_id or trans.get('to_user_id') == user_id:
            user_transactions.append((trans_id, trans))
    
    # Сортируем по времени (новые сначала)
    user_transactions.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)
    
    if not user_transactions:
        response = f"📭 У вас нет истории переводов\n\n💬 Зарабатывайте SCT в группе: https://t.me/c/{str(GROUP_ID)[4:]}/"
    else:
        response = "📋 История ваших переводов:\n\n"
        
        for trans_id, trans in user_transactions[:20]:  # Показываем последние 20
            amount = trans.get('amount', 0)
            trans_type = trans.get('type', 'unknown')
            timestamp = datetime.fromisoformat(trans.get('timestamp', datetime.now().isoformat()))
            
            if trans_type == 'transfer':
                if trans.get('from_user_id') == user_id:
                    to_user = trans.get('to_user_id')
                    response += f"➡️ Перевод {to_user}: -{amount:,} SCT\n"
                else:
                    from_user = trans.get('from_user_id')
                    response += f"⬅️ От {from_user}: +{amount:,} SCT\n"
            elif trans_type == 'deposit':
                response += f"🏦 Депозит: -{amount:,} SCT\n"
            elif trans_type == 'withdrawal':
                response += f"🏧 Снятие: +{amount:,} SCT\n"
            elif trans_type == 'coin_flip':
                if amount > 0:
                    result = trans.get('result', 'unknown')
                    response += f"🎰 Выигрыш ({result}): +{amount:,} SCT\n"
                else:
                    response += f"🎰 Проигрыш: -{abs(amount):,} SCT\n"
            
            response += f"   📅 {timestamp.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        response += f"💬 Продолжайте зарабатывать в группе: https://t.me/c/{str(GROUP_ID)[4:]}/"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('💸 Новый перевод', callback_data='menu_transfer'))
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    markup.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main'))
    
    try:
        bot.edit_message_text(response, chat_id, message_id, reply_markup=markup)
    except:
        bot.send_message(chat_id, response, reply_markup=markup)

# Настройки
def reset_stats_confirmation(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('✅ Да, сбросить', callback_data='reset_stats_confirm'),
        types.InlineKeyboardButton('❌ Нет, отмена', callback_data='reset_stats_cancel')
    )
    
    try:
        bot.edit_message_text(
            "⚠️ Внимание!\n\n"
            "Вы уверены, что хотите сбросить свою статистику?\n"
            "Это действие нельзя отменить!\n\n"
            "Будут сброшены:\n"
            "• Общее количество заработанных SCT\n"
            "• История переводов\n"
            "• Баланс останется неизменным\n\n"
            f"💬 Группа для заработка: https://t.me/c/{str(GROUP_ID)[4:]}/",
            chat_id, message_id,
            reply_markup=markup
        )
    except:
        bot.send_message(chat_id,
            "⚠️ Внимание!\n\n"
            "Вы уверены, что хотите сбросить свою статистику?\n"
            "Это действие нельзя отменить!\n\n"
            "Будут сброшены:\n"
            "• Общее количество заработанных SCT\n"
            "• История переводов\n"
            "• Баланс останется неизменным\n\n"
            f"💬 Группа для заработка: https://t.me/c/{str(GROUP_ID)[4:]}/",
            reply_markup=markup
        )

def reset_user_stats(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str in users:
        # Сохраняем текущий баланс
        current_balance = users[user_id_str].get('balance', 0)
        
        # Сбрасываем статистику
        users[user_id_str]['total_earned'] = current_balance
        users[user_id_str]['registered_date'] = datetime.now().isoformat()
        save_json(USERS_FILE, users)
        
        # Удаляем историю переводов пользователя
        transactions = load_json(TRANSACTIONS_FILE)
        transactions_to_delete = []
        for trans_id, trans in transactions.items():
            if trans.get('from_user_id') == user_id or trans.get('to_user_id') == user_id:
                transactions_to_delete.append(trans_id)
        
        for trans_id in transactions_to_delete:
            del transactions[trans_id]
        
        save_json(TRANSACTIONS_FILE, transactions)
        
        try:
            bot.answer_callback_query(call.id, "✅ Статистика успешно сброшена!")
        except:
            pass
        
        # Возвращаем в настройки
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
        markup.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main'))
        
        try:
            bot.edit_message_text("✅ Статистика успешно сброшена!\n\n💬 Продолжайте зарабатывать в группе!", 
                                chat_id, message_id,
                                reply_markup=markup)
        except:
            bot.send_message(chat_id, "✅ Статистика успешно сброшена!\n\n💬 Продолжайте зарабатывать в группе!", 
                           reply_markup=markup)

# Статистика
def show_stats_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        try:
            bot.answer_callback_query(call.id, "❌ Пользователь не найден!")
        except:
            bot.send_message(chat_id, "❌ Пользователь не найден!")
        return
    
    user_info = users[user_id_str]
    
    # Считаем различные статистики
    transactions = load_json(TRANSACTIONS_FILE)
    
    total_transfers = 0
    total_deposits = 0
    total_withdrawals = 0
    total_games = 0
    games_won = 0
    total_shop_spent = 0
    
    for trans_id, trans in transactions.items():
        if trans.get('from_user_id') == user_id or trans.get('to_user_id') == user_id:
            trans_type = trans.get('type', '')
            amount = trans.get('amount', 0)
            
            if trans_type == 'transfer':
                total_transfers += 1
            elif trans_type == 'deposit':
                total_deposits += 1
            elif trans_type == 'withdrawal':
                total_withdrawals += 1
            elif trans_type == 'coin_flip':
                total_games += 1
                if amount > 0:
                    games_won += 1
            elif trans_type in ['subscription_purchase', 'privilege_purchase']:
                total_shop_spent += abs(amount)
    
    # Подсчет активных вкладов
    deposits = load_json(DEPOSITS_FILE)
    active_deposits = 0
    total_deposit_amount = 0
    
    for dep_id, deposit in deposits.items():
        if deposit.get('user_id') == user_id and deposit.get('is_active', True):
            active_deposits += 1
            total_deposit_amount += deposit.get('amount', 0)
    
    # Подсчет покупок
    subscriptions = load_json(SUBSCRIPTIONS_FILE)
    privileges = load_json(PRIVILEGES_FILE)
    
    total_subscriptions = sum(1 for sub in subscriptions.values() if sub.get('user_id') == user_id)
    total_privileges = sum(1 for priv in privileges.values() if priv.get('user_id') == user_id)
    
    # Рассчитываем проценты
    win_rate = (games_won / total_games * 100) if total_games > 0 else 0
    avg_transfer = user_info.get('total_earned', 0) / max(1, total_transfers) if total_transfers > 0 else 0
    
    registered_date = datetime.fromisoformat(user_info.get('registered_date', datetime.now().isoformat()))
    days_active = (datetime.now() - registered_date).days
    sct_per_day = user_info.get('total_earned', 0) / max(1, days_active)
    
    # Активность в группе
    last_group_msg = user_info.get('last_group_message_time')
    group_activity = "Никогда"
    if last_group_msg:
        last_time = datetime.fromisoformat(last_group_msg)
        days_ago = (datetime.now() - last_time).days
        if days_ago == 0:
            group_activity = "Сегодня"
        elif days_ago == 1:
            group_activity = "Вчера"
        else:
            group_activity = f"{days_ago} дней назад"
    
    stats_text = (
        f"📊 Детальная статистика:\n\n"
        f"📅 Активность:\n"
        f"• Дней с ботом: {days_active}\n"
        f"• Всего SCT заработано: {user_info.get('total_earned', 0):,}\n"
        f"• SCT в день: {sct_per_day:,.1f}\n"
        f"• Активность в группе: {group_activity}\n\n"
        f"💸 Переводы:\n"
        f"• Всего переводов: {total_transfers}\n"
        f"• Средний перевод: {avg_transfer:,.0f} SCT\n\n"
        f"🏦 Банк:\n"
        f"• Активных вкладов: {active_deposits}/5\n"
        f"• Всего в банке: {total_deposit_amount:,} SCT\n"
        f"• Депозитов/снятий: {total_deposits}/{total_withdrawals}\n\n"
        f"🎰 Игры:\n"
        f"• Всего игр: {total_games}\n"
        f"• Побед: {games_won}\n"
        f"• Процент побед: {win_rate:.1f}%\n\n"
        f"🛒 Покупки:\n"
        f"• Подписок: {total_subscriptions}\n"
        f"• Привилегий: {total_privileges}\n"
        f"• Потрачено в магазине: {total_shop_spent:,} SCT\n\n"
        f"💬 Группа для заработка: https://t.me/c/{str(GROUP_ID)[4:]}/"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('👤 Профиль', callback_data='menu_profile'))
    markup.add(types.InlineKeyboardButton('📊 Весь топ', callback_data='menu_top'))
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    markup.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='menu_main'))
    
    try:
        bot.edit_message_text(stats_text, chat_id, message_id, reply_markup=markup)
    except:
        bot.send_message(chat_id, stats_text, reply_markup=markup)

# Бонус
def give_daily_bonus(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        try:
            bot.answer_callback_query(call.id, "❌ Пользователь не найден!")
        except:
            bot.send_message(chat_id, "❌ Пользователь не найден!")
        return
    
    # Проверяем, когда был последний бонус
    last_bonus = users[user_id_str].get('daily_bonus_date')
    current_time = datetime.now()
    
    if last_bonus:
        last_bonus_date = datetime.fromisoformat(last_bonus)
        hours_since_last = (current_time - last_bonus_date).total_seconds() / 3600
        
        if hours_since_last < 24:
            hours_left = 24 - hours_since_last
            try:
                bot.answer_callback_query(call.id, 
                                         f"⏳ Следующий бонус через {int(hours_left)} часов!")
            except:
                bot.send_message(chat_id, f"⏳ Следующий бонус через {int(hours_left)} часов!")
            return
    
    # Выдаем бонус
    bonus_amount = random.randint(50, 500)
    users[user_id_str]['balance'] = users[user_id_str].get('balance', 0) + bonus_amount
    users[user_id_str]['total_earned'] = users[user_id_str].get('total_earned', 0) + bonus_amount
    users[user_id_str]['daily_bonus_date'] = current_time.isoformat()
    save_json(USERS_FILE, users)
    
    # Добавляем транзакцию
    transactions = load_json(TRANSACTIONS_FILE)
    trans_id = get_next_id(transactions)
    transactions[str(trans_id)] = {
        'from_user_id': 'system',
        'to_user_id': user_id,
        'amount': bonus_amount,
        'type': 'daily_bonus',
        'timestamp': current_time.isoformat()
    }
    save_json(TRANSACTIONS_FILE, transactions)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('🎰 Сыграть в игру', callback_data='menu_coinflip'))
    markup.add(types.InlineKeyboardButton('💸 Сделать перевод', callback_data='menu_transfer'))
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    
    try:
        bot.edit_message_text(
            f"🎁 Ежедневный бонус!\n\n"
            f"💰 Вы получили: {bonus_amount:,} SCT\n"
            f"💳 Новый баланс: {users[user_id_str]['balance']:,} SCT\n\n"
            f"🎯 Следующий бонус через 24 часа!\n\n"
            f"💬 Продолжайте зарабатывать в группе: https://t.me/c/{str(GROUP_ID)[4:]}/",
            chat_id, message_id,
            reply_markup=markup
        )
    except:
        bot.send_message(chat_id,
            f"🎁 Ежедневный бонус!\n\n"
            f"💰 Вы получили: {bonus_amount:,} SCT\n"
            f"💳 Новый баланс: {users[user_id_str]['balance']:,} SCT\n\n"
            f"🎯 Следующий бонус через 24 часа!\n\n"
            f"💬 Продолжайте зарабатывать в группе: https://t.me/c/{str(GROUP_ID)[4:]}/",
            reply_markup=markup
        )

# Помощь
def show_help_callback(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    help_text = (
        "❓ Помощь по боту SCT\n\n"
        "💰 SCT (SedWC Coin) - валюта бота\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 Основные функции:\n"
        "• 💰 Баланс - ваш баланс SCT\n"
        "• 🎰 Орёл/Решка - игра на удачу\n"
        "• 🏦 Банк - вклады под 10% в неделю\n"
        "• 🛒 Магазин - покупка подписок\n"
        "• 👤 Профиль - ваша статистика\n"
        "• 💸 Перевести SCT - перевод другому\n"
        "• 📊 Топ - лучшие игроки с пагинацией\n"
        "• ⚙️ Настройки - настройки бота\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Особенности:\n"
        "• +1 SCT за каждое сообщение В ГРУППЕ\n"
        "• Команды работают ТОЛЬКО в личных сообщениях\n"
        "• Макс. 5 банковских вкладов\n"
        "• Подписки отображаются в профиле\n"
        "• Без комиссии за переводы\n"
        "• Персональное меню с кнопками\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📱 Команды (только в ЛС):\n"
        "/start - Запустить бота\n"
        "/menu - Показать меню\n"
        "/help - Показать справку\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 Группа для заработка SCT:\n"
        f"👉 https://t.me/c/{str(GROUP_ID)[4:]}/\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 Версия: 4.0 (Групповой заработок)"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📱 Показать меню', callback_data='menu_main'))
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    
    try:
        bot.edit_message_text(help_text, chat_id, message_id,
                            reply_markup=markup)
    except:
        bot.send_message(chat_id, help_text, reply_markup=markup)

# Команда /menu
@bot.message_handler(commands=['menu'])
def menu_command(message):
    user_id = message.from_user.id
    
    # Проверяем, что команда используется в ЛС
    if not is_private_chat(message.chat.id):
        bot.reply_to(message, "⚠️ Команды бота работают только в личных сообщениях!\n\n"
                            "💬 Для заработка SCT пишите сообщения в группе:\n"
                            f"👉 https://t.me/c/{str(GROUP_ID)[4:]}/")
        return
    
    bot.send_message(message.chat.id, "📱 Ваше персональное меню:", 
                   reply_markup=personal_inline_menu(user_id, 1))

# Команда /help
@bot.message_handler(commands=['help'])
def help_command(message):
    # Проверяем, что команда используется в ЛС
    if not is_private_chat(message.chat.id):
        bot.reply_to(message, "⚠️ Команды бота работают только в личных сообщениях!\n\n"
                            "💬 Для заработка SCT пишите сообщения в группе:\n"
                            f"👉 https://t.me/c/{str(GROUP_ID)[4:]}/")
        return
    
    help_text = (
        "❓ Помощь по боту SCT\n\n"
        "💰 SCT (SedWC Coin) - валюта бота\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 Основные функции:\n"
        "• 💰 Баланс - ваш баланс SCT\n"
        "• 🎰 Орёл/Решка - игра на удачу\n"
        "• 🏦 Банк - вклады под 10% в неделю\n"
        "• 🛒 Магазин - покупка подписок\n"
        "• 👤 Профиль - ваша статистика\n"
        "• 💸 Перевести SCT - перевод другому\n"
        "• 📊 Топ - лучшие игроки с пагинацией\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📱 Команды (только в ЛС):\n"
        "/start - Запустить бота\n"
        "/menu - Показать меню\n"
        "/help - Показать справку\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 Группа для заработка SCT:\n"
        f"👉 https://t.me/c/{str(GROUP_ID)[4:]}/\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 Используйте кнопки меню для навигации!"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📱 Показать меню', callback_data='menu_main'))
    markup.add(types.InlineKeyboardButton('💬 Перейти в группу', url=f'https://t.me/c/{str(GROUP_ID)[4:]}/'))
    
    bot.send_message(message.chat.id, help_text, reply_markup=markup)

# Команда для группы - информация о заработке
@bot.message_handler(commands=['earn'], func=lambda m: is_target_group(m.chat.id))
def earn_command(message):
    response = (
        "💰 Как зарабатывать SCT?\n\n"
        "💬 Просто пишите сообщения в этой группе!\n"
        "📈 За каждое сообщение вы получаете 1 SCT\n"
        "⏰ Начисление раз в 30 секунд (анти-спам)\n\n"
        "🎯 Дополнительные возможности:\n"
        "• 🏦 Банк под 10% в неделю\n"
        "• 🎰 Игра 'Орёл/Решка'\n"
        "• 🛒 Покупка подписок и привилегий\n"
        "• 💸 Переводы другим пользователям\n\n"
        "📱 Для управления балансом и командами:\n"
        "1. Напишите боту в личные сообщения: @sedwc_bot\n"
        "2. Используйте команду /start\n"
        "3. Выбирайте действия через меню\n\n"
        "💎 Удачи в заработке!"
    )
    bot.reply_to(message, response)

# Функция для еженедельного начисления процентов
def calculate_weekly_interest():
    while True:
        time.sleep(604800)  # 7 дней
        
        print(f"[{datetime.now()}] Начинаю расчет процентов по вкладам...")
        
        deposits = load_json(DEPOSITS_FILE)
        transactions = load_json(TRANSACTIONS_FILE)
        
        updated = False
        
        for dep_id, deposit in list(deposits.items()):
            try:
                if deposit.get('is_active', True):
                    user_id = deposit.get('user_id')
                    amount = deposit.get('amount', 0)
                    interest_rate = deposit.get('weekly_interest', 10)
                    
                    # Рассчитываем проценты
                    interest = (amount * interest_rate) // 100
                    
                    if interest > 0:
                        # Обновляем сумму вклада
                        deposits[dep_id]['amount'] = amount + interest
                        deposits[dep_id]['total_interest'] = deposits[dep_id].get('total_interest', 0) + interest
                        
                        # Записываем транзакцию
                        trans_id = get_next_id(transactions)
                        transactions[str(trans_id)] = {
                            'from_user_id': 'system',
                            'to_user_id': user_id,
                            'amount': interest,
                            'type': 'interest',
                            'timestamp': datetime.now().isoformat(),
                            'deposit_id': dep_id
                        }
                        updated = True
            except Exception as e:
                print(f"Ошибка при расчете процентов для депозита {dep_id}: {e}")
                continue
        
        if updated:
            save_json(DEPOSITS_FILE, deposits)
            save_json(TRANSACTIONS_FILE, transactions)
            print(f"[{datetime.now()}] Проценты по вкладам начислены успешно")
        else:
            print(f"[{datetime.now()}] Активных вкладов для начисления процентов не найдено")

# Функция для резервного копирования
def backup_data():
    import shutil
    import glob
    
    backup_dir = os.path.join(DATA_DIR, 'backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Создаем резервную копию раз в день
    while True:
        time.sleep(86400)  # 24 часа
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        print(f"[{datetime.now()}] Начинаю создание резервной копии...")
        
        try:
            for file_path in [USERS_FILE, TRANSACTIONS_FILE, DEPOSITS_FILE,
                             SUBSCRIPTIONS_FILE, PRIVILEGES_FILE, USER_STATES_FILE]:
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    filename = os.path.basename(file_path)
                    backup_path = os.path.join(backup_dir, f"{timestamp}_{filename}")
                    
                    # Копируем с блокировкой
                    lock = file_locks.get(file_path)
                    if lock:
                        lock.acquire()
                    
                    try:
                        shutil.copy2(file_path, backup_path)
                    finally:
                        if lock:
                            lock.release()
            
            # Удаляем старые бэкапы (старше 7 дней)
            for backup_file in glob.glob(os.path.join(backup_dir, "*")):
                try:
                    file_time = datetime.fromtimestamp(os.path.getctime(backup_file))
                    if (datetime.now() - file_time).days > 7:
                        os.remove(backup_file)
                except Exception as e:
                    print(f"Ошибка при удалении старого бэкапа {backup_file}: {e}")
            
            print(f"[{datetime.now()}] Резервная копия создана успешно")
            
        except Exception as e:
            print(f"[{datetime.now()}] Ошибка при создании резервной копии: {e}")

# Функция для проверки и восстановления целостности данных
def check_data_integrity():
    print("Проверка целостности данных...")
    
    files_to_check = [
        (USERS_FILE, "users"),
        (TRANSACTIONS_FILE, "transactions"),
        (DEPOSITS_FILE, "deposits"),
        (SUBSCRIPTIONS_FILE, "subscriptions"),
        (PRIVILEGES_FILE, "privileges"),
        (USER_STATES_FILE, "user_states")
    ]
    
    for file_path, name in files_to_check:
        try:
            data = load_json(file_path)
            print(f"  {name}: {len(data)} записей")
            
            # Проверяем базовую структуру
            if not isinstance(data, dict):
                print(f"  Внимание: {name} не является словарем, исправляю...")
                save_json(file_path, {})
        
        except Exception as e:
            print(f"  Ошибка проверки {name}: {e}")

# Запуск бота
if __name__ == '__main__':
    init_data_storage()
    check_data_integrity()
    
    # Запуск потока для начисления процентов
    interest_thread = threading.Thread(target=calculate_weekly_interest, daemon=True)
    interest_thread.start()
    
    # Запуск потока для резервного копирования
    backup_thread = threading.Thread(target=backup_data, daemon=True)
    backup_thread.start()
    
    print("=" * 60)
    print("Бот SCT запущен с групповым заработком...")
    print(f"Данные хранятся в папке: {os.path.abspath(DATA_DIR)}")
    print(f"Группа для заработка: {GROUP_ID}")
    print("=" * 60)
    
    # Основной цикл бота с обработкой ошибок
    while True:
        try:
            print(f"[{datetime.now()}] Запускаю бота...")
            bot.polling(none_stop=True, timeout=30, long_polling_timeout=20)
        
        except KeyboardInterrupt:
            print("\nБот остановлен пользователем")
            break
        
        except Exception as e:
            print(f"Критическая ошибка в основном цикле бота: {e}")
            print("Перезапуск через 10 секунд...")
            
            # Сохраняем все данные перед перезапуском
            try:
                check_data_integrity()
            except:
                pass
            
            time.sleep(10)