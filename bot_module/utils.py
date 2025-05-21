from bot_module.states import AUTHENTICATION
from bot_module.database import DB_connect
from datetime import datetime, date, time
user_states = {}

def set_user_state(user_id, state):
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id]['state'] = state

def get_user_state(user_id):
    return user_states.get(user_id, {}).get('state', AUTHENTICATION)

def format_date(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%d.%m.%Y")

def format_time(time_str: str) -> str:
    dt = datetime.strptime(time_str, "%H:%M:%S")
    return dt.strftime("%H:%M")
