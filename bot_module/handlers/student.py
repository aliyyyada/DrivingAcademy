from telebot import types
from config import token
from bot_module.database import DB_connect
from bot_module.utils import *
from bot_module.states import *
from telebot import TeleBot
from psycopg2.extras import DictCursor
from bot_module.handlers.student import *
from bot_module.loader import bot

def student_menu(user_id):
    keyboard = [[types.KeyboardButton('Информация об обучении')], [types.KeyboardButton('Записаться на вождение')], [types.KeyboardButton('Предстоящие занятия')]]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(*[i for sublist in keyboard for i in sublist])
    bot.send_message(user_id, 'Главное меню:', reply_markup=markup)

    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT phone_number FROM users WHERE id = %s', (user_id,))
            result = cur.fetchone()
            phone = result[0] if result else None
    user_states[user_id] = {
        'phone': phone
    }
    set_user_state(user_id, MAIN_MENU)

@bot.message_handler(func=lambda message: message.text=='Информация об обучении' and get_user_state(message.chat.id)==MAIN_MENU)
def handle_student_get_info(message):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT u.phone_number, u.full_name, i.car_plate, i.car_model, i.car_color
                FROM instructor i 
                    JOIN users u ON u.id=i.id_user
                    WHERE i.id=(SELECT s.instructor_id
                                    FROM student s
                                        JOIN users u1 ON u1.id=s.id_user
                                            WHERE u1.phone_number=%s)
            ''', (user_states[message.chat.id]['phone'], ))
            instructor_info = cur.fetchone()
            cur.execute('''
                SELECT s.hours 
                    FROM student s
                        WHERE s.id_user = (SELECT u.id
                                            FROM users u WHERE u.phone_number = %s)
            ''', (user_states[message.chat.id]['phone'],))
            hours_info = cur.fetchone()

            if instructor_info and hours_info:
                mes=f'Оставшееся количесвто часов обучения - {hours_info[0]}'
                mes+= f'\nАвтоинструктор:\n{instructor_info[1]} | {instructor_info[0]}'
                mes+=f'\n\nУчебный автомобиль:\n{instructor_info[3]} {instructor_info[2]} ({instructor_info[4]})'
                bot.send_message(message.chat.id, mes)
            else:
                bot.send_message(message.chat.id, 'Ошибка при запросе данных.')
    set_user_state(message.chat.id, MAIN_MENU)

@bot.message_handler(func=lambda message: message.text=='Записаться на вождение' and get_user_state(message.chat.id)==MAIN_MENU)
def handle_student_sign_up_main(message):
