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

def update_phone_number(user_id):
    if 'phone' not in user_states[user_id] or user_states[user_id]['phone'] == None:
        with DB_connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT phone_number FROM users WHERE telegram_id = %s', (str(user_id),))
                result = cur.fetchone()
                phone = result[0] if result else None
                user_states[user_id]['phone'] = phone

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
    #user_states[user_id]['state'] = INSTRUCTOR_MENU
    print(user_id)


@bot.message_handler(func=lambda message: message.text == 'Список курсантов' and get_user_state(message.chat.id)==INSTRUCTOR_MENU)
def handle_instructor_menu_student_list(message):
    update_phone_number(message.chat.id)
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
    update_phone_number(message.chat.id)
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
    #user_states[message.chat.id]['state']=EDIT_SCHEDULE

@bot.message_handler(func=lambda message: message.text == 'Добавить расписание (txt файл)' and get_user_state(message.chat.id) == EDIT_SCHEDULE)
def handle_instructor_menu_edit_schedule_add_txt(message):
    bot.send_message(message.chat.id, 'Отправьте txt файл с расписанием в формате *ДД.ММ.ГГ ЧЧ:ММ-ЧЧ:ММ*')
    set_user_state(message.chat.id, WAITING_TXT_FILE)
    #user_states[message.chat.id]['state'] = WAITING_TXT_FILE

@bot.message_handler(content_types=['document'],  func=lambda message: get_user_state(message.chat.id) == WAITING_TXT_FILE )
def handle_instructor_menu_edit_schedule_add_txt_recive(message):
    file_id = message.document.file_id
    file_info = bot.get_file(file_id)
    download_file = bot.download_file(file_info.file_path)
    mess = download_file.decode('utf-8')
    schedule_entries = mess.strip().split('\n')

    update_phone_number(message.chat.id)
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
                    cur.execute('''
                        SELECT 1 FROM session
                        WHERE instructor_id = %s AND date = %s AND start_time = %s
                        AND status IN ('free', 'booked')
                    ''', (instructor_id, date_str, start_time))
                    exists = cur.fetchone()

                    if exists:
                        bot.send_message(message.chat.id, f'На {date_str} {start_time} уже есть активное занятие, пропущено.')
                    else: cur.execute(
                        'INSERT INTO session (instructor_id,  date, start_time, end_time, status) VALUES (%s,  %s, %s, %s, %s)',
                        (instructor_id, date_str, start_time, end_time, 'free')
                    )
                except Exception as e:
                    bot.send_message(message.chat.id, f'Ошибка при добавлении записи в БД {i}: {e}')

            conn.commit()
            bot.send_message(message.chat.id, 'Расписание успешно добавлено!')
            notify_student_about_new_slots(user_states[message.chat.id]['phone'], mess)
        set_user_state(message.chat.id, EDIT_SCHEDULE)
        #user_states[message.chat.id]['state'] = EDIT_SCHEDULE

@bot.message_handler(func=lambda message: message.text == 'Добавить расписание (сообщение)' and get_user_state(message.chat.id) == EDIT_SCHEDULE)
def handle__instructor_menu_edit_schedule_add_message(message):
    bot.send_message(message.chat.id, 'Отправьте расписание в формате *ДД.ММ.ГГ ЧЧ:ММ-ЧЧ:ММ*')
    set_user_state(message.chat.id, WAITING_TEXT_SCHEDULE)
    #user_states[message.chat.id]['state'] = WAITING_TEXT_SCHEDULE

@bot.message_handler(func=lambda message: get_user_state(message.chat.id) == WAITING_TEXT_SCHEDULE)
def handle_received_text_schedule(message):
    mess = message.text
    schedule_entries = mess.strip().split("\n")

    update_phone_number(message.chat.id)
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
                    cur.execute('''
                        SELECT 1 FROM session
                        WHERE instructor_id = %s AND date = %s AND start_time = %s
                        AND status IN ('free', 'booked')
                    ''', (instructor_id, date_str, start_time))
                    exists = cur.fetchone()

                    if exists:
                        bot.send_message(message.chat.id,f'На {date_str} {start_time} уже есть активное занятие, пропущено.')
                    else:
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



@bot.message_handler(func=lambda message: message.text=='Отменить занятие' and get_user_state(message.chat.id)==EDIT_SCHEDULE)
def show_upcoming_lessons_to_instructor_to_cancel(message):
    update_phone_number(message.chat.id)
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT      s.id,
                            s.date,
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
                        WHERE  s.instructor_id = (
                                SELECT i.id
                                FROM instructor i
                                JOIN users u2 ON u2.id = i.id_user
                                WHERE u2.phone_number = %s
                            ) AND (s.status='booked' OR s.status='free') 
                        ORDER BY s.date,  s.start_time;
            ''', (user_states[message.chat.id]['phone'],))
            sessions= cur.fetchall()
            if sessions:
                markup = types.InlineKeyboardMarkup()
                for session in sessions:
                    s_id=session[0]
                    s_date = session[1]
                    s_start=session[2]
                    s_end=session[3]
                    s_student = session[4]
                    s_status=session[5]
                    b_status=session[6]
                    if s_status == 'free':
                        btn_text = f"{s_date} {s_start}-{s_end} | Свободно\n"
                    elif b_status == 'booked' and s_status == 'booked':
                        btn_text= f"{s_date} {s_start}-{s_end} | {s_student}\n"
                    markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'cancel_session_{s_id}'))
                mes = bot.send_message(message.chat.id, 'Выберите занятие для отмены.', reply_markup=markup)
                user_states[message.chat.id]['instructor_cancel_lesson_mess1']=mes.message_id
            else:
                bot.send_message(message.chat.id, 'У вас нет предстоящих занятий для отмены.')


@bot.callback_query_handler(func=lambda callback: callback.data.startswith('cancel_session_'))
def confirm_cancel_session(callback):
    session_id = callback.data.split('_')[2]
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT s.date, s.start_time, s.end_time
                FROM session s
                WHERE s.id = %s
            ''', (session_id,))
            session = cur.fetchone()

            if session:
                session_date = session[0]
                session_start = session[1]
                session_end = session[2]

                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("Да", callback_data=f"confirm_cancel_yes_{session_id}"))
                markup.add(types.InlineKeyboardButton("Нет", callback_data=f"confirm_cancel_no_{session_id}"))

                mes = bot.send_message(callback.message.chat.id,
                                 f"Вы уверены, что хотите отменить занятие на {session_date} {session_start}-{session_end}?",
                                 reply_markup=markup)
                user_states[callback.message.chat.id]['instructor_cancel_lesson_mess2']=mes.message_id
            else:
                bot.send_message(callback.message.chat.id, "Занятие не найдено.")
                set_user_state(callback.message.chat.id, EDIT_SCHEDULE)

@bot.callback_query_handler(func=lambda callback: callback.data.startswith('confirm_cancel_yes_'))
def cancel_session(callback):
    session_id = callback.data.split('_')[3]
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE session SET status = 'canceled' WHERE id = %s
            ''', (session_id,))
            cur.execute('''
                UPDATE booking SET status = 'canceled' WHERE session_id = %s
            ''', (session_id,))

            cur.execute('''
                UPDATE student SET hours = hours + 1
                WHERE id = (SELECT student_id FROM booking WHERE session_id = %s)
            ''', (session_id,))

            conn.commit()
            bot.edit_message_reply_markup(callback.message.chat.id, user_states[callback.message.chat.id]['instructor_cancel_lesson_mess1'], reply_markup=None)
            bot.edit_message_reply_markup(callback.message.chat.id, user_states[callback.message.chat.id]['instructor_cancel_lesson_mess2'], reply_markup=None)
            bot.send_message(callback.message.chat.id, "Занятие успешно отменено.")
            set_user_state(callback.message.chat.id, EDIT_SCHEDULE)


@bot.callback_query_handler(func=lambda callback: callback.data.startswith('confirm_cancel_no_'))
def cancel_no_session(callback):
    bot.send_message(callback.message.chat.id, "Расписание оставлено без изменений.")
    set_user_state(callback.message.chat.id, EDIT_SCHEDULE)



@bot.message_handler(func=lambda message: message.text=='Главное меню' and get_user_state(message.chat.id) == EDIT_SCHEDULE)
def back_instructor_menu(message):
    set_user_state(message.chat.id, INSTRUCTOR_MENU)
    #user_states[message.chat.id]['state'] = INSTRUCTOR_MENU
    instructor_menu(message.chat.id)


@bot.message_handler(func=lambda message: message.text == 'Календарь расписания' and get_user_state(message.chat.id) == INSTRUCTOR_MENU)
def instructor_show_calendar(message):
    today = date.today()
    print(user_states[message.chat.id]['phone'])
    print(message.chat.id)
    show_calendar_message(bot, message.chat.id, today.year, today.month)
    set_user_state(message.chat.id, INSTRUCTOR_MENU)
    #user_states[message.chat.id]['state']=INSTRUCTOR_MENU


@bot.callback_query_handler(func=lambda callback: (callback.data.startswith("month_") or callback.data.startswith("date_")) and get_user_state(callback.message.chat.id)==INSTRUCTOR_MENU )
def handle_calendar_navigation_callback(callback):
    update_phone_number(callback.message.chat.id)
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

