import requests

# Замени на адрес, где запущен твой бот (если локально, то оставь так)
URL = "http://127.0.0.1:8000/api/v1/internal/finish-visit"

# Найди в своей базе appointments.db любой appointment_id и вставь сюда
TEST_ID = "fa9267b8-15bc-11f1-a992-18c04ded4182" 

print(f"Отправляем сигнал боту для записи: {TEST_ID}...")

try:
    response = requests.post(URL, json={"appointment_id": TEST_ID})
    print("Код ответа:", response.status_code)
    print("Ответ бота:", response.json())
except Exception as e:
    print("Ошибка соединения:", e)