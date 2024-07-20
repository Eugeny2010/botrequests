import vk_api
import threading
import requests
import os
import shutil
import time
from datetime import datetime
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api import VkUpload
import threading

# Ваш токен доступа
TOKEN = 'vk1.a.goTp9VaoSbQd4h8S9r-y2oItpxs1xgekIJZgTI8ga3_tjcQ2oOImL0kZnV2pqrTuRLwPTlDOvPu3LOC8ne8AZIYu0WGGldgDotbwXvX_3rUiLTdW2UCoWNaSZ_h8NBojnlv6BycS5KbeTO8eQZsk5Xp0rDa5Hz79y4w6l7z_NE8e22t7caZToyRCB3xknZePpZk-CKRH09Do9MmZ5VCQIg'

# ID чата администрации (замените на реальный ID чата)
ADMIN_CHAT_ID = 2000000012

questions = [
    "Название страны:",
    "Флаг (пришлите фото, не файл - бот не умеет распознавать файлы):",
    "Герб (пришлите фото, не файл - бот не умеет распознавать файлы):",
    "Территории (название государства/региона, пришлите фото (не файл - бот не умеет распознавать файлы):",
    "Численность населения:", "Государственная религия:", "Валюта:",
    "Форма правления:", "Государственный строй:", "Правитель:", "Столица:",
    "Ссылка на государственное сообщество в ВК:"
]

# Авторизация в VK
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)
upload = VkUpload(vk_session)

# Директория для временного сохранения изображений
TEMP_DIR = "temp_images"

# Создание временной директории, если она не существует
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


# Функция для отправки сообщения с логированием
def send_message(peer_id, message, attachment=None):
    try:
        vk.messages.send(peer_id=peer_id,
                         random_id=get_random_id(),
                         message=message,
                         attachment=attachment)
    except vk_api.exceptions.ApiError as e:
        print(f"Ошибка отправки сообщения: {e}")


# Функция для обработки новых сообщений
def handle_message(event):
    if event.type == VkEventType.MESSAGE_NEW and event.from_user and event.to_me:
        user_id = event.user_id
        if event.text.lower() in ['!начать', '/start', 'начать', 'старт']:
            send_message(
                event.peer_id,
                f"Привет, {get_user_name(user_id)}! Давай начнем заполнять заявку."
            )
            threading.Thread(target=process_application,
                             args=(user_id, )).start()


# Функция для получения имени пользователя по его ID
def get_user_name(user_id):
    user_info = vk.users.get(user_ids=user_id)
    if user_info:
        return f"{user_info[0]['first_name']} {user_info[0]['last_name']}"
    return "Пользователь"


# Функция для обработки заявки
def process_application(user_id):
    application = {
        'user_id': user_id,
        'user_name': get_user_name(user_id),
        'answers': {},
        'attachments': []
    }
    for question in questions:
        send_message(user_id, question)
        answer, attachments = wait_for_message(user_id)
        application['answers'][question] = answer
        if attachments:
            application['attachments'].extend(attachments)
    send_to_admin(application)


# Функция для ожидания ответа пользователя
def wait_for_message(user_id):
    while True:
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.from_user and event.to_me and event.user_id == user_id:
                attachments = download_attachments(event.message_id)
                return event.text, attachments


# Функция для скачивания и сохранения вложений
def download_attachments(message_id):
    try:
        attachment_paths = []
        for attach in vk.messages.getById(
                message_ids=message_id)['items'][0]['attachments']:
            if attach['type'] == 'photo':
                # Определение расширения изображения
                photo_url = max(attach['photo']['sizes'],
                                key=lambda size: size['height'])['url']
                image_format = photo_url.split('.')[-1].split('?')[
                    0]  # Получаем формат из URL

                # Загрузка и сохранение изображения
                response = requests.get(photo_url)
                file_name = f"photo_{message_id}.{image_format}"
                file_path = os.path.join(TEMP_DIR, file_name)
                with open(file_path, 'wb') as file:
                    file.write(response.content)
                attachment_paths.append(file_path)

        return attachment_paths if attachment_paths else None
    except Exception as e:
        print(f"Ошибка при скачивании вложения: {e}")
        return None


# Функция для отправки заявки в чат администрации
def send_to_admin(application):
    user_mention = f"@id{application['user_id']}({application['user_name']})"
    message = f"Новая заявка от {user_mention}:\n"
    for question, answer in application['answers'].items():
        message += f"{question}\n{answer}\n\n"

    attachments = upload_photos(application['attachments'])

    # Отправка сообщения в чат администрации
    send_message(ADMIN_CHAT_ID, message, attachments)

    # Отправка уведомления пользователю
    send_message(
        application['user_id'],
        "Благодарим. Заявка отправлена на рассмотрение. Ожидайте ответа администрации."
    )

    # Удаление временных изображений
    delete_temp_images(application['attachments'])


# Функция для загрузки фотографий в VK и получения ссылок
def upload_photos(attachment_paths):
    try:
        attachments = []
        for path in attachment_paths:
            upload_response = upload.photo_messages(path)
            attachments.append(
                f"photo{upload_response[0]['owner_id']}_{upload_response[0]['id']}"
            )
        return ','.join(attachments) if attachments else None
    except Exception as e:
        print(f"Ошибка при загрузке фотографий: {e}")
        return None


# Функция для удаления временных изображений
def delete_temp_images(attachment_paths):
    try:
        for path in attachment_paths:
            os.remove(path)
    except Exception as e:
        print(f"Ошибка при удалении временных изображений: {e}")


# Функция для вывода текущего времени в консоль каждые 5 минут
def print_current_time():
    while True:
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        print("Current Time:", current_time)
        time.sleep(300)


# Основной цикл бота
def main():
    # Запуск функции вывода времени в отдельном потоке
    threading.Thread(target=print_current_time, daemon=True).start()

    for event in longpoll.listen():
        handle_message(event)


def keep_alive():
    while True:
        try:
            # Отправляем запрос к VK API, чтобы проверить соединение
            vk.groups.getById(group_id=201784905)
            time.sleep(25 * 60)  # Отправляем запрос каждые 25 минут
        except Exception as e:
            print(f"Ошибка keep-alive: {e}")
            print(traceback.format_exc())
            time.sleep(5)

if __name__ == '__main__':
    # Запускаем поток с keep-alive запросами
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True  # Делаем поток фоновым
    keep_alive_thread.start()

    start_longpoll()
