from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from bot_module.database import DB_connect
from bot_module.notification import notify_student_about_up_coming_soon_lesson

def update_completed_lessons():
    with DB_connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE session 
                    SET status = 'completed' 
                    WHERE (date < CURRENT_DATE OR (date = CURRENT_DATE AND end_time < CURRENT_TIME)) 
                    AND status != 'completed';

            ''')

            conn.commit()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_completed_lessons, 'interval', minutes=1)
    scheduler.add_job(notify_student_about_up_coming_soon_lesson, 'interval', minutes=1)
    scheduler.start()