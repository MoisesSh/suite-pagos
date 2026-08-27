from django.conf import settings

_COOKIE = settings.JWT_REFRESH_COOKIE


def set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        _COOKIE['NAME'],
        str(refresh_token),
        httponly=_COOKIE['HTTPONLY'],
        secure=_COOKIE['SECURE'],
        samesite=_COOKIE['SAMESITE'],
        path=_COOKIE['PATH'],
    )


def clear_refresh_cookie(response):
    response.delete_cookie(_COOKIE['NAME'], path=_COOKIE['PATH'])


def get_refresh_from_request(request):
    cookie_value = request.COOKIES.get(_COOKIE['NAME'])
    if cookie_value:
        return cookie_value
    return request.data.get('refresh')
