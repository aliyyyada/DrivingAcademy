from telebot import types
from config import token
from bot_module.database import DB_connect
from bot_module.utils import *
from bot_module.states import *
from telebot import TeleBot
from psycopg2.extras import DictCursor
from bot_module.handlers.student import *
from bot_module.loader import bot
#import datetime
from datetime import datetime, date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

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

#TODO: Отправить сообщение студенту о новых слотах
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
    schedule_entries = download_file.decode('utf-8').strip().split('\n')

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
        set_user_state(message.chat.id, EDIT_SCHEDULE)

@bot.message_handler(func=lambda message: message.text == 'Добавить расписание (сообщение)' and get_user_state(message.chat.id) == EDIT_SCHEDULE)
def handle__instructor_menu_edit_schedule_add_message(message):
    bot.send_message(message.chat.id, 'Отправьте расписание в формате *ДД.ММ.ГГ ЧЧ:ММ-ЧЧ:ММ*')
    set_user_state(message.chat.id, WAITING_TEXT_SCHEDULE)

@bot.message_handler(func=lambda message: get_user_state(message.chat.id) == WAITING_TEXT_SCHEDULE)
def handle_received_text_schedule(message):
    schedule_entries = message.text.strip().split("\n")

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
                        UPDATE booking SET status = 'canceled' WHERE session_id = %s
                    ''', (session_id,))

                    conn.commit()
                    bot.send_message(callback.message.chat.id, "Занятие успешно отменено.")
                #TODO: отправить уведомление студенту об отмене занятия
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

def generate_calendar(year, month):
    markup = types.InlineKeyboardMarkup()
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    row = [types.InlineKeyboardButton(day, callback_data="ignore") for day in days]
    markup.row(*row)

    first_day = date(year, month, 1)
    start_weekday = first_day.weekday()
    days_in_month = (date(year, month+1, 1) - timedelta(days=1)).day if month < 12 else 31

    row = [types.InlineKeyboardButton(" ", callback_data="ignore")] * start_weekday
    for day in range(1, days_in_month + 1):
        row.append(types.InlineKeyboardButton(str(day), callback_data=f"date_{year}_{month}_{day}"))
        if len(row) == 7:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)

    previous_month = month - 1 if month > 1 else 12
    next_month = month + 1 if month < 12 else 1
    previous_year = year - 1 if month == 1 else year
    next_year = year + 1 if month == 12 else year

    markup.row(
        types.InlineKeyboardButton("Назад", callback_data=f"month_{previous_year}_{previous_month}"),
        types.InlineKeyboardButton(f"{month:02}.{year}", callback_data="ignore"),
        types.InlineKeyboardButton("Вперед", callback_data=f"month_{next_year}_{next_month}")
    )
    return markup


@bot.message_handler(func=lambda message: message.text == 'Календарь расписания' and get_user_state(message.chat.id) == INSTRUCTOR_MENU)
def show_calendar(message):
    today = date.today()

    bot.send_message(message.chat.id, "Выберите дату:", reply_markup=generate_calendar(today.year, today.month))

@bot.callback_query_handler(func=lambda call: call.data.startswith("month_"))
def change_month(call):
    _, year, month = call.data.split("_")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=generate_calendar(int(year), int(month)))

@bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
def show_schedule(call):
    _, year, month, day = call.data.split("_")
    date_selected = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT s.start_time, s.end_time, u.full_name
                    FROM session s
                        JOIN booking b ON b.session_id = s.id
                        JOIN student st ON b.student_id = st.id
                        JOIN users u ON u.id = st.id_user
                            WHERE s.instructor_id = (
                                SELECT i.id FROM instructor i
                                JOIN users u2 ON i.id_user = u2.id
                                WHERE u2.phone_number = %s
                            ) AND s.date = %s AND b.status = 'booked';


            ''', (user_states[call.message.chat.id]['phone'], date_selected))
            schedule = cur.fetchall()

    if schedule:
        response = f"Расписание на {date_selected}:\n"
        for start, end, student in schedule:
            response += f"{start}-{end} | {student}\n"
    else:
        response = f"На {date_selected} занятий нет."

    bot.send_message(call.message.chat.id, response)


