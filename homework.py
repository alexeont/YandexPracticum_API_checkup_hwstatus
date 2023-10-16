import logging
from logging.handlers import RotatingFileHandler
import os
import time

import telegram
import requests

from dotenv import load_dotenv

from exceptions import (ApiResponseHomeworkError, InvalidResponse,
                        YandexStatusCodeError)

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

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.DEBUG,
    filename='main.log'
)
logger = logging.getLogger(__name__)
file_handler = RotatingFileHandler('main.log', maxBytes=50000000,
                                   backupCount=5)
logger.addHandler(file_handler)
logger.addHandler(logging.StreamHandler())


def check_tokens():
    """Проверка доступности токенов."""
    for i in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        if i is not None:
            return True
        else:
            return False


def send_message(bot, message):
    """Отправка сообщения в ТГ."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logging.debug('Сообщение об изменении статуса '
                  'успешно отправлено в тг')


def get_api_answer(timestamp):
    """Получаем ответ от Яндекса."""
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params={'from_date': timestamp})
        if homework_statuses.status_code != 200:
            logging.error('Сервер Яндекса недоступен')
            raise YandexStatusCodeError
    except requests.RequestException:
        logging.error('Ошибка на сервере Яндекса')
    else:
        return homework_statuses.json()


def check_response(response):
    """Проверяем валидность ответа."""
    MESSAGE_FOR_EXCEPTIONS = 'Вернулся не валидный ответ сервера'
    if not isinstance(response, dict):
        raise TypeError(MESSAGE_FOR_EXCEPTIONS)
    if ('homeworks' or 'current_date') not in response.keys():
        logging.error(MESSAGE_FOR_EXCEPTIONS)
        raise InvalidResponse(MESSAGE_FOR_EXCEPTIONS)
    if not isinstance(response['homeworks'], list):
        raise TypeError(MESSAGE_FOR_EXCEPTIONS)


def parse_status(homework):
    """Возвращаем статус домашки."""
    homework_name_error_message = 'Нет названия у домашки'
    if 'homework_name' not in homework.keys():
        logging.error(homework_name_error_message)
        raise ApiResponseHomeworkError(homework_name_error_message)
    homework_name = homework['homework_name']
    status_error_message = f'У домашки "{homework_name}" нет статуса'
    if 'status' not in homework.keys():
        logging.error(status_error_message)
        raise ApiResponseHomeworkError(status_error_message)
    unknown_verdict_error_message = 'Пришел неизвестный статус домашки'
    try:
        homework_name = homework['homework_name']
        verdict = HOMEWORK_VERDICTS[homework['status']]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError:
        logging.error(unknown_verdict_error_message)
        raise ApiResponseHomeworkError(unknown_verdict_error_message)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Возникла ошибка при передаче токенов или chat_id')
        raise SystemExit

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if response['homeworks']:
                success_message = parse_status(response['homeworks'][0])
                send_message(bot, success_message)
            else:
                logging.debug('Статус не был изменен')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)
    '''Сначала пробовал поставить time.sleep() перед try,
    чтобы первый запрос бота не возвращал априори неизмененный
    статус, но тесты не приняли. Почему слип должен быть в конце?'''


if __name__ == '__main__':
    main()
