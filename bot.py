import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
WEBAPP_URL2 = os.getenv("WEBAPP_URL2")

if not BOT_TOKEN or not WEBAPP_URL:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Проверьте BOT_TOKEN и WEBAPP_URL в файле .env!")
    exit(1)

# Создаем объекты бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    # Создаем кнопку, которая будет открывать твой Web App
    web_app_btn = KeyboardButton(
        text="🌐Наш сайт", 
        web_app=WebAppInfo(url=WEBAPP_URL2)
    )
    
    # Добавляем кнопку в клавиатуру (которая появится внизу экрана)
    markup = ReplyKeyboardMarkup(
        keyboard=[[web_app_btn]],
        resize_keyboard=True
    )
    
    await message.answer(
        f"Здравствуйте, {message.from_user.first_name}! 👋\n\n"
        "Добро пожаловать в бота нашей клиники. Нажмите кнопку слева, "
        "чтобы выбрать врача, посмотреть свободное время и записаться на прием.",
        reply_markup=markup
    )

async def main():
    print("🤖 Бот успешно запущен и ждет сообщений...")
    # Запускаем бота в режиме polling (он будет постоянно опрашивать сервера ТГ)
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Запускаем асинхронную функцию
    asyncio.run(main())