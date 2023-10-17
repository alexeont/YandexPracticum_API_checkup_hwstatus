from http import HTTPStatus
import logging
from logging.handlers import RotatingFileHandler
import os
import time

import telegram
import requests
from dotenv import load_dotenv

from exceptions import (ApiResponseHomeworkError, EmptyAPIResponse,
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
    format='%(asctime)s [%(levelname)s] %(funcName)s %(lineno)d %(message)s',
    level=logging.DEBUG,
    filename='main.log'
)
logger = logging.getLogger(__name__)
file_handler = RotatingFileHandler(__file__ + '.log', maxBytes=50000000,
                                   backupCount=5, encoding='utf-8')
logger.addHandler(file_handler)
logger.addHandler(logging.StreamHandler())


def check_tokens():
    """Проверка доступности токенов."""
    TOKENS_DATA = (
        (PRACTICUM_TOKEN, 'Токен практикума'),
        (TELEGRAM_TOKEN, 'Телеграм-токен'),
        (TELEGRAM_CHAT_ID, 'ID Телеграм-чата')
    )
    '''Сначала пробовал сделать константой файла, но тесты не принимали'''
    for token, name in TOKENS_DATA:
        if token is None:
            logging.critical(f'Отсутствует {name}')
            raise SystemExit


def send_message(bot, message):
    """Отправка сообщения в ТГ."""
    logging.debug('Отправляем сообщение в ТГ...')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logging.error(f'Ошибка при отправке сообщения в ТГ: {error}')
        return False
    else:
        logging.debug('Сообщение об изменении статуса '
                      'успешно отправлено в ТГ')
        return True


def get_api_answer(timestamp):
    """Получаем ответ от Яндекса."""
    # Сделал так, потому что большинство данных и так константы,
    # словарь как-будто лишний
    params = {'from_date': timestamp}
    request_text = f'URL = {ENDPOINT}, headers = {HEADERS}, params = {params}'
    logging.debug(f'Отправляем запрос Яндексу: {request_text}')
    try:
        homework_response = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params)
        if homework_response.status_code != HTTPStatus.OK:
            raise YandexStatusCodeError
        return homework_response.json()
    except requests.RequestException:
        logging.error(f'Ошибка при отправке запроса: {request_text}')
        raise ConnectionError(f'Ошибка при отправке запроса: {request_text}')


def check_response(response):
    """Проверяем валидность ответа."""
    MESSAGE_FOR_EXCEPTIONS = 'Вернулся не валидный ответ сервера'
    if not isinstance(response, dict):
        raise TypeError(MESSAGE_FOR_EXCEPTIONS)
    if ('homeworks' or 'current_date') not in response.keys():
        logging.error('От сервера вернулся пустой ответ')
        raise EmptyAPIResponse('От сервера вернулся пустой ответ')
    if not isinstance(response['homeworks'], list):
        raise TypeError(MESSAGE_FOR_EXCEPTIONS)
    return response['homeworks']


def parse_status(homework):
    """Возвращаем статус домашки."""
    if 'homework_name' not in homework.keys():
        raise ApiResponseHomeworkError('У домашки нет названия')
    if 'status' not in homework.keys():
        raise ApiResponseHomeworkError('У домашки нет статуса')
    if homework['status'] not in HOMEWORK_VERDICTS.keys():
        raise KeyError('Получен непредусмотренный статус домашки')
    verdict = HOMEWORK_VERDICTS[homework['status']]
    return (f'Изменился статус проверки работы "{homework["homework_name"]}". '
            f'{verdict}')


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    prev_report = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                success_message = parse_status(homework)
                current_report = HOMEWORK_VERDICTS[homework['status']]
            else:
                current_report = 'Статус не был изменен'
            if not current_report == prev_report:
                message_sent = send_message(bot, success_message)
                if message_sent:
                    prev_report = current_report
                    timestamp = response.get('current_date')
            else:
                logging.debug('Статус не был изменен')
        except EmptyAPIResponse as error:
            logging.error(error)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if not message == prev_report:
                bot.send_message(TELEGRAM_CHAT_ID, message)
                prev_report = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
