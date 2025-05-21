from telebot import types
from config import token
from bot_module.database import DB_connect
from bot_module.utils import *
from bot_module.states import *
from telebot import TeleBot
from psycopg2.extras import DictCursor
from bot_module.handlers.student import *
from bot_module.loader import bot

def admin_menu(user_id):
    keyboard = [[
        types.KeyboardButton('Редактировать профиль автоинструктора'),
        types.KeyboardButton('Редактировать профиль студента')],
        [types.KeyboardButton('Список курсантов'),
         types.KeyboardButton('Список пользователей')],
        [types.KeyboardButton('Редактировать права управления')],
    ]

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in keyboard:
        markup.row(*row)
    bot.send_message(user_id, 'Главное меню:', reply_markup=markup)
    set_user_state(user_id, ADMIN_MENU)

@bot.message_handler(func=lambda message: message.text=='Список курсантов' and get_user_state(message.chat.id) == ADMIN_MENU)
def handle_admin_get_student_list(message):
    keyboard = [
        [types.KeyboardButton('Список закрепленных студентов'), types.KeyboardButton('Закрепить студента')],
        [types.KeyboardButton('Список незакрепленных студентов'), types.KeyboardButton('Открепить студента')],
        [types.KeyboardButton('Главное меню')]
    ]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in keyboard:
        markup.row(*row)
    bot.send_message(message.chat.id, 'Меню управления студентами и курсантами:', reply_markup=markup)
    set_user_state(message.chat.id, 'ADMIN_STUDENT_LIST')

@bot.message_handler(func=lambda message: message.text =='Главное меню' and (get_user_state(message.chat.id)=='ADMIN_STUDENT_LIST' or get_user_state(message.chat.id)=='ADMIN_USER_LIST'))
def handler_get_admin_menu(message):
    set_user_state(message.chat.id, ADMIN_MENU)
    admin_menu(message.chat.id)

@bot.message_handler(func=lambda message: message.text=='Список незакрепленных студентов' and get_user_state(message.chat.id)=='ADMIN_STUDENT_LIST')
def handler_admin_untied_students(message):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                '''
                    SELECT u.full_name, u.phone_number 
                        FROM users u
                            JOIN student s ON u.id=s.id_user
                                WHERE s.instructor_id IS NULL AND u.role = 'student'; 
                '''
            )
            students=cur.fetchall()
            if students:
                respone = 'Незакрепленные студенты:'
                temp=f"{'ФИО':<150}{'Номер телефона':<20}\n"
                respone+=temp
                for i, (full_name, phone) in enumerate(students, start=1):
                    respone += f"{full_name:<150}{phone:<20}\n"
                bot.send_message(message.chat.id, respone)
            else:
                bot.send_message(message.chat.id, 'Незакрепленных студентов нет.')

@bot.message_handler(func=lambda message: message.text == 'Список закрепленных студентов' and get_user_state(message.chat.id) == 'ADMIN_STUDENT_LIST')
def handler_admin_tied_students_request(message):
    bot.send_message(message.chat.id, 'Введите ФИО инструктора:')
    bot.register_next_step_handler(message, process_instructor_name)

def process_instructor_name(message):
    instructor_name = message.text.strip()
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT u.full_name, u.phone_number 
                FROM users u
                JOIN student s ON u.id = s.id_user
                JOIN instructor i ON i.id = s.instructor_id
                WHERE i.id = (
                    SELECT id FROM instructor WHERE id_user = (
                        SELECT id FROM users WHERE full_name = %s
                    )
                )

            ''', (instructor_name,))
            students = cur.fetchall()
            if students:
                response = f"Инструктор - {instructor_name}\n\n"
                temp = f"{'ФИО':<150}{'Номер телефона':<20}\n"
                response += temp
                for i, (full_name, phone) in enumerate(students, start=1):
                    response += f"{full_name:<150}{phone:<20}\n"
                bot.send_message(message.chat.id, response)
            else:
                bot.send_message(message.chat.id, 'У данного инструктора нет закрепленных студентов.')

@bot.message_handler(func= lambda message: message.text =='Список пользователей' and get_user_state(message.chat.id)==ADMIN_MENU)
def handle_admin_get_list_of_users(message):
    keyboard = [
        [types.KeyboardButton('Список инструкторов'), types.KeyboardButton('Список администраторов')],
        [types.KeyboardButton('Список пользователей')],
        [types.KeyboardButton('Главное меню')]
    ]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in keyboard:
        markup.row(*row)
    bot.send_message(message.chat.id, 'Получение данных пользоватлей:', reply_markup=markup)
    set_user_state(message.chat.id, 'ADMIN_USER_LIST')

@bot.message_handler(func=lambda message: message.text=='Список инструкторов' and get_user_state(message.chat.id)=='ADMIN_USER_LIST')
def handle_admin_get_list_of_instructors(message):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT full_name, phone_number 
                    FROM users 
                        where role = 'instructor'
            ''')
            instructors= cur.fetchall()
            if instructors:
                mes = 'Список инструкторов\n'
                for instructor in instructors:
                    mes+=f'\n{instructor[0]}({instructor[1]})'
                bot.send_message(message.chat.id, mes)
            else:
                bot.send_message(message.chat.id, 'Отсутствуют списки инструкторов в БД.')

@bot.message_handler(func=lambda message: message.text=='Список администраторов' and get_user_state(message.chat.id)=='ADMIN_USER_LIST')
def handle_admin_get_list_of_admins(message):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT full_name, phone_number 
                    FROM users 
                        where role = 'admin'
            ''')
            admins= cur.fetchall()
            if admins:
                mes = 'Список администраторов\n'
                for admin in admins:
                    mes+=f'\n{admin[0]}({admin[1]})'
                bot.send_message(message.chat.id, mes)
            else:
                bot.send_message(message.chat.id, 'Отсутствуют списки администраторов в БД.')

@bot.message_handler(func=lambda message: message.text=='Список пользователей' and get_user_state(message.chat.id)=='ADMIN_USER_LIST')
def handle_admin_get_list_of_users(message):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT full_name, phone_number 
                    FROM users 
                        where role = 'user'
            ''')
            users= cur.fetchall()
            if users:
                mes = 'Список пользователей\n'
                for user in users:
                    mes+=f'\n{user[0]}({user[1]})'
                bot.send_message(message.chat.id, mes)
            else:
                bot.send_message(message.chat.id, 'Отсутствуют списки пользователей в БД.')

@bot.message_handler(func=lambda message: message.text=='Редактировать профиль автоинструктора' and get_user_state(message.chat.id) == ADMIN_MENU)
def handle_admin_change_instructor_info(message):
    bot.send_message(message.chat.id, 'Введите ФИО автоинструктора, чей профиль Вы хотите изменить.')
    bot.register_next_step_handler(message, change_instructor_info)

def change_instructor_info(message):
    instructor_name = message.text.strip()

    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM users WHERE full_name = %s AND role = %s', (instructor_name, 'instructor'))
            instructor = cur.fetchone()

            if instructor:


                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton('Номер машины', callback_data='edit_car_plate'))
                markup.add(types.InlineKeyboardButton('Модель машины', callback_data='edit_car_model'))
                markup.add(types.InlineKeyboardButton('Цвет машины', callback_data='edit_car_color'))
                markup.add(types.InlineKeyboardButton('Готово', callback_data='done_instructor'))

                mes = bot.send_message(message.chat.id, 'Выберите поле для изменения:', reply_markup=markup)
                mes_id = mes.message_id
                user_states[message.chat.id] = {
                    'state': 'ADMIN_CHANGE_INSTRUCTOR_FIELD',
                    'instructor_name': instructor_name,
                    'instructor_id': instructor[0],
                    'message_id': mes_id
                }

            else:
                bot.send_message(message.chat.id, 'Инструктор с таким ФИО не найден.')
                set_user_state(message.chat.id, ADMIN_MENU)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_car_'))
def process_field_selection(call):
    field_map = {
        'edit_car_plate': 'car_plate',
        'edit_car_model': 'car_model',
        'edit_car_color': 'car_color'
    }

    field_to_edit = field_map[call.data]
    user_states[call.message.chat.id]['field_to_edit'] = field_to_edit
    mes = 'Введите новое значение для поля '
    if field_to_edit=='car_plate':
        mes+='"номер автомобиля":'
    elif field_to_edit=='car_model':
        mes+='"модель автомобиля":'
    elif field_to_edit=='car_color':
        mes+='"цвет автомобиля":'

    bot.send_message(call.message.chat.id, mes)
    bot.register_next_step_handler(call.message, update_instructor_info)

def update_instructor_info(message):
    new_value = message.text.strip()
    instructor_id = user_states[message.chat.id]['instructor_id']
    field_to_edit = user_states[message.chat.id]['field_to_edit']

    with DB_connect() as conn:
        with conn.cursor() as cur:
            query = f'UPDATE instructor SET {field_to_edit} = %s WHERE id_user = %s'
            cur.execute(query, (new_value, instructor_id))
            conn.commit()

    bot.send_message(message.chat.id, f'Поле {field_to_edit} успешно обновлено!')
    set_user_state(message.chat.id, ADMIN_MENU)

@bot.callback_query_handler(func=lambda callback: callback.data=='done_instructor')
def done_with_editing_instructor_info(callback):
    user_id = user_states[callback.message.chat.id]['instructor_id']
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT u.full_name, i.car_plate, i.car_model, i.car_color
                    FROM users u
                        JOIN instructor i ON u.id=i.id_user
                            WHERE u.id=%s
            ''', (user_id, ))
            instructor = cur.fetchone()
            if instructor:
                mes=f'Автоинструктор:\n{instructor[0]}\n\nАвтомобиль:\n{instructor[2]} {instructor[1]}({instructor[3]})'
                bot.send_message(callback.message.chat.id, mes)

    bot.edit_message_reply_markup(callback.message.chat.id, user_states[callback.message.chat.id]['message_id'], reply_markup=None)



@bot.message_handler(func=lambda message: message.text=='Редактировать профиль студента' and get_user_state(message.chat.id) == ADMIN_MENU)
def handle_admin_change_student_info(message):
    bot.send_message(message.chat.id, 'Введите ФИО студента, чей профиль Вы хотите изменить.')
    bot.register_next_step_handler(message, change_student_info)

def change_student_info(message):
    student_name = message.text.strip()

    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM users WHERE full_name = %s AND role = %s', (student_name, 'student'))
            student = cur.fetchone()

            if student:


                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton('Инструктор', callback_data='edit_instructor_of_student'))
                markup.add(types.InlineKeyboardButton('Количество часов обучения', callback_data='edit_study_hours'))
                markup.add(types.InlineKeyboardButton('Готово', callback_data='done_student'))

                mes = bot.send_message(message.chat.id, 'Выберите поле для изменения:', reply_markup=markup)
                mes_id = mes.message_id
                user_states[message.chat.id] = {
                    'state': 'ADMIN_CHANGE_STUDENT_FIELD',
                    'student_name': student_name,
                    'student_id': student[0],
                    'message_id': mes_id
                }

            else:
                bot.send_message(message.chat.id, 'Студент с таким ФИО не найден.')
                set_user_state(message.chat.id, ADMIN_MENU)

@bot.callback_query_handler(func=lambda call: call.data in ['edit_instructor_of_student', 'edit_study_hours'])
def process_field_selection(call):
    field_map = {
        'edit_instructor_of_student': 'instructor_id',
        'edit_study_hours': 'hours'
    }

    field_to_edit = field_map[call.data]
    user_states[call.message.chat.id]['field_to_edit'] = field_to_edit
    mes = 'Введите новое значение для поля '
    if field_to_edit=='instructor_id':
        mes+='"инструктор":'
    elif field_to_edit=='hours':
        mes+='"количество часов обучения":'

    bot.send_message(call.message.chat.id, mes)
    bot.register_next_step_handler(call.message, update_student_info)


def update_student_info(message):
    new_value = message.text.strip()
    student_id = user_states[message.chat.id]['student_id']
    field_to_edit = user_states[message.chat.id]['field_to_edit']

    with DB_connect() as conn:
        with conn.cursor() as cur:
            if field_to_edit == 'instructor_id':
                cur.execute('SELECT id FROM users WHERE full_name = %s AND role = %s', (new_value, 'instructor'))
                user_result = cur.fetchone()

                if user_result:
                    user_id = user_result[0]
                    cur.execute('SELECT id FROM instructor WHERE id_user = %s', (user_id,))
                    instructor_result = cur.fetchone()

                    if instructor_result:
                        instructor_id = instructor_result[0]

                        cur.execute('UPDATE student SET instructor_id = %s WHERE id_user = %s',
                                    (instructor_id, student_id, ))
                        conn.commit()
                        bot.send_message(message.chat.id, 'Инструктор успешно изменён!')
                    else:
                        bot.send_message(message.chat.id, 'Пользователь найден, но не зарегистрирован как инструктор.')
                else:
                    bot.send_message(message.chat.id, 'Инструктор с таким ФИО не найден.')

            elif field_to_edit == 'hours':
                try:
                    hours = int(new_value)
                    if hours < 0:
                        raise ValueError
                    cur.execute('UPDATE student SET hours = %s WHERE id_user = %s', (hours, student_id, ))
                    conn.commit()
                    bot.send_message(message.chat.id, 'Количество часов обучения успешно изменено!')
                except ValueError:
                    bot.send_message(message.chat.id, 'Введите корректное число для часов.')
            else:
                bot.send_message(message.chat.id, 'Неизвестное поле для обновления.')

    set_user_state(message.chat.id, ADMIN_MENU)

@bot.callback_query_handler(func=lambda callback: callback.data=='done_student')
def done_with_editing_instructor_info(callback):
    user_id = user_states[callback.message.chat.id]['student_id']
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT u.full_name, s.instructor_id, s.hours
                    FROM users u
                        JOIN student s ON u.id=s.id_user
                        JOIN instructor i ON s.instructor_id=i.id
                            WHERE u.id=%s
            ''', (user_id, ))
            student = cur.fetchone()
            if student:
                cur.execute('''
                    SELECT u.full_name FROM users u JOIN instructor i ON i.id_user=u.id WHERE i.id= %s
                ''', (student[1], ))
                instuctor_name = cur.fetchone()
                if instuctor_name:
                    mes=f'Студент:\n{student[0]}\n\nАвтоиструктор:\n{instuctor_name[0]}\nКоличество часов обучения: {student[2]}'
                    bot.send_message(callback.message.chat.id, mes)

    bot.edit_message_reply_markup(callback.message.chat.id, user_states[callback.message.chat.id]['message_id'], reply_markup=None)

@bot.message_handler(func=lambda message: message.text=='Редактировать права управления' and get_user_state(message.chat.id) == ADMIN_MENU)
def handle_admin_edit_roles(message):
    bot.send_message(message.chat.id, 'Введите ФИО пользователя, чьи права вы хотите изменить.')
    bot.register_next_step_handler(message, get_user_edit_role)

def get_user_edit_role(message):
    user_name = message.text.strip()
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT telegram_id FROM users WHERE full_name = %s', (user_name,))
            user = cur.fetchone()
            print(user[0], message.chat.id)
            if user:
                target_user_id = user[0]
                if target_user_id == str(message.chat.id):
                    bot.send_message(message.chat.id, 'Вы не можете изменить собственные права.')
                    set_user_state(message.chat.id, ADMIN_MENU)
                    return

                user_states[message.chat.id] = {
                    'state': 'ADMIN_EDIT_ROLE_SELECT',
                    'target_user_id': target_user_id,
                    'target_user_name': user_name
                }

                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton('Администратор', callback_data='admin'),
                    types.InlineKeyboardButton('Автоинструктор', callback_data='instructor'),
                )
                markup.add(
                    types.InlineKeyboardButton('Студент', callback_data='student'),
                    types.InlineKeyboardButton('Пользователь', callback_data='user')
                )

                bot.send_message(message.chat.id, 'Выберите новую роль для пользователя:', reply_markup=markup)
            else:
                bot.send_message(message.chat.id, 'Пользователь с таким ФИО не найден.')

@bot.callback_query_handler(func=lambda callback: callback.data in ['admin', 'instructor', 'student', 'user'])
def edit_role(callback):
    admin_id = callback.message.chat.id
    target_user_id_tg = user_states.get(admin_id, {}).get('target_user_id')
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT id FROM users WHERE telegram_id=%s
            ''', (target_user_id_tg, ))
            target_user_id = cur.fetchone()
    new_role = callback.data
    if not target_user_id:
        bot.send_message(admin_id, 'Ошибка: пользователь не выбран.')
        return

    if target_user_id == admin_id:
        bot.send_message(admin_id, 'Вы не можете изменить собственные права.')
        return

    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT role FROM users WHERE id = %s', (target_user_id,))
            current_role = cur.fetchone()[0]
            cur.execute('UPDATE users SET role = %s WHERE id = %s', (new_role, target_user_id, ))
            if current_role=='instructor':
                cur.execute('DELETE FROM instructor WHERE id_user =%s', (target_user_id,))
            elif current_role=='admin':
                cur.execute('DELETE FROM admin WHERE id_user =%s', (target_user_id,))
            elif current_role=='student':
                cur.execute('DELETE FROM student WHERE id_user =%s', (target_user_id,))

            if new_role=='instructor':
                cur.execute('''
                    INSERT INTO instructor (id_user) VALUES (%s)
                ''', (target_user_id, ))

            elif new_role=='admin':
                cur.execute('''
                     INSERT INTO admin (id_user) VALUES (%s)
                ''', (target_user_id, ))
            elif new_role=='student':
                cur.execute('''
                      INSERT INTO student (id_user) VALUES (%s)
            ''', (target_user_id,))

            conn.commit()

    full_name = user_states.get(admin_id, {}).get('target_user_name', '[неизвестно]')
    bot.send_message(admin_id, f'Роль пользователя "{full_name}" успешно изменена на "{new_role}".')
    set_user_state(admin_id, ADMIN_MENU)

@bot.message_handler(func=lambda message: message.text=='Закрепить студента' and get_user_state(message.chat.id)=='ADMIN_STUDENT_LIST')
def handle_admin_add_student(message):
    bot.send_message(message.chat.id, 'Введите ФИО автоинструктора, за которым Вы хотите закрепить студента.')
    bot.register_next_step_handler(message, get_instructor_name_to_add_student)

def get_instructor_name_to_add_student(message):
    instructor_name=message.text.strip()
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT i.id
                    FROM instructor i
                        JOIN users u ON i.id_user=u.id
                            WHERE u.full_name = %s AND u.role = 'instructor'
            ''', (instructor_name, ))

            instructor = cur.fetchone()
            if instructor:
                instructor_id = instructor[0]
                user_states[message.chat.id]={
                    'instructor_id': instructor_id,
                    'instructor_name': instructor_name
                }
                bot.send_message(message.chat.id, f'Введите ФИО студентов (по одному на строку), которых вы хотите закрепить за {instructor_name}:')
                bot.register_next_step_handler(message, attach_students_to_instructor)
            else:
                bot.send_message(message.chat.id, 'Инструктор с таким ФИО не найден')

def attach_students_to_instructor(message):
    instructor_id = user_states[message.chat.id]['instructor_id']
    instructor_name = user_states[message.chat.id]['instructor_name']
    student_names = [name.strip() for name in message.text.strip().split('\n') if name.strip()]
    success=[]
    failed=[]

    with DB_connect() as conn:
        with conn.cursor() as cur:
            for student_name in student_names:
                cur.execute('''
                    SELECT s.id_user 
                        FROM student s
                            JOIN users u ON u.id=s.id_user
                                WHERE u.full_name = %s
                ''', (student_name, ))
                student = cur.fetchone()
                if student:
                    cur.execute('''
                        UPDATE student SET instructor_id = %s WHERE id_user =%s
                    ''', (instructor_id, student[0],))
                    success.append(student_name)
                else:
                    failed.append(student_name)
            conn.commit()

    result = f'Закреплены за {instructor_name}:\n' + '\n'.join(success) if success else ''
    if failed:
        result += f'\n\nУже закрепленные или не найденные студенты:\n' + '\n'.join(failed)

    bot.send_message(message.chat.id, result)
    set_user_state(message.chat.id, 'ADMIN_STUDENT_LIST')

@bot.message_handler(func=lambda message: message.text=='Открепить студента' and get_user_state(message.chat.id)=='ADMIN_STUDENT_LIST')
def handle_admin_remove_student(message):
    bot.send_message(message.chat.id, 'Введите ФИО автоинструктора, от которого Вы хотите открепить студентов.')
    bot.register_next_step_handler(message, get_instructor_name_to_remove_student)

def get_instructor_name_to_remove_student(message):
    instructor_name=message.text.strip()
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT i.id
                    FROM instructor i
                        JOIN users u ON i.id_user=u.id
                            WHERE u.full_name = %s AND u.role = 'instructor'
            ''', (instructor_name, ))

            instructor = cur.fetchone()
            if instructor:
                user_states[message.chat.id]={
                    'instructor_name': instructor_name
                }
                bot.send_message(message.chat.id, f'Введите ФИО студентов (по одному на строку), которых вы хотите открепить от {instructor_name}:')
                bot.register_next_step_handler(message, remove_students_from_instructor)
            else:
                bot.send_message(message.chat.id, 'Инструктор с таким ФИО не найден')

def remove_students_from_instructor(message):
    instructor_name = user_states[message.chat.id]['instructor_name']
    student_names = [name.strip() for name in message.text.strip().split('\n') if name.strip()]
    success = []
    failed = []

    with DB_connect() as conn:
        with conn.cursor() as cur:
            for student_name in student_names:
                cur.execute('''
                        SELECT s.id_user 
                            FROM student s
                                JOIN users u ON u.id=s.id_user
                                    WHERE u.full_name = %s
                    ''', (student_name, ))
                student = cur.fetchone()
                if student:
                    cur.execute('''
                            UPDATE student SET instructor_id = NULL WHERE id_user =%s
                        ''', (student[0], ))
                    success.append(student_name)
                else:
                    failed.append(student_name)
            conn.commit()

    result = f'Откреплены от {instructor_name}:\n' + '\n'.join(success) if success else ''
    if failed:
        result += f'\n\nНе найдены:\n' + '\n'.join(failed)

    bot.send_message(message.chat.id, result)
    set_user_state(message.chat.id, 'ADMIN_STUDENT_LIST')

