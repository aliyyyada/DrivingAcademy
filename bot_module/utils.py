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



def format_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")

def format_time(t: time) -> str:
    return t.strftime("%H:%M")

def format_datetime(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")
