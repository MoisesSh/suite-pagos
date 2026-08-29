from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema
from rest_framework import status, views
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.shared.api.serializers import MensajeRespuestaSerializer
from apps.users.api.cookies import (
    clear_refresh_cookie,
    get_refresh_from_request,
    set_refresh_cookie,
)
from apps.users.api.serializers import LoginSerializer, UsuarioSerializer


class LoginView(views.APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    @extend_schema(
        request=LoginSerializer,
        responses={200: UsuarioSerializer, 401: MensajeRespuestaSerializer},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = authenticate(
            request,
            username=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
        )
        if usuario is None:
            return Response({'error': 'Credenciales inválidas.'}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(usuario)
        # `refresh` NUNCA en el body (auditoría de seguridad, Bloque #16):
        # solo viaja en la cookie HttpOnly — devolverlo también en el JSON
        # anula esa protección a nivel de contrato de API para cualquier
        # consumidor futuro (XSS que lea la respuesta ya tiene el refresh).
        response = Response(
            {
                'access': str(refresh.access_token),
                'usuario': UsuarioSerializer(usuario).data,
            },
        )
        set_refresh_cookie(response, refresh)
        return response


class CookieTokenRefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'refresh'

    def post(self, request, *args, **kwargs):
        refresh_token = get_refresh_from_request(request)
        if not refresh_token:
            return Response({'error': 'No se encontró refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = self.get_serializer(data={'refresh': refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            return Response({'error': 'Refresh token inválido o expirado.'}, status=status.HTTP_401_UNAUTHORIZED)

        nuevo_refresh = serializer.validated_data.pop('refresh', None)
        # Igual que en LoginView: el refresh rotado va solo a la cookie, nunca
        # de vuelta en el body (serializer.validated_data ya sin 'refresh').
        response = Response(serializer.validated_data)
        if nuevo_refresh:
            set_refresh_cookie(response, nuevo_refresh)
        return response


class LogoutView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = get_refresh_from_request(request)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response
