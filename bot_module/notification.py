from telebot import types
from bot_module.database import DB_connect
from bot_module.loader import bot
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta

def notify_student_about_new_slots(instructor_phone_number, text):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT i.id 
                    FROM instructor i 
                        JOIN users u ON u.id=i.id_user 
                            WHERE u.phone_number=%s
            ''', (instructor_phone_number, ))
            instructor_id = cur.fetchone()
            cur.execute('''
                SELECT u.telegram_id
                    FROM users u
                        JOIN student st ON u.id = st.id_user
                             WHERE st.instructor_id=%s
            ''', (instructor_id, ))
            students = cur.fetchall()
            if students:
                for one in students:
                    bot.send_message(one[0], 'Появились новые слоты для записи!\n'+text)

                    cur.execute('''
                        INSERT INTO notification (telegram_id, text, type, date, status) VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s)
                    ''', (one[0], text, 'new_sessions_added', 'sent'))
            conn.commit()

def notify_student_about_lesson_cancel(session_id):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT u.telegram_id, s.date, s.start_time, s.end_time
                    FROM session s 
                        JOIN booking b ON s.id=b.session_id
                        JOIN student st ON st.id=b.student_id
                        JOIN users u ON u.id=st.id_user 
                            WHERE s.id = %s
            ''', (session_id, ))
            student = cur.fetchone()
            if student:
                start_time_formatted = student[2].strftime('%H:%M')
                end_time_formatted = student[3].strftime('%H:%M')
                text = f'Занятие на {student[1]} {start_time_formatted}-{end_time_formatted} отменено.'
                bot.send_message(student[0], text)
                cur.execute('''
                            INSERT INTO notification (telegram_id, text, type, date, status) VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s)
                ''', (student[0], text, 'session_canceled', 'sent'))
                conn.commit()

def add_notification_to_schedle(booking_id):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT s.date, s.start_time, u.telegram_id
                    FROM session s
                        JOIN booking b ON b.session_id = s.id
                        JOIN student st ON st.id = b.student_id
                        JOIN users u ON u.id = st.id_user
                            WHERE b.id = %s
                        ''', (booking_id,))
            session_info = cur.fetchone()

            if session_info:
                session_date = session_info[0]
                start_time = session_info[1]
                student_telegram_id = session_info[2]

                session_datetime = datetime.combine(session_date, start_time)
                notification_time = session_datetime - timedelta(hours=24)
                text = f'Напоминаем вам, что ваше занятие с инструктором состоится {session_date} в {start_time}.'
                cur.execute('''
                                INSERT INTO notification (telegram_id, text, type, date, status)
                                VALUES (%s, %s, %s, %s, %s)
                            ''', (student_telegram_id, text, 'session_reminder', notification_time, 'waiting'))

            conn.commit()




def remove_notification_from_schedule(session_id):
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                            SELECT s.date, s.start_time
                            FROM session s
                            WHERE s.id = %s
                        ''', (session_id,))
            session_info = cur.fetchone()

            if session_info:
                session_date = session_info[0]
                start_time = session_info[1]
                session_datetime = datetime.combine(session_date, start_time)
                notification_time = session_datetime - timedelta(hours=24)
                cur.execute('''
                                UPDATE notification
                                SET status = 'canceled'
                                WHERE telegram_id IN (
                                    SELECT u.telegram_id
                                    FROM session s
                                    JOIN booking b ON s.id = b.session_id
                                    JOIN student st ON b.student_id = st.id
                                    JOIN users u ON u.id = st.id_user
                                    WHERE s.id = %s
                                )
                                AND status = 'waiting'
                                AND date <= %s  
                            ''', (session_id, notification_time))

                conn.commit()


def notify_student_about_up_coming_soon_lesson():
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT id, telegram_id, text
                FROM notification
                WHERE status = 'waiting' AND date<=CURRENT_TIMESTAMP
            ''')
            notifications = cur.fetchall()
            for notification in notifications:
                notification_id, telegram_id, text = notification
                bot.send_message(telegram_id, text)
                cur.execute('''
                    UPDATE notification
                        SET status = 'sent'
                            WHERE id = %s
                ''', (notification_id,))

            conn.commit()

