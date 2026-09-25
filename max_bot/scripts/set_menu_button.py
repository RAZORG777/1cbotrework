import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")
MAX_API_URL = os.getenv("MAX_API_URL", "https://platform-api.max.ru")

async def set_side_menu_button():
    """Отправляет запрос в MAX для установки глобальной боковой кнопки WebApp"""
    # Предполагаемый эндпоинт MAX для настройки профиля/меню
    url = f"{MAX_API_URL.rstrip('/')}/bot/menu" 
    
    headers = {
        "Authorization": f"{MAX_BOT_TOKEN}", 
        "Content-Type": "application/json"
    }
    
    # Стандартный формат Payload для боковых кнопок WebApp в мессенджерах
    payload = {
        "menu_button": {
            "type": "web_app",
            "text": "Наш сайт 🌐",
            "web_app": {
                "url": "https://yasno-vizhu.com/"
            }
        }
    }
    
    print("⏳ Отправляем запрос на установку боковой кнопки MAX...")
    
    async with httpx.AsyncClient() as client:
        try:
            # Отправляем конфигурацию на сервер MAX
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code in [200, 201]:
                print(f"✅ УСПЕХ! Боковая кнопка установлена. Ответ: {response.text}")
            else:
                print(f"⚠️ Ошибка {response.status_code}: {response.text}")
                print("💡 Вероятно, для MAX это настраивается только вручную в панели dev.max.ru!")
        except Exception as e:
            print(f"❌ Ошибка сети: {e}")

if __name__ == "__main__":
    asyncio.run(set_side_menu_button())