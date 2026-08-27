from django.urls import path

from apps.users.api.views import CookieTokenRefreshView, LoginView, LogoutView

app_name = 'users'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', CookieTokenRefreshView.as_view(), name='refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
