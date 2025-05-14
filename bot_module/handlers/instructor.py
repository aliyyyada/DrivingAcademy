from telebot import types
from config import token
from bot_module.database import DB_connect
from bot_module.utils import *
from bot_module.states import *
from telebot import TeleBot
from psycopg2.extras import DictCursor
from bot_module.handlers.student import *
from bot_module.loader import bot
from bot_module.calendar import generate_calendar, handle_calendar_navigation, show_calendar_message
from datetime import datetime, date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from bot_module.notification import notify_student_about_new_slots, notify_student_about_lesson_cancel, remove_notification_from_schedule

def instructor_menu(user_id):
    keyboard = [
        [types.KeyboardButton('Список курсантов')],
        [types.KeyboardButton('Редактировать расписание')],
        [types.KeyboardButton('Календарь расписания')]
    ]
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
    set_user_state(user_id, INSTRUCTOR_MENU)


@bot.message_handler(func=lambda message: message.text == 'Список курсантов' and get_user_state(message.chat.id)==INSTRUCTOR_MENU)
def handle_instructor_menu_student_list(message):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                '''
                SELECT u.full_name,  s.hours, u.phone_number
                    FROM student s
                        JOIN users u ON s.id_user = u.id
                            WHERE s.instructor_id = (SELECT i.id FROM instructor i
	                                    JOIN users u ON u.id=i.id_user WHERE u.phone_number= %s)

                ''',
                (user_states[message.chat.id]['phone'],)
            )
            students = cur.fetchall()
            if students:
                respone = 'Ваши ученики: \n\n'
                temp = f"{'ФИО':<50}{'Остатки часов':<20}{'Номер телефона':<20}\n"
                respone += temp
                for i, (full_name, hours, phone) in enumerate(students, start=1):
                    respone+= f"{full_name:<50}{hours:<20}{phone}\n"
                bot.send_message(message.chat.id, respone)
            else:
                bot.send_message(message.chat.id, 'У вас пока нет прикреплённых курсантов.')

@bot.message_handler(func = lambda message: message.text == 'Редактировать расписание' and get_user_state(message.chat.id) == INSTRUCTOR_MENU)
def handle_instructor_menu_edit_schedule(message):
    keyboard = [
        [types.KeyboardButton('Добавить расписание (txt файл)')],
        [types.KeyboardButton('Добавить расписание (сообщение)')],
        [types.KeyboardButton('Отменить занятие')],
        [types.KeyboardButton('Главное меню')]
    ]
    markup =types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(*[i for sublist in keyboard for i in sublist])
    bot.send_message(message.chat.id, 'Выберите действие: ', reply_markup=markup)
    set_user_state(message.chat.id, EDIT_SCHEDULE)

@bot.message_handler(func=lambda message: message.text == 'Добавить расписание (txt файл)' and get_user_state(message.chat.id) == EDIT_SCHEDULE)
def handle_instructor_menu_edit_schedule_add_txt(message):
    bot.send_message(message.chat.id, 'Отправьте txt файл с расписанием в формате *ДД.ММ.ГГ ЧЧ:ММ-ЧЧ:ММ*')
    set_user_state(message.chat.id, WAITING_TXT_FILE)

@bot.message_handler(content_types=['document'],  func=lambda message: get_user_state(message.chat.id) == WAITING_TXT_FILE )
def handle_instructor_menu_edit_schedule_add_txt_recive(message):
    file_id = message.document.file_id
    file_info = bot.get_file(file_id)
    download_file = bot.download_file(file_info.file_path)
    mess = download_file.decode('utf-8')
    schedule_entries = mess.strip().split('\n')

    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT i.id 
                    FROM instructor i
                        JOIN users u ON i.id_user = u.id WHERE u.phone_number=%s
            ''', (user_states[message.chat.id]['phone'], ))
            instructor_id = cur.fetchone()[0]

            for i in schedule_entries:
                try:
                    date_str, time_str = i.split(' ')
                    start_time, end_time = time_str.split('-')
                    cur.execute(
                        'INSERT INTO session (instructor_id,  date, start_time, end_time, status) VALUES (%s,  %s, %s, %s, %s)',
                        (instructor_id, date_str, start_time, end_time, 'free')
                    )
                except Exception as e:
                    bot.send_message(message.chat.id, f'Ошибка при добавлении записи в БД {i}: {e}')

            conn.commit()
            bot.send_message(message.chat.id, 'Расписание успешно добавлено!')
            notify_student_about_new_slots(user_states[message.chat.id]['phone'], mess)
        set_user_state(message.chat.id, EDIT_SCHEDULE)

@bot.message_handler(func=lambda message: message.text == 'Добавить расписание (сообщение)' and get_user_state(message.chat.id) == EDIT_SCHEDULE)
def handle__instructor_menu_edit_schedule_add_message(message):
    bot.send_message(message.chat.id, 'Отправьте расписание в формате *ДД.ММ.ГГ ЧЧ:ММ-ЧЧ:ММ*')
    set_user_state(message.chat.id, WAITING_TEXT_SCHEDULE)

@bot.message_handler(func=lambda message: get_user_state(message.chat.id) == WAITING_TEXT_SCHEDULE)
def handle_received_text_schedule(message):
    mess = message.text
    schedule_entries = mess.strip().split("\n")

    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                            SELECT i.id 
                                FROM instructor i
                                    JOIN users u ON i.id_user = u.id WHERE u.phone_number=%s
                        ''', (user_states[message.chat.id]['phone'],))
            instructor_id = cur.fetchone()[0]

            for i in schedule_entries:
                try:
                    date_str, time_str = i.split(" ")
                    start_time, end_time = time_str.split("-")
                    cur.execute(
                        'INSERT INTO session (instructor_id,  date, start_time, end_time, status) VALUES (%s,  %s, %s, %s, %s)',
                        (instructor_id, date_str, start_time, end_time, 'free')
                    )
                except Exception as e:
                    bot.send_message(message.chat.id, f'Ошибка при добавлении записи в БД {i}: {e}')

            conn.commit()
            bot.send_message(message.chat.id, 'Расписание успешно добавлено!')
            notify_student_about_new_slots(user_states[message.chat.id]['phone'], mess)

    set_user_state(message.chat.id, EDIT_SCHEDULE)


@bot.message_handler(func=lambda message: message.text == 'Отменить занятие' and get_user_state(message.chat.id) == EDIT_SCHEDULE)
def handle_instructor_menu_cancel_lesson_request(message):
    bot.send_message(message.chat.id, 'Введите дату занятия, которое хотите отменить в формате *ДД.ММ.ГГ ЧЧ:ММ*. (Укажите только время начала занятия).')
    set_user_state(message.chat.id, WAITING_CANCEL_CONFIRMATION)


@bot.message_handler(func=lambda message: get_user_state(message.chat.id) == WAITING_CANCEL_CONFIRMATION)
def handle_cancel_lesson_confirmation(message):
    lesson_time = message.text.strip()


    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT i.id 
                    FROM instructor i
                        JOIN users u ON i.id_user = u.id WHERE u.phone_number=%s
            ''', (user_states[message.chat.id]['phone'],))
            instructor_id = cur.fetchone()[0]
            date_str, time_str = lesson_time.split()


            date = datetime.strptime(date_str, '%d.%m.%y').replace(year=2000 + int(date_str.split('.')[2])).date()
            time = datetime.strptime(time_str, '%H:%M').time()

            cur.execute("SELECT * FROM session WHERE instructor_id = %s AND date = %s AND start_time = %s",
                        (instructor_id, date, time))
            lesson = cur.fetchone()

            if lesson:
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("Да", callback_data="confirm_cancel_yes"),
                             types.InlineKeyboardButton("Нет", callback_data="confirm_cancel_no"))
                bot.send_message(message.chat.id, f'Вы уверены, что хотите отменить занятие {lesson_time}?', reply_markup=keyboard)
                user_states[message.chat.id]['date'] = date
                user_states[message.chat.id]['time'] = time

                set_user_state(message.chat.id, 'CONFIRM_CANCEL')
            else:
                bot.send_message(message.chat.id, "Занятие не найдено в расписании.")
                set_user_state(message.chat.id, EDIT_SCHEDULE)

@bot.callback_query_handler(func=lambda callback: callback.data in ['confirm_cancel_yes', 'confirm_cancel_no'])
def confirm_lesson_cancel(callback):
    date = user_states[callback.message.chat.id]['date']
    time = user_states[callback.message.chat.id]['time']

    if callback.data == 'confirm_cancel_yes':
        with DB_connect() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT id FROM session 
                    WHERE date = %s AND start_time = %s AND instructor_id = (
                        SELECT i.id FROM instructor i
                        JOIN users u ON u.id = i.id_user
                        WHERE u.phone_number = %s
                    )
                ''', (date, time, user_states[callback.message.chat.id]['phone']))
                session = cur.fetchone()
                if session:
                    session_id = session[0]
                    cur.execute('''
                        UPDATE session SET status = 'canceled' WHERE id = %s
                    ''', (session_id,))
                    cur.execute('''
                        UPDATE student SET hours=hours+1
	                        WHERE id=(SELECT b.student_id FROM booking b WHERE b.session_id=%s AND b.status='booked')
                    ''', (session_id, ))

                    cur.execute('''
                        UPDATE booking SET status = 'canceled' WHERE session_id = %s
                    ''', (session_id,))

                    conn.commit()
                    bot.send_message(callback.message.chat.id, "Занятие успешно отменено.")
                    notify_student_about_lesson_cancel(session_id)
                    remove_notification_from_schedule(session_id)

                else:
                    bot.send_message(callback.message.chat.id, "Занятие не найдено.")
        set_user_state(callback.message.chat.id, EDIT_SCHEDULE)

        set_user_state(callback.message.chat.id, EDIT_SCHEDULE)
    if callback.data == 'confirm_cancel_no':
        bot.send_message(callback.message.chat.id, "Расписание оставлено без изменений.")
        set_user_state(callback.message.chat.id, EDIT_SCHEDULE)

@bot.message_handler(func=lambda message: message.text=='Главное меню' and get_user_state(message.chat.id) == EDIT_SCHEDULE)
def back_instructor_menu(message):
    set_user_state(message.chat.id, INSTRUCTOR_MENU)
    instructor_menu(message.chat.id)


@bot.message_handler(func=lambda message: message.text == 'Календарь расписания' and get_user_state(message.chat.id) == INSTRUCTOR_MENU)
def instructor_show_calendar(message):
    today = date.today()
    show_calendar_message(bot, message.chat.id, today.year, today.month)
    set_user_state(message.chat.id, INSTRUCTOR_MENU)

@bot.callback_query_handler(func=lambda callback: (callback.data.startswith("month_") or callback.data.startswith("date_")) and get_user_state(callback.message.chat.id)==INSTRUCTOR_MENU )
def handle_calendar_navigation_callback(callback):

    if callback.data.startswith("month_"):
        handle_calendar_navigation(callback, bot)
    elif callback.data.startswith("date_") and get_user_state(callback.message.chat.id)==INSTRUCTOR_MENU:
        date_selected = handle_calendar_navigation(callback, bot)

        with DB_connect() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                        SELECT 
                            s.start_time, 
                            s.end_time, 
                            COALESCE(u.full_name, 'Свободно') AS student_full_name, 
                            s.status,
                            b.status
                        FROM 
                            session s
                        LEFT JOIN 
                            booking b ON s.id = b.session_id
                        LEFT JOIN 
                            student st ON b.student_id = st.id
                        LEFT JOIN 
                            users u ON st.id_user = u.id
                        WHERE 
                            s.date = %s AND s.instructor_id = (
                                SELECT i.id
                                FROM instructor i
                                JOIN users u2 ON u2.id = i.id_user
                                WHERE u2.phone_number = %s
                            ) AND (s.status='booked' OR s.status='free') 
                        ORDER BY 
                            s.start_time;
                       


                    ''', (date_selected, user_states[callback.message.chat.id]['phone'],))
                schedule = cur.fetchall()



        if schedule:
            response = f"Расписание на {date_selected}:\n"
            for start, end, student, status_session, status_booking in schedule:
                if status_session=='free':
                    response += f"{start}-{end} | Свободно\n"
                elif status_booking=='booked' and status_session=='booked':
                    response += f"{start}-{end} | {student}\n"

        else:
            response = f"На {date_selected} занятий нет."

        bot.send_message(callback.message.chat.id, response)

