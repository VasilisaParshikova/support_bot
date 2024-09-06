from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData


class MyCallback(CallbackData, prefix="my"):
    foo: str


def support_keyboard():
    support_button = InlineKeyboardButton(
        text="Написать в поддержку", callback_data=MyCallback(foo="support").pack()
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[support_button]])
    return keyboard
