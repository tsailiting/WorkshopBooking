from app import app, fetch_online_uuid, normalize_datetime, resolve_user_id
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


def test_normalize_datetime_adds_timezone():
    naive = datetime(2030, 8, 12, 10, 0)
    aware = normalize_datetime(naive)
    assert aware.tzinfo is not None


def test_future_session_time_is_not_ended():
    future = datetime(2030, 8, 12, 10, 0, tzinfo=timezone.utc)
    assert normalize_datetime(future) > datetime.now(timezone.utc)


def test_resolve_user_id_prefers_header_uuid():
    class DummyRequest:
        def __init__(self):
            self.headers = {'X-User-Id': '123e4567-e89b-12d3-a456-426614174000'}
            self._json = {'user_id': '00000000-0000-0000-0000-000000000001'}

        def get_json(self, silent=True):
            return self._json

    request = DummyRequest()
    assert resolve_user_id(request) == '123e4567-e89b-12d3-a456-426614174000'


def test_generate_user_uuid_route_uses_online_generator_result():
    with patch('app.fetch_online_uuid', return_value='99999999-9999-4999-8999-999999999999'):
        client = app.test_client()
        response = client.post('/users/generate')

    assert response.status_code == 200
    assert response.get_json()['user_id'] == '99999999-9999-4999-8999-999999999999'
