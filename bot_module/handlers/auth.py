from bot_module.handlers.instructor import *
from bot_module.handlers.admin import *
from bot_module.loader import bot
from bot_module.utils import user_states, set_user_state, get_user_state
import bcrypt


@bot.callback_query_handler(func=lambda callback: callback.data in ['auth', 'reg'] )
def auth_callback_message(callback):
    if callback.data in ['auth', 'reg']:
        if callback.data == 'auth':
            bot.send_message(callback.message.chat.id, 'Введите ваш номер телефона для входа.')
            set_user_state(callback.message.chat.id, 'AUTH_PHONE')
        elif callback.data == 'reg':
            bot.send_message(callback.message.chat.id, 'Введите ваш номер телефона для регистрации.')
            set_user_state(callback.message.chat.id, 'REG_PHONE')

@bot.callback_query_handler(func=lambda callback: callback.data in ['reg_student', 'reg_not_student'])
def get_role_callback_meassage(callback):
    if callback.data == 'reg_student':
        user_states[callback.message.chat.id]['role']='student'
    else:
        user_states[callback.message.chat.id]['role']='user'
    user_data = user_states[callback.message.chat.id]
    phone, name, password_hash_str, role = user_data['phone'], user_data['name'], user_data['password'], user_data[
        'role']

    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO users (full_name, password_hash, phone_number, role) VALUES (%s, %s, %s, %s)',
                (name, password_hash_str, phone, role,)
            )
            if role=='student':
                cur.execute(
                    'SELECT * FROM users WHERE phone_number = %s', (phone, )
                )
                user = cur.fetchone()
                user_pk = user[0]
                cur.execute(
                    'INSERT INTO student (id_user) VALUES (%s)', (user_pk, )
                )
            conn.commit()
            keyboard = [[types.InlineKeyboardButton('Вход', callback_data='auth')]]
            markup = types.InlineKeyboardMarkup(keyboard)
            bot.send_message(callback.message.chat.id,
                             'Регистрация завершена успешно! Чтобы продолжить работу, необходимо войти.',
                             reply_markup=markup)
            set_user_state(callback.message.chat.id, AUTHENTICATION)
            del user_states[callback.message.chat.id]

@bot.message_handler(commands=['start'])
def start(message):
    keyboard = [[
        types.InlineKeyboardButton('Регистрация', callback_data='reg'),
        types.InlineKeyboardButton('Вход', callback_data='auth')
    ]]
    markup = types.InlineKeyboardMarkup(keyboard)
    bot.send_message(message.chat.id, 'Добро пожаловать в Академию Вождения!', reply_markup=markup)
    set_user_state(message.chat.id, AUTHENTICATION)



@bot.message_handler(func=lambda message: get_user_state(message.chat.id) == 'REG_PHONE')
def handle_reg_phone(message):
    phone_number = message.text.strip()
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE phone_number = %s', (phone_number, ))
            user = cur.fetchone()
            if user:
                keyboard = [[types.InlineKeyboardButton('Вход', callback_data='auth')]]
                markup = types.InlineKeyboardMarkup(keyboard)
                bot.send_message(message.chat.id, 'Этот номер телефона уже зарегистрирован. Попробуйте войти.', reply_markup=markup)
                set_user_state(message.chat.id, AUTHENTICATION)
            else:
                bot.send_message(message.chat.id, 'Введите ФИО:')
                if message.chat.id not in user_states:
                    user_states[message.chat.id] = {}
                user_states[message.chat.id]['phone'] = phone_number
                set_user_state(message.chat.id, 'REG_NAME')

@bot.message_handler(func=lambda message: get_user_state(message.chat.id) == 'REG_NAME')
def handle_reg_name(message):
    name = message.text.strip()
    user_states[message.chat.id]['name'] = name
    bot.send_message(message.chat.id, 'Введите пароль:')
    set_user_state(message.chat.id, 'REG_PASSWORD')


@bot.message_handler(func=lambda message: get_user_state(message.chat.id) == 'REG_PASSWORD')
def handle_reg_password(message):
    password = message.text.strip()
    #password = password.encode('utf-8')
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    password_hash_str = password_hash.decode('utf-8')
    user_states[message.chat.id]['password'] = password_hash_str

    keyboard = [[
        types.InlineKeyboardButton('Да', callback_data='reg_student'),
        types.InlineKeyboardButton('Нет', callback_data='reg_not_student')
    ]]
    markup = types.InlineKeyboardMarkup(keyboard)
    bot.send_message(message.chat.id, 'Вы являетесь студентом автошколы?', reply_markup=markup)
    set_user_state(message.chat.id, AUTHENTICATION)



@bot.message_handler(func=lambda message: get_user_state(message.chat.id) == 'AUTH_PHONE')
def handle_auth_phone(message):
    phone_number = message.text.strip()
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE phone_number = %s', (phone_number, ))
            user = cur.fetchone()
            if user:
                bot.send_message(message.chat.id, 'Введите пароль:')
                user_states[message.chat.id] = {'state': 'AUTH_PASSWORD', 'phone': phone_number}
            else:
                bot.send_message(message.chat.id, 'Номер телефона не найден. Пожалуйста, зарегистрируйтесь.')
                set_user_state(message.chat.id, AUTHENTICATION)

@bot.message_handler(func=lambda message: get_user_state(message.chat.id) == 'AUTH_PASSWORD')
def handle_auth_password(message):
    password = message.text.strip().encode('utf-8')
    phone_number = user_states[message.chat.id]['phone']
    with DB_connect() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute('SELECT * FROM users WHERE phone_number = %s', (phone_number, ))
            user = cur.fetchone()

            if user:
                password_hashed = user['password_hash'].encode('utf-8')
                if bcrypt.checkpw(password, password_hashed):
                    role = user['role']
                    bot.send_message(message.chat.id, 'Успешный вход!')
                    if role=='student':
                        student_menu(message.chat.id)
                    elif role=='instructor':
                        instructor_menu(message.chat.id)
                    elif role=='admin':
                        admin_menu(message.chat.id)
                    user_states[message.chat.id]['phone'] = phone_number
            else:
                bot.send_message(message.chat.id, 'Неверный пароль.')
            #del user_states[message.chat.id]


