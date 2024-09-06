from aiogram import Bot, Dispatcher, types, Router
from aiogram.fsm.storage.base import StorageKey

from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import asyncio
from aiogram import F
from sqlalchemy import select
import aiofiles

from key_bords import support_keyboard, MyCallback
from database import session, Ticket, Base, engine

from dotenv import load_dotenv
import os

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID'))
USERS_FILE = os.getenv('USERS_FILE')

bot = Bot(token=BOT_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

ticket_router = Router()

dp.include_router(ticket_router)


async def write_users_file(user_id: int):
    async with aiofiles.open(USERS_FILE, 'a') as file:
        await file.write(str(user_id) + '\n')


class Support(StatesGroup):
    started = State()
    wait_request = State()
    wait_response = State()


@ticket_router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    if message.chat.id == GROUP_CHAT_ID:
        await message.answer(f"Привет, {message.chat.full_name}! "
                             f"Я - бот техподдержки, буду переправлять вам сообщения от пользователей.")
    else:

        await message.answer(f"Привет, {message.from_user.full_name}! "
                             f"Я - бот техподдержки, ты можешь обратиться ко мне по любым вопросам.",
                             reply_markup=support_keyboard())
        await state.set_state(Support.started)
        await write_users_file(message.from_user.id)


@dp.callback_query(MyCallback.filter(F.foo == "support"))
async def process_callback_button1(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    current_state = await state.get_state()
    if not current_state or current_state == Support.started:
        await bot.send_message(callback_query.from_user.id, 'Напиши текст')
        await state.set_state(Support.wait_request)
    else:
        await bot.send_message(callback_query.from_user.id, 'У вас уже есть открытое обращение в поддержку')


@ticket_router.message(Support.started)
async def get_support_request(message: Message) -> None:
    await message.answer('Если ты хочешь создать обращение в поддержку, пожалуйста, '
                         'начни обращение при помощи кнопки "Написать в поддержку"')


@ticket_router.message(Support.wait_request)
async def get_support_request(message: Message, state: FSMContext) -> None:
    await message.answer('Спасибо за обращение, я вернусь с ответом в течении дня')
    await state.set_state(Support.wait_response)
    new_ticket = Ticket(tg_user_id=message.from_user.id, first_message=message.text)
    session.add(new_ticket)
    await session.commit()
    await bot.send_message(GROUP_CHAT_ID, f"Новое обращение № {new_ticket.id} "
                                          f"от пользователя {message.from_user.full_name}: "
                                          f"\n{message.text}")


@ticket_router.message(Support.wait_response)
async def get_support_request(message: Message) -> None:
    await message.answer('Ваш комментарий по обращению передан в поддержку. В ближайшее время я вернусь с ответом.')
    ticket = await session.execute(select(Ticket).where(Ticket.tg_user_id == message.from_user.id,
                                                        Ticket.activ == 1))
    ticket = ticket.scalars().first()
    await bot.send_message(GROUP_CHAT_ID, f"Комментарий обращения № {ticket.id} "
                                          f"от пользователя {message.from_user.full_name}: "
                                          f"\n{message.text}")
    ticket.following_message += f'пользователь: \n{message.text}\n'
    session.add(ticket)
    await session.commit()


@dp.message((F.chat.id == GROUP_CHAT_ID) & F.reply_to_message)
async def collect_answers(message: Message):
    ticket_id = int(message.reply_to_message.text.split(" ")[3].split(':')[0])
    ticket = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = ticket.scalars().first()

    if message.text.lower() == 'закрыть':
        await bot.send_message(ticket.tg_user_id, 'Обращение закрыто.')
        await bot.send_message(ticket.tg_user_id,f"Привет, {message.from_user.full_name}! "
                             f"Я - бот техподдержки, ты можешь обратиться ко мне по любым вопросам.",
                             reply_markup=support_keyboard())

        ticket.activ = False
        session.add(ticket)
        await session.commit()
        state = FSMContext(storage=storage,
                           key=StorageKey(chat_id=ticket.tg_user_id, user_id=ticket.tg_user_id, bot_id=bot.id))
        await state.set_state(Support.started)
    else:
        await bot.send_message(ticket.tg_user_id, f"Ответ поддержки:\n{message.text}")
        ticket.following_message += f'поддержка: \n{message.text}\n'
        session.add(ticket)
        await session.commit()


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
