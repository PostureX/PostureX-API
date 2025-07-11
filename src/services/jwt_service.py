from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    set_access_cookies,
    set_refresh_cookies
)
from datetime import timedelta

def create_tokens_and_set_cookies(resp, user_id):
    access_token = create_access_token(identity=str(user_id), expires_delta=timedelta(hours=3))
    refresh_token = create_refresh_token(identity=str(user_id))
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp
