import logging
from aiogram import Bot, Dispatcher, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, InputMediaPhoto
import sqlite3
from aiogram import types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup


API_TOKEN = '6705359060:AAEoL-TJRaLoLcFgZoLo4E7GGgUll39xfx0'  # Укажите здесь свой API токен
ADMINS = [1255860004, 912509985]
storage = MemoryStorage()

logging.basicConfig(level=logging.INFO)
GROUP_CHAT_ID = -1002118943059

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

# База данных
conn = sqlite3.connect('balance_db.db')
cursor = conn.cursor()

# Создание таблицы, если она не существует
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)
""")
conn.commit()

EXITLAG_PRICES = {
    'exit15': 120,
    'exit30': 200,
    'exit60': 400,
    'exit100': 500,
    'exit150': 550,
    'exit200': 600,
    'exit300': 700
}
VBUCKS_PRICES = {
    'vb1000': 199,
    'vb2800': 479,
    'vb5000': 749,
    'vb13500': 1549
}
DISCORD_PRICES = {
    'discord_c30': 250,
    'discord_c365': 1500,
    'discord_f30': 400,
    'discord_f365': 3050
}


class PurchaseProcess(StatesGroup):
    waiting_for_account_data = State()  # Состояние для ожидания данных аккаунта
    purchase_info = State()  # Состояние для хранения информации о покупке
    waiting_for_payment_photo = State()  # Состояние для ожидания фото чека об оплате


# Функции для работы с балансом
def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

def update_balance(user_id, amount):
    cursor.execute("UPDATE users SET balance = COALESCE((SELECT balance FROM users WHERE user_id = ?) + ?, 0) WHERE user_id = ?", (user_id, amount, user_id))
    conn.commit()


def get_username(user_id):
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None


# Команды бота
@dp.message_handler(commands=['balance'])
async def balance_command(message: Message):
    balance = get_balance(message.from_user.id)
    await message.reply(f'Ваш баланс: {balance}')

@dp.message_handler(commands=['check_balance'])
async def check_balance_command(message: Message):
    if message.from_user.id in ADMINS:
        try:
            user_id = int(message.get_args())
            balance = get_balance(user_id)
            await message.reply(f'Баланс пользователя с ID {user_id}: {balance}')
        except Exception as e:
            await message.reply(f'Ошибка: {e}')
    else:
        await message.reply('У вас нет прав для выполнения этой операции.')

@dp.message_handler(commands=['add'])
async def add_balance_command(message: Message):
    if message.from_user.id in ADMINS:
        try:
            user_id, amount = map(int, message.get_args().split())
            update_balance(user_id, amount)
            await message.reply('Баланс успешно обновлен.')
        except Exception as e:
            await message.reply(f'Ошибка: {e}')
    else:
        await message.reply('У вас нет прав для выполнения этой операции.')

@dp.message_handler(commands=['user'])
async def get_user_info(message: types.Message):
    if str(message.from_user.id) in [str(admin) for admin in ADMINS]:  # Проверяем, является ли пользователь администратором
        try:
            user_id = int(message.get_args())  # Получаем ID пользователя из аргументов команды
            username = get_username(user_id)
            if username:
                await message.reply(f"Username пользователя: @{username}")
            else:
                await message.reply("Пользователь не найден или не взаимодействовал с ботом.")
        except ValueError:
            await message.reply("Пожалуйста, укажите корректный ID пользователя.")
    else:
        await message.reply("У вас нет прав для использования этой команды.")




#EXITLAG

async def notify_purchase_exitlag(user_id, item, period, price):
    message = f"Пользователь с ID {user_id} приобрёл {item} на период {period} дней за {price} руб."
    await bot.send_message(GROUP_CHAT_ID, message)

async def process_purchase(callback_query: types.CallbackQuery, period: str):
    await callback_query.answer()  # Отправляет пустой ответ пользователю
    logging.info(f"Processing purchase for {period}")
    user_id = callback_query.from_user.id
    user_balance = get_balance(user_id)
    price = EXITLAG_PRICES[period]
    item_name = "Exitlag"

    if user_balance >= price:
        update_balance(user_id, -price)  # Уменьшаем баланс пользователя
        balance = get_balance(user_id)
        await bot.send_message(user_id, f"Покупка успешно совершена! {period[4:]} дней {item_name} будут активированы. После выполнения заказа с вами свяжутся администраторы и выдадут данные от аккаунта. Ваш баланс: {balance}")
        await notify_purchase_exitlag(user_id, item_name, period[4:], price)  # Отправляем уведомление в группу
    else:
        await bot.send_message(user_id, "Недостаточно средств на балансе.")

@dp.callback_query_handler(lambda c: c.data.startswith("exit"))
async def purchase_exit(callback_query: types.CallbackQuery):
    try:
        await process_purchase(callback_query, callback_query.data)
    except Exception as e:
        logging.error(f"Error processing purchase: {e}")
        await callback_query.answer("Произошла ошибка при обработке вашего запроса.")

async def notify_vbucks_purchase(user_id, amount, price):
    message = f"Пользователь с ID {user_id} приобрёл {amount} V-Bucks за {price} руб."
    await bot.send_message(GROUP_CHAT_ID, message)





#VBUCKS

@dp.callback_query_handler(lambda c: c.data.startswith("vb"))
async def purchase_vbucks(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    vbucks_code = callback_query.data
    price = VBUCKS_PRICES[vbucks_code]
    user_balance = get_balance(user_id)

    if user_balance >= price:
        update_balance(user_id, -price)
        balance_after_purchase = get_balance(user_id)

        async with state.proxy() as data:
            data['purchase_type'] = 'vbucks'
            data['item_code'] = vbucks_code
            data['price'] = price
            data['balance_after_purchase'] = balance_after_purchase

        await PurchaseProcess.waiting_for_account_data.set()
        await bot.send_message(user_id, "Введите данные вашего аккаунта для активации V-Bucks:")
    else:
        await bot.send_message(user_id, "Недостаточно средств на балансе.")








#DISCORD NITRO

@dp.callback_query_handler(lambda c: c.data.startswith("discord_"))
async def purchase_discord_nitro(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    product_code = callback_query.data
    price = DISCORD_PRICES[product_code]
    user_balance = get_balance(user_id)

    if user_balance >= price:
        update_balance(user_id, -price)
        new_balance = get_balance(user_id)

        item_name = "Discord Nitro Classic" if "c" in product_code else "Discord Nitro Full"
        duration = "30 дней" if "30" in product_code else "365 дней"

        async with state.proxy() as data:
            data['purchase_type'] = 'discord'
            data['item_name'] = item_name
            data['duration'] = duration
            data['price'] = price
            data['new_balance'] = new_balance

        await PurchaseProcess.waiting_for_account_data.set()
        await bot.send_message(user_id, "Покупка успешно совершена! Пожалуйста, введите данные вашего аккаунта для активации Discord Nitro.")
    else:
        await bot.send_message(user_id, "Недостаточно средств на балансе.")




@dp.message_handler(state=PurchaseProcess.waiting_for_account_data, content_types=types.ContentTypes.TEXT)
async def account_data_received(message: types.Message, state: FSMContext):
    account_data = message.text
    user_id = message.from_user.id

    async with state.proxy() as data:
        purchase_type = data.get(
            'purchase_type')  # Это новое поле, которое указывает на тип покупки ('vbucks' или 'discord')

        if purchase_type == 'vbucks':
            # Обработка данных аккаунта для покупки V-Bucks
            item_code = data.get('item_code')
            price = data.get('price')
            balance_after_purchase = data.get('balance_after_purchase')
            # Сообщение для администраторов и пользователя о покупке V-Bucks
            admin_message = f"Пользователь с ID {user_id} приобрёл V-Bucks (код товара: {item_code}) за {price} руб. Баланс после покупки: {balance_after_purchase}. Данные аккаунта: {account_data}"

        elif purchase_type == 'discord':
            # Обработка данных аккаунта для покупки Discord Nitro
            item_name = data.get('item_name')
            duration = data.get('duration')
            price = data.get('price')
            new_balance = data.get('new_balance')
            # Сообщение для администраторов и пользователя о покупке Discord Nitro
            admin_message = f"Пользователь с ID {user_id} приобрёл {item_name} на {duration} за {price} руб. Новый баланс: {new_balance}. Данные аккаунта: {account_data}"

        else:
            await message.reply("Произошла ошибка при обработке вашей покупки. Пожалуйста, попробуйте снова.")
            await state.finish()
            return

        await bot.send_message(GROUP_CHAT_ID, admin_message)
        await bot.send_message(user_id,
                               "Ваши данные аккаунта получены и отправлены на обработку. Скоро с вами свяжутся администраторы.")
        await state.finish()


def add_or_update_user(user_id, username):
    # Вставляем или обновляем данные пользователя только если username отсутствует и excluded.username не равен NULL
    cursor.execute("""
    INSERT INTO users (user_id, username, balance) VALUES (?, ?, 0)
    ON CONFLICT(user_id) DO UPDATE SET username = COALESCE(users.username, excluded.username)
    WHERE excluded.username IS NOT NULL
    """, (user_id, username))
    conn.commit()


# Клавиатуры
def start_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Fortnite", callback_data="fortnite"))
    keyboard.add(InlineKeyboardButton("Exitlag", callback_data="mexitlag"))
    keyboard.add(InlineKeyboardButton("Discord", callback_data="mdiscord"))
    keyboard.add(InlineKeyboardButton("Личный кабинет", callback_data="account"))
    return keyboard

def fortnite_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("В-Баксы", callback_data="mvb"))
    keyboard.add(InlineKeyboardButton("Наборы", callback_data="mkits"))
    keyboard.add(InlineKeyboardButton("Назад", callback_data="back_start"))
    return keyboard

def exitlag_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton(text="Купить 15d", callback_data="exit15"),
                 InlineKeyboardButton(text="Купить 30d", callback_data="exit30"))
    keyboard.add(InlineKeyboardButton(text="Купить 60d", callback_data="exit60"),
                 InlineKeyboardButton(text="Купить 100d", callback_data="exit100"))
    keyboard.add(InlineKeyboardButton(text="Купить 150d", callback_data="exit150"),
                 InlineKeyboardButton(text="Купить 200d", callback_data="exit200"))
    keyboard.add(InlineKeyboardButton(text="Купить 300d", callback_data="exit300"))
    keyboard.row(InlineKeyboardButton(text="Назад", callback_data="back_start"))
    return keyboard

def vb_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Купить 1000 VB", callback_data="vb1000"),
                InlineKeyboardButton("Купить 2800 VB", callback_data="vb2800"))
    keyboard.add(InlineKeyboardButton("Купить 5000 VB", callback_data="vb5000"),
                InlineKeyboardButton("Купить 13500 VB", callback_data="vb13500"))
    keyboard.add(InlineKeyboardButton("Назад", callback_data="back_fortnite"))
    return keyboard

def discord_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Classic 30d", callback_data="discord_c30"),
                InlineKeyboardButton("Classic 365d", callback_data="discord_c365"))
    keyboard.add(InlineKeyboardButton("Full 30d", callback_data="discord_f30"),
                InlineKeyboardButton("Full 365d", callback_data="discord_f365"))
    keyboard.add(InlineKeyboardButton("Назад", callback_data="back_start"))
    return keyboard


def account_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Пополнить баланс", callback_data="add_balance"))
    keyboard.add(InlineKeyboardButton("Назад", callback_data="back_start"))
    return keyboard


# Обработка команды старт и вывод клавиатуры
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    add_or_update_user(user_id, username)
    # Отправка изображения с подписью
    with open('start.jpg', 'rb') as photo:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=photo,
            caption="Добро пожаловать FITShop! Выберите категорию:",
            reply_markup=start_keyboard()  # предполагается, что эта функция возвращает объект клавиатуры
        )






@dp.callback_query_handler(lambda c: c.data == 'add_balance')
async def add_balance(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    instructions = "Для пополнения баланса переведите нужную сумму на следующие реквизиты: [Номер карты/Счёт]. После перевода нажмите кнопку 'Я перевёл'."
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("Я перевёл", callback_data="confirm_transfer"))
    await bot.send_message(callback_query.from_user.id, instructions, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'confirm_transfer')
async def confirm_transfer(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Пожалуйста, пришлите фото чека об оплате.")
    await PurchaseProcess.waiting_for_payment_photo.set()  # Переводим пользователя в состояние ожидания фото

@dp.message_handler(content_types=['photo'], state=PurchaseProcess.waiting_for_payment_photo)
async def payment_photo_received(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    balance = get_balance(user_id)  # предполагается, что функция get_balance возвращает текущий баланс пользователя

    # Отправка информации администраторам
    info_for_admins = f"Пользователь: @{username} (ID: {user_id}) отправил фото чека. Текущий баланс: {balance}"
    await bot.send_photo(GROUP_CHAT_ID, message.photo[-1].file_id, caption=info_for_admins)  # Пересылаем фото и информацию в группу администраторов

    # Уведомление пользователя
    await bot.send_message(message.from_user.id, "Спасибо, ваша оплата на проверке. Мы свяжемся с вами после проверки.")
    await state.finish()  # Выход из состояния ожидания


@dp.callback_query_handler(lambda c: c.data == "account")
async def account_info(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username
    balance = get_balance(user_id)  # Получение текущего баланса пользователя

    # Текст подписи с информацией о пользователе
    account_info_caption = f"Ваш ID: {user_id}\nВаш username: @{username}\nВаш текущий баланс: {balance} руб."

    # Открытие файла изображения для отправки
    with open('start.jpg', 'rb') as photo:  # Укажите правильный путь к изображению
        # Обновление медиа-содержимого сообщения
        await bot.edit_message_media(
            media=types.InputMediaPhoto(photo),
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id
        )

        # Обновление подписи сообщения с информацией о пользователе
        await bot.edit_message_caption(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id,
            caption=account_info_caption,
            reply_markup=account_keyboard()  # Предполагается, что account_keyboard() возвращает клавиатуру для раздела "Личный кабинет"
        )




# Обработка нажатий на кнопки
@dp.callback_query_handler(lambda c: True)
async def process_callback(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    data = callback_query.data

    if data == "fortnite":
        # Создание нового объекта InputMediaPhoto с новым изображением
        new_photo = InputMediaPhoto(open('start.jpg', 'rb'))

        # Изменение медиа-содержимого сообщения
        await bot.edit_message_media(
            media=new_photo,
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id
        )

        # Опционально: изменение подписи сообщения, если требуется
        await bot.edit_message_caption(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id,
            caption="Тут вы можете купить всё для игры Fortnite по самым низким ценам\nВАЖНО\n• Необходимо создать учетную запись Xbox.\n• При регистрации ставьте возраст 18+ \n• Затем привязать его к аккаунту Epic Games во вкладке Соединения: Соединения > XBOX > Подключить",
            reply_markup=fortnite_keyboard()  # Отправка обновленной клавиатуры, если нужно
        )

    if data == "back_start":
        # Создание нового объекта InputMediaPhoto с новым изображением
        new_photo = InputMediaPhoto(open('start.jpg', 'rb'))

        # Изменение медиа-содержимого сообщения
        await bot.edit_message_media(
            media=new_photo,
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id
        )

        # Опционально: изменение подписи сообщения, если требуется
        await bot.edit_message_caption(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id,
            caption="Добро пожаловать в наш магазин! Выберите категорию:",
            reply_markup=start_keyboard()  # Отправка обновленной клавиатуры, если нужно
        )


    if data == "back_fortnite":
        # Создание нового объекта InputMediaPhoto с новым изображением
        new_photo = InputMediaPhoto(open('start.jpg', 'rb'))

        # Изменение медиа-содержимого сообщения
        await bot.edit_message_media(
            media=new_photo,
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id
        )

        # Опционально: изменение подписи сообщения, если требуется
        await bot.edit_message_caption(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id,
            caption="Тут вы можете купить всё для игры Fortnite по самым низким ценам\nВАЖНО\n• Необходимо создать учетную запись Xbox.\n• При регистрации ставьте возраст 18+ \n• Затем привязать его к аккаунту Epic Games во вкладке Соединения: Соединения > XBOX > Подключить",
            reply_markup=fortnite_keyboard()  # Отправка обновленной клавиатуры, если нужно
        )

    if data == "mexitlag":
        # Создание нового объекта InputMediaPhoto с новым изображением
        new_photo = InputMediaPhoto(open('mexitlag.png', 'rb'))

        # Изменение медиа-содержимого сообщения
        await bot.edit_message_media(
            media=new_photo,
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id
        )

        # Опционально: изменение подписи сообщения, если требуется
        await bot.edit_message_caption(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id,
            caption="EXITLAG (При нажатии на кнопку сразу происходит оплата с баланса) \n15 дней - 120 рублей\n30 дней - 200 рублей\n60 дней - 400 рублей\n100 дней - 500 рубля\n150 дней - 550 рублей\n200 дней - 600 рублей\n300 дней - 700 рублей",
            reply_markup=exitlag_keyboard()  # Отправка обновленной клавиатуры, если нужно
        )

    if data == "mvb":
        # Создание нового объекта InputMediaPhoto с новым изображением
        new_photo = InputMediaPhoto(open('mvb.jpg', 'rb'))

        # Изменение медиа-содержимого сообщения
        await bot.edit_message_media(
            media=new_photo,
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id
        )

        # Опционально: изменение подписи сообщения, если требуется
        await bot.edit_message_caption(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id,
            caption="Выберите количество:\n1000 В-Баксов - 199 рублей\n2800 В-Баксов - 479 рублей\n5.000 В-Баксов - 749 рублей\n13.500 В-Баксов - 1549 рублей",
            reply_markup=vb_keyboard()  # Отправка обновленной клавиатуры, если нужно
        )

    if data == "mdiscord":
        # Создание нового объекта InputMediaPhoto с новым изображением
        new_photo = InputMediaPhoto(open('mdiscord.png', 'rb'))

        # Изменение медиа-содержимого сообщения
        await bot.edit_message_media(
            media=new_photo,
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id
        )

        # Опционально: изменение подписи сообщения, если требуется
        await bot.edit_message_caption(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id,
            caption="Discord Nitro\nDiscord Nitro Classic 30 дней- 250₽\nDiscord Nitro Classic 365 дней- 1500₽\nDiscord Nitro Full 30 дней- 400₽\nDiscord Nitro Full 365 дней - 3050₽\nДанное нитро подходит для любых аккаунтов!",
            reply_markup=discord_keyboard()  # Отправка обновленной клавиатуры, если нужно
        )








# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
