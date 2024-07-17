import os
import base64
import json

import requests

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from rest_framework_simplejwt.tokens import RefreshToken

from auths.models import MutsaUser
from auths.serializers import KakaoLoginRequestSerializer, UserPatchSerializer, MutsaUserResponseSerializer

class KakaoAccessTokenException(Exception):
    pass

class KakaoOIDCException(Exception):
    pass

class KakaoDataException(Exception):
    pass

def exchange_kakao_access_token(access_code):
    response = requests.post(
        'https://kauth.kakao.com/oauth/token',
        headers={
            'Content-type': 'application/x-www-form-urlencoded;charset=utf-8',
        },
        data={
            'grant_type': 'authorization_code',
            'client_id': os.environ.get('KAKAO_REST_API_KEY'),
            'redirect_uri': os.environ.get('KAKAO_REDIRECT_URI'),
            'code': access_code,
        },
    )
    if response.status_code >= 300:
        raise KakaoAccessTokenException()
    return response.json()

def verify_kakao_oidc(kakao_data):
    if kakao_data.get('id_token', None) is None:
        raise KakaoDataException()
    # todo: implement OIDC verify code here...

def extract_kakao_nickname(kakao_data):
    id_token = kakao_data.get('id_token', None)
    if id_token is None:
        raise KakaoDataException()
    try:
        payload_encoded = id_token.split('.')[1]
        payload_decoded = base64.urlsafe_b64decode(payload_encoded + '=' * (4 - len(payload_encoded) % 4))
        payload = json.loads(payload_decoded)
    except:
        raise KakaoDataException()
    return payload['nickname']

def extract_kakao_sub(kakao_data):
    id_token = kakao_data.get('id_token', None)
    if id_token is None:
        raise KakaoDataException()
    try:
        payload_encoded = id_token.split('.')[1]
        payload_decoded = base64.urlsafe_b64decode(payload_encoded + '=' * (4 - len(payload_encoded) % 4))
        payload = json.loads(payload_decoded)
    except:
        raise KakaoDataException()
    return payload['sub']

@api_view(['POST'])
@permission_classes([AllowAny])
def kakao_login(request):
    serializer = KakaoLoginRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        kakao_data = exchange_kakao_access_token(data['access_code'])
        verify_kakao_oidc(kakao_data)
        nickname = extract_kakao_nickname(kakao_data)
        sub = extract_kakao_sub(kakao_data)
    except KakaoAccessTokenException:
        return Response({'detail': 'Access token 교환에 실패했습니다.'}, status=401)
    except KakaoDataException:
        return Response({'detail': 'OIDC token 정보를 확인할 수 없습니다.'}, status=401)
    except KakaoOIDCException:
        return Response({'detail': 'OIDC 인증에 실패했습니다.'}, status=401)

    try:
        user = MutsaUser.objects.get(kakao_sub=sub)
    except MutsaUser.DoesNotExist:
        user = MutsaUser.objects.create_user(nickname=nickname, description="안녕하세요!", kakao_sub=sub)

    refresh = RefreshToken.for_user(user)
    return Response({
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh)
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify(request):
    return Response({'datail': 'Token is verified.'}, status=200)

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_detail(request):
    if request.method == 'GET':
        users = MutsaUser.objects.all()
        serializer = MutsaUserResponseSerializer(users, many=True)
        return Response(serializer.data)
    elif request.method == 'PATCH':
        user = MutsaUser.objects.get(nickname=request.user.nickname)
        
        patchSerializer = UserPatchSerializer(data=request.data)
        patchSerializer.is_valid(raise_exception=True)
        data = patchSerializer.validated_data
        
        user.description = data['description']
        user.save()
        
        serializer = MutsaUserResponseSerializer(user)
        return Response(serializer.data)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_my_detail(request):
    serializer = MutsaUserResponseSerializer(request.user)
    return Response(serializer.data)