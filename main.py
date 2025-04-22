import telebot
import config
from bot_module.database import DB_init
import bot_module
from bot_module.loader import bot

if __name__=="__main__":
    DB_init()
    bot.polling(none_stop = True)