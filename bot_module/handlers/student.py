from telebot import types
from config import token
from bot_module.database import DB_connect
from bot_module.utils import *
from bot_module.states import *
from telebot import TeleBot
from psycopg2.extras import DictCursor
from bot_module.handlers.student import *
from bot_module.loader import bot
from datetime import date, datetime, timedelta
from bot_module.calendar import handle_calendar_navigation, generate_calendar, show_calendar_message
from bot_module.notification import add_notification_to_schedle, remove_notification_from_schedule

def student_menu(user_id):
    keyboard = [[types.KeyboardButton('Информация об обучении')], [types.KeyboardButton('Записаться на вождение')], [types.KeyboardButton('Предстоящие занятия')], [types.KeyboardButton('Выйти из аккаунта')]]
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
def student_show_calendar(message):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT st.hours FROM student st 
                    WHERE st.id_user = (SELECT u.id FROM users u WHERE u.phone_number=%s)
            ''', (user_states[message.chat.id]['phone'], ))
            hours = cur.fetchone()
            if hours and hours[0]>0:
                today = date.today()
                show_calendar_message(bot, message.chat.id, today.year, today.month)
            else:
                bot.send_message(message.chat.id, 'У вас недостаточно часов для записи на занятие. Пожалуйста, обратитесь в автошколу для получения дополнительных часов.')


@bot.callback_query_handler(func=lambda callback: (callback.data.startswith("month_") or callback.data.startswith("date_")) and get_user_state(callback.message.chat.id) == MAIN_MENU)
def student_sign_up(callback):
    if callback.data.startswith("month_"):
        handle_calendar_navigation(callback, bot)
    elif callback.data.startswith("date_") and get_user_state(callback.message.chat.id) == MAIN_MENU:
        date_selected = handle_calendar_navigation(callback, bot)
        current_time = datetime.now()
        with DB_connect() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT s.start_time, s.end_time, s.id
	                FROM session s 
		            WHERE s.date=%s AND s.instructor_id =(SELECT st.instructor_id 
															        FROM student st 
																    WHERE st.id_user= (SELECT u.id
																				  	    FROM users u
																				  		WHERE u.phone_number=%s)
													                 ) AND s.status='free'       
                    ORDER BY s.start_time;
                ''', (date_selected, user_states[callback.message.chat.id]['phone'],))
                schedule = cur.fetchall()
                markup = types.InlineKeyboardMarkup()
                if schedule:
                    for item in schedule:
                        start_time = item[0]
                        end_time = item[1]
                        session_id = item[2]

                        slot_time = datetime.combine(datetime.strptime(date_selected, "%Y-%m-%d").date(), start_time)

                        if slot_time > current_time + timedelta(hours=24):
                            start_time_formatted = start_time.strftime('%H:%M')
                            end_time_formatted = end_time.strftime('%H:%M')
                            button_text = f"{start_time_formatted}-{end_time_formatted}"
                            callback_data = f"signup_{session_id}"
                            markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))


                        else:

                            button_text = f"{start_time}-{end_time} (нельзя записаться)"
                            markup.add(types.InlineKeyboardButton(button_text, callback_data="inactive"))

                    sent_message = bot.send_message(callback.message.chat.id, "Выберите время для записи на занятие:",
                                                    reply_markup=markup)
                    user_states[callback.message.chat.id]['message_id'] = sent_message.message_id

                else:
                    bot.send_message(callback.message.chat.id, "Нет свободных слотов для записи на выбранную дату.")


@bot.callback_query_handler(func=lambda callback: callback.data.startswith("signup_"))
def handle_sign_up(callback):
    session_id = callback.data.split("_")[1]
    with DB_connect() as conn:
        with conn.cursor() as cur:

            cur.execute('''
                    SELECT status FROM session 
                        WHERE id = %s
                    ''', (session_id,))
            session_status = cur.fetchone()
            if session_status and session_status[0] == 'free':
                cur.execute('''
                            INSERT INTO booking (session_id, student_id, status) 
                                            VALUES (%s, (SELECT id FROM student WHERE id_user = (SELECT id FROM users WHERE phone_number = %s)), 'booked')
                    ''', (session_id, user_states[callback.message.chat.id]['phone']))
                cur.execute('''
                    UPDATE session SET status='booked' WHERE id =%s
                ''', (session_id, ))
                cur.execute('''
                    SELECT b.id 
                        FROM booking b
                            WHERE b.session_id =%s AND b.status = 'booked'
                ''', (session_id, ))
                booking_id = cur.fetchone()
                cur.execute('''
                    SELECT st.hours, st.id 
                        FROM student st 
                            JOIN users u ON st.id_user= u.id 
                                WHERE u.phone_number=%s
                ''', (user_states[callback.message.chat.id]['phone'], ))
                student = cur.fetchone()

                if student:
                    hours = student[0]-1
                    id = student[1]
                    cur.execute('''
                        UPDATE student SET hours=%s WHERE id=%s
                    ''', (hours, id, ))
                conn.commit()
                bot.edit_message_reply_markup(callback.message.chat.id, user_states[callback.message.chat.id]['message_id'],reply_markup=None)
                bot.send_message(callback.message.chat.id, "Вы успешно записались на занятие!")
                add_notification_to_schedle(booking_id)

            else:
                bot.send_message(callback.message.chat.id, "Этот слот уже занят или недоступен для записи.")

@bot.message_handler(func=lambda message: message.text=='Предстоящие занятия' and get_user_state(message.chat.id)==MAIN_MENU)
def handle_student_upcoming_lessons(message):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT DISTINCT ON (s.id)
                    s.id,
                    s.date,
                    s.start_time,
                    s.end_time,
                    s.status 
                FROM users u
                JOIN student st ON st.id_user = u.id
                JOIN booking b ON b.student_id = st.id
                JOIN session s ON s.id = b.session_id
                WHERE 
                    u.phone_number = %s  
                    AND s.date >= CURRENT_DATE
                    AND (b.status = 'booked' OR s.status = 'canceled') 
                ORDER BY 
                    s.id, s.date, s.start_time;   
            ''', (user_states[message.chat.id]['phone'], ))
            schedule = cur.fetchall()
            if schedule:
                markup = types.InlineKeyboardMarkup()
                for item in schedule:
                    session_id=item[0]
                    slot_date=str(item[1])
                    slot_start_time=str(item[2])
                    slot_end_time = str(item[3])
                    slot_status = item[4]
                    button_text = f'{format_date(slot_date)} {format_time(slot_start_time)}-{format_time(slot_end_time)}' if slot_status=='booked' else f'{format_date(slot_date)} {format_time(slot_start_time)}-{format_time(slot_end_time)} Отменено'
                    markup.add(types.InlineKeyboardButton(button_text, callback_data=f'cancel_booking_session_{session_id}'))
                bot.send_message(message.chat.id, 'Чтобы отменить запись, нажмите на неё.', reply_markup=markup)

            else:
                bot.send_message(message.chat.id, 'У вас нет предстоящих занятий.')

@bot.callback_query_handler(func=lambda callback: callback.data.startswith('cancel_booking_session_'))
def get_confirm_cancel(callback):
    markup = types.InlineKeyboardMarkup()
    session_id = callback.data.split("_")[3]
    markup.add(types.InlineKeyboardButton('Да', callback_data=f'yes_confirm_cancel_session_{session_id}'), types.InlineKeyboardButton('Нет', callback_data='no_confirm_cancel_session'))
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT s.date, s.start_time, s.end_time FROM  session s WHERE s.id = %s
            ''', (session_id, ))
            session = cur.fetchone()
            if session:
                sent_message=bot.send_message(callback.message.chat.id, f'Вы хотите отменить запись на {format_date(str(session[0]))} {format_time(str(session[1]))}-{format_time(str(session[2]))}?', reply_markup=markup)
                user_states[callback.message.chat.id]['message_id'] = sent_message.message_id

@bot.callback_query_handler(func=lambda callback: callback.data.startswith('yes_confirm_cancel_session_'))
def cancel_booking(callback):
    session_id = callback.data.split("_")[4]
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE booking SET status='canceled' WHERE session_id=%s
            ''', (session_id, ))
            cur.execute('''
                UPDATE session SET status='free' WHERE id = %s
            ''', (session_id, ))
            cur.execute('''
                                SELECT st.hours, st.id 
                                    FROM student st 
                                        JOIN users u ON st.id_user= u.id 
                                            WHERE u.phone_number=%s
                            ''', (user_states[callback.message.chat.id]['phone'],))
            student = cur.fetchone()

            if student:
                hours = student[0] + 1
                id = student[1]
                cur.execute('''
                                    UPDATE student SET hours=%s WHERE id=%s
                                ''', (hours, id,))
            conn.commit()
            bot.edit_message_reply_markup(callback.message.chat.id, user_states[callback.message.chat.id]['message_id'], reply_markup=None)
            bot.send_message(callback.message.chat.id, 'Запись на занятие отменена.')
            remove_notification_from_schedule(session_id)

@bot.callback_query_handler(func=lambda callback: callback.data=='no_confirm_cancel_session')
def no_cancel_booking(callback):
    bot.send_message(callback.message.chat.id, 'Расписание оставлено без изменений.')
