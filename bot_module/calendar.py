from telebot import types
from datetime import date, timedelta

def generate_calendar(year, month):
    markup = types.InlineKeyboardMarkup()
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    row = [types.InlineKeyboardButton(day, callback_data="ignore") for day in days]
    markup.row(*row)

    first_day = date(year, month, 1)
    start_weekday = first_day.weekday()
    days_in_month = (date(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31

    row = [types.InlineKeyboardButton(" ", callback_data="ignore")] * start_weekday
    for day in range(1, days_in_month + 1):
        row.append(types.InlineKeyboardButton(str(day), callback_data=f"date_{year}_{month}_{day}"))
        if len(row) == 7:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)

    previous_month = month - 1 if month > 1 else 12
    next_month = month + 1 if month < 12 else 1
    previous_year = year - 1 if month == 1 else year
    next_year = year + 1 if month == 12 else year

    markup.row(
        types.InlineKeyboardButton("Назад", callback_data=f"month_{previous_year}_{previous_month}"),
        types.InlineKeyboardButton(f"{month:02}.{year}", callback_data="ignore"),
        types.InlineKeyboardButton("Вперед", callback_data=f"month_{next_year}_{next_month}")
    )
    return markup


def show_calendar_message(bot, chat_id, year, month):
    bot.send_message(chat_id, "Выберите дату:", reply_markup=generate_calendar(year, month))


def handle_calendar_navigation(call, bot):
    if call.data.startswith("month_"):
        _, year, month = call.data.split("_")
        year, month = int(year), int(month)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=generate_calendar(year, month))

    elif call.data.startswith("date_"):
        _, year, month, day = call.data.split("_")
        date_selected = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        return date_selected
