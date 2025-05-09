from bot_module.states import AUTHENTICATION
from bot_module.database import DB_connect
user_states = {}

def set_user_state(user_id, state):
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id]['state'] = state

def get_user_state(user_id):
    return user_states.get(user_id, {}).get('state', AUTHENTICATION)

