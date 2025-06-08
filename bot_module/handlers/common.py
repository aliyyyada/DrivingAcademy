from bot_module.loader import bot
from bot_module.utils import *
from bot_module.states import *
from telebot import types

@bot.message_handler(func=lambda message: message.text == 'Главное меню')
def handle_global_main_menu(message):
    from bot_module.utils import update_phone_number, get_user_role_by_phone
    from bot_module.handlers.instructor import instructor_menu
    from bot_module.handlers.admin import admin_menu

    update_phone_number(message.chat.id)
    phone = user_states.get(message.chat.id, {}).get('phone')

    if not phone:
        bot.send_message(message.chat.id, 'Не удалось определить номер телефона.')
        return

    role = get_user_role_by_phone(phone)

    if role == 'instructor':
        set_user_state(message.chat.id, INSTRUCTOR_MENU)
        instructor_menu(message.chat.id)

    elif role == 'admin':
        set_user_state(message.chat.id, ADMIN_MENU)
        admin_menu(message.chat.id)

    else:
        bot.send_message(message.chat.id, 'Неизвестная роль. Обратитесь к администратору.')

@bot.message_handler(func=lambda message: message.text.lower()=='выйти из аккаунта')
def logout(message):
    user_states.pop(message.chat.id, None)
    set_user_state(message.chat.id, AUTHENTICATION)
    remove_markup = types.ReplyKeyboardRemove()

    keyboard = [[
        types.InlineKeyboardButton('Регистрация', callback_data='reg'),
        types.InlineKeyboardButton('Вход', callback_data='auth')
    ]]
    markup = types.InlineKeyboardMarkup(keyboard)
    bot.send_message(message.chat.id, 'Вы вышли из аккаунта.', reply_markup=remove_markup)
    bot.send_message(
        message.chat.id,
        'Добро пожаловать в Академию Вождения!',
        reply_markup=markup
    )