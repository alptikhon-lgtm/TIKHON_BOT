import telebot
import requests
from datetime import datetime
from flask import Flask, render_template_string
import os
import threading
import time
import sys

TOKEN = "8565116421:AAFVGEG0a-gbFtmQaWovh4Hv2tCHc_VAsdc"
bot = telebot.TeleBot(TOKEN)
DEEPSEEK_API_KEY = "sk-00c783ad1fd84101bac89a5c0f5ae453"


# Экономия токенов

MAX_TOKENS = 300 #больше токенов больше ответ
API_URL = "https://api.deepseek.com/v1/chat/completions"

#потом заменить на базу
user_usage = {}

#Проверка лимитов. Увеличивает кол-во исп. вопросов + 1
def check_daily_limit(user_id):
    """Проверка лимита запросов в день"""
    today = datetime.now().date().isoformat()

    #Впервые зашел в бота
    if user_id not in user_usage:
        user_usage[user_id] = {'date': today, 'count': 1}
        return True
    #Если наступил след. день. сбросить лимит запросов
    if user_usage[user_id]['date'] != today:
        user_usage[user_id] = {'date': today, 'count': 1}
        return True

    #Если лимит исчерпан !!!!!!!
    if user_usage[user_id]['count'] >= 15:  # Максимум 10 вопросов в день
        return False

    user_usage[user_id]['count'] += 1
    return True


#Запрос к DeepSeek API с оптимизацией токенов
def askDeepseek(question):


    # Обрезаем вопрос если слишком длинный
    if len(question) > 300:
        question = question[:300] + "..."

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "Ты полезный помощник. Отвечай максимально кратко и по делу. Ограничь ответ 3-4 предложениями."
            },
            {
                "role": "user",
                "content": question
            }
        ],
        "max_tokens": MAX_TOKENS,  # Экономим токены
        "temperature": 0.7,  # Уменьшил температуру для более предсказуемых ответов
        "stream": False
    }

    try:
        response = requests.post(API_URL, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            print(f"Ошибка API: {response.status_code}, {response.text}")
            return f"Ошибка: {response.status_code}. Попробуйте позже."

    except requests.exceptions.Timeout:
        return "Время ожидания истекло. Попробуйте снова."
    except Exception as e:
        print(f"Ошибка в askDeepseek: {e}")
        return "Произошла ошибка при обработке запроса."



@bot.message_handler(commands=['start'])
def start(message):

    welcome_text = "Привет"
    bot.send_message(message.chat.id, welcome_text)


@bot.message_handler(commands=['ai'])
def deepseekSearch(message):
    """Обработчик команды /ai"""
    user_id = message.from_user.id

    @bot.message_handler(func=lambda message: True)
    def echo_all(message):

        if message.text.startswith('/'):
            return

        bot.reply_to(message, " Используйте команду /ai для вопросов\n\nПример: /ai Как работает нейросеть?")

    # ========== FLASK СЕРВЕР ==========
HTML_TEMPLATE = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Telegram Bot</title>
        <meta http-equiv="refresh" content="300">
        <style>
            body { 
                font-family: Arial, sans-serif; 
                max-width: 800px; 
                margin: 50px auto; 
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                padding: 30px;
                border-radius: 15px;
                backdrop-filter: blur(10px);
            }
            h1 { 
                font-size: 2.5em; 
                margin-bottom: 10px;
            }
            .status {
                padding: 10px;
                margin: 20px 0;
                border-radius: 10px;
                font-weight: bold;
            }
            .online { background: #4CAF50; }
            .stats { 
                background: rgba(255, 255, 255, 0.2); 
                padding: 15px; 
                border-radius: 10px;
                margin: 20px 0;
            }
            .btn {
                display: inline-block;
                padding: 12px 24px;
                background: white;
                color: #667eea;
                text-decoration: none;
                border-radius: 25px;
                font-weight: bold;
                margin: 10px;
                transition: transform 0.3s;
            }
            .btn:hover {
                transform: translateY(-3px);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Telegram Bot</h1>
            <p>Бот работает в режиме polling + Flask</p>

            <div class="status online">
                ✅ СТАТУС: ОНЛАЙН
            </div>

            <div class="stats">
                <p>🕒 Время сервера: {{ time }}</p>
                <p>👤 Пользователей сегодня: {{ users_today }}</p>
                <p>📊 Всего запросов сегодня: {{ total_requests }}</p>
                <p>⏰ Автообновление: каждые 5 минут</p>
            </div>

            <p>
                <a href="https://t.me/{{ bot_username }}" class="btn" target="_blank">
                    💬 Написать боту
                </a>
            </p>
        </div>
    </body>
    </html>
    '''

@app.route('/')
def home():
    today = datetime.now().date().isoformat()
    users_today = len([u for u, data in user_usage.items()
                       if data.get('date') == today])
    total_requests = sum([data.get('count', 0) for u, data in user_usage.items()
                          if data.get('date') == today])

    return render_template_string(HTML_TEMPLATE,
                                  time=datetime.now().strftime("%H:%M:%S"),
                                  users_today=users_today,
                                  total_requests=total_requests,
                                  bot_username=bot.get_me().username if hasattr(bot, '_me') else "Bot"
                                  )


@app.route('/health')
def health():
    return "OK", 200


@app.route('/ping')
def ping():
    """Эндпоинт для пинга чтобы сервер не засыпал"""
    return "PONG", 200


# ========== АВТОПРОБУЖДЕНИЕ ==========
def auto_ping():
    """Автоматически пингует сервер"""
    while True:
        try:
            time.sleep(300)  # 5 минут

            # Пингуем сами себя
            url = os.environ.get('RENDER_EXTERNAL_URL', '')
            if url:
                requests.get(f"{url}/ping", timeout=10)
                print(f"🔄 Автопинг в {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"⚠️ Ошибка автопинга: {e}")


# ========== ЗАПУСК БОТА ==========
def run_bot():
    try:
        bot_info = bot.get_me()
        print(f"✅ Бот: @{bot_info.username}")
    except Exception as e:
        print(f"⚠️ Не удалось получить информацию о боте: {e}")

    restart_count = 0
    while True:
        try:
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=30
            )
        except Exception as e:
            restart_count += 1
            print(f"🔥 Ошибка в боте: {e}")
            print(f"🔄 Перезапуск через 10 секунд...")
            time.sleep(10)

            if restart_count > 5:
                print("⚠️ Много перезапусков, жду 60 секунд...")
                time.sleep(60)


# ========== ЗАПУСК ВСЕГО ПРИЛОЖЕНИЯ ==========
if __name__ == '__main__':
    # Запускаем автопинг
    ping_thread = threading.Thread(target=auto_ping, daemon=True)
    ping_thread.start()
    print("✅ Автопинг запущен")

    # Запускаем бота
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("✅ Бот запущен в фоновом режиме")

    # Запускаем Flask
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Flask запускается на порту: {port}")
    print("=" * 50)

    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        use_reloader=False
    )
