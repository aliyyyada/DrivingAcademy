from telebot import types
from config import token
from bot_module.database import DB_connect
from bot_module.utils import *
from bot_module.states import *
from telebot import TeleBot
from psycopg2.extras import DictCursor
from bot_module.handlers.student import *
from bot_module.loader import bot

def instructor_menu(user_id):
    keyboard = [
        [types.KeyboardButton('Список курсантов')],
        [types.KeyboardButton('Редактировать расписание')],
        [types.KeyboardButton('Календарь расписания')]
    ]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(*[i for sublist in keyboard for i in sublist])
    bot.send_message(user_id, 'Главное меню:', reply_markup=markup)
    set_user_state(user_id, INSTRUCTOR_MENU)