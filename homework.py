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
    variables = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for name, value in variables.items():
        if value is None:
            logger.critical(f'Отсутствует переменная окружения: {name}')
            return False
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено в Telegram')
    except Exception:
        logger.error('Сбой при отправке сообщения в Telegram')


class APIError(Exception):
    """Исключение для ошибок запроса к API и обработки ответа."""


def get_api_answer(timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        raise APIError(f'Ошибка при запросе к API: {error}')

    if response.status_code != 200:
        raise APIError(f'Код ответа API {response.status_code}')

    try:
        return response.json()
    except ValueError as value_error:
        raise APIError(f'Ошибка при обработке JSON: {value_error}')


def check_response(response):
    """Соответствие ответа API документации."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API должен быть словарем,'
            f' но получен тип данных: {type(response)}'
        )

    if 'homeworks' not in response:
        raise KeyError('Ключ "homeworks" отсутствует в ответе API')

    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'Ключ "homeworks" должен содержать список'
            f' но содержит: {type(homeworks)}'
        )

    if not homeworks:
        logger.debug('Новых статусов домашних работ нет')

    return homeworks


def parse_status(homework):
    """Статус конкретной домашней работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('Ключ "homework_name" отсутствует')

    status = homework.get('status')
    if not status:
        raise KeyError('Ключ "status" отсутствует')

    verdict = HOMEWORK_VERDICTS.get(status)

    if verdict is None:
        raise ValueError(f'Неизвестный статус {status}')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise SystemExit('Отсутсвуют необходимые переменные окружения.')

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message != last_message:
                    send_message(bot, message)
                    last_message = message
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
            if message != last_message:
                send_message(bot, message)
                last_message = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
