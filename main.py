import telebot
import config
from bot_module.database import DB_init
import bot_module
from bot_module.loader import bot
from bot_module.scheduler import start_scheduler

if __name__=="__main__":
    start_scheduler()
    DB_init()
    bot.polling(none_stop = True)
