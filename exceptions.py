class ApiResponseHomeworkError(Exception):
    """API вернул домашку без необходимых ключей."""

    ...


class InvalidResponse(Exception):
    """API вернул невалидный ответ."""

    ...


class YandexStatusCodeError(Exception):
    """Сервер Яндекса недоступен."""

    ...
