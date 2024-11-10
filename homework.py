import logging
import os
import requests
import time
import sys

from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger('HomeworkBot')
logger.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def check_tokens():
    """Доступность необходимых переменных окружения."""
    environment_variables = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if not all(environment_variables):
        logger.critical('Отсутствуют обязательные переменные окружения')
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено в Telegram')
    except Exception:
        logger.error('Сбой при отправке сообщения в Telegram')


def get_api_answer(timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            logger.error(f'Код ответа API {response.status_code}')
            raise Exception(f'Код ответа API {response.status_code}')
        return response.json()
    except requests.RequestException as error:
        logger.error(f'Ошибка при запросе к API: {error}')
        raise Exception(f'Ошибка при запросе к API: {error}')
    except ValueError as value_error:
        logger.error(f'Ошибка при обработке JSON: {value_error}')
        raise Exception(f'Ошибка при обработке JSON: {value_error}')


def check_response(response):
    """Соответствие ответа API документации."""
    if not isinstance(response, dict):
        logger.error('Ответ API должен быть словарём')
        raise TypeError('Ответ API должен быть словарём')

    if 'homeworks' not in response:
        logger.error('Ключ "homeworks" отсутствует в ответе API')
        raise KeyError('Ключ "homeworks" отсутствует в ответе API')

    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logger.error('Ключ "homeworks" должен содержать список')
        raise TypeError('Ключ "homeworks" должен содержать список')

    if not homeworks:
        logger.debug('Новых статусов домашних работ нет')

    return homeworks


def parse_status(homework):
    """Статус конкретной домашней работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        logger.error('Ключ "homework_name" отсутствует')
        raise KeyError('Ключ "homework_name" отсутствует')

    status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(status)

    if verdict is None:
        logger.error(f'Неизвестный статус {status}')
        raise ValueError(f'Неизвестный статус {status}')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise SystemExit('Отсутсвуют необходимые переменные окружения.')

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
