class ApiResponseHomeworkError(Exception):
    """API вернул домашку c ошибкой."""

    ...


class EmptyAPIResponse(Exception):
    """API вернул невалидный ответ."""

    ...


class YandexStatusCodeError(Exception):
    """Сервер Яндекса недоступен."""

    ...
