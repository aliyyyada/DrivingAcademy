import psycopg2
from config import DB_host, DB_user, DB_password, DB_name
import bcrypt

def DB_connect():
    try:
        return psycopg2.connect(
            host=DB_host,
            user=DB_user,
            password=DB_password,
            dbname=DB_name
        )
    except Exception as e:
        print(f'DB connection error: {e}')

def DB_init():
    conn = DB_connect()
    if not conn:
        print('DB connection error')
        return
    try:
        with conn.cursor() as cur:
            cur.execute('''
            CREATE TABLE IF NOT EXISTS Users(
                id SERIAL PRIMARY KEY, 
                telegram_id VARCHAR NOT NULL UNIQUE,
                full_name VARCHAR(150) NOT NULL, 
                password_hash VARCHAR NOT NULL, 
                phone_number VARCHAR(11) NOT NULL UNIQUE,
                role VARCHAR CHECK (role IN ('admin', 'student', 'instructor', 'user')) DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS Instructor(
                id SERIAL PRIMARY KEY,
                id_user INT REFERENCES Users(id) ON DELETE CASCADE,
                car_plate VARCHAR(50),
                car_model VARCHAR(50),
                car_color VARCHAR(50)
            );

            CREATE TABLE IF NOT EXISTS Student(
                id SERIAL PRIMARY KEY,
                id_user INT REFERENCES Users(id) ON DELETE CASCADE,
                instructor_id INT REFERENCES Instructor(id) ON DELETE SET NULL,
                hours INT DEFAULT 0 NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS Admin(
                id SERIAL PRIMARY KEY,
                id_user INT REFERENCES Users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Session(
                id SERIAL PRIMARY KEY,
                instructor_id INT NOT NULL REFERENCES Instructor(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                status VARCHAR CHECK (status IN ('free', 'booked', 'canceled', 'completed')) NOT NULL
                
            );
            
            CREATE TABLE IF NOT EXISTS Booking(
                id SERIAL PRIMARY KEY, 
                session_id INT NOT NULL REFERENCES Session(id) ON DELETE CASCADE,
                student_id INT NOT NULL REFERENCES Student(id) ON DELETE CASCADE,
                status VARCHAR CHECK (status IN ('booked', 'canceled'))
                
            );

            CREATE TABLE IF NOT EXISTS Notification(
                id SERIAL PRIMARY KEY,
                telegram_id VARCHAR NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                type VARCHAR CHECK (type IN ('session_reminder', 'session_canceled', 'new_sessions_added')),
                date TIMESTAMP NOT NULL, 
                status VARCHAR CHECK (status IN ('sent', 'waiting', 'canceled'))
            );
            ''')
            password='a'
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            password_hash_str = password_hash.decode('utf-8')
            cur.execute('''
                            INSERT INTO users (telegram_id, full_name, password_hash, phone_number, role)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (phone_number) DO NOTHING;
                        ''', ('admin_telegram_id', 'admin', password_hash_str, 'poznanie', 'admin'))
            cur.execute('''
                SELECT * FROM admin a
                    JOIN users u ON a.id_user = u.id 
                        WHERE u.phone_number=%s
            ''', ('poznanie',))
            admin_test=cur.fetchone()
            if not admin_test:

                cur.execute('''
                    INSERT INTO admin (id_user)
                        SELECT id FROM users WHERE telegram_id = %s
                ''', ('admin_telegram_id',))
            conn.commit()
            print('Инициализация базы данных завершена успешно!')
    except Exception as e:
        print(f'Ошибка при инициализации базы данных: {e}')
    finally:
        conn.close()