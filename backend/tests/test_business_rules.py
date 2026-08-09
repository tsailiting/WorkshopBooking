from app import (
    Reservation,
    WorkshopSession,
    app,
    configure_database,
    db,
    fetch_online_uuid,
    init_db,
    normalize_datetime,
    resolve_user_id,
)
import os
import sys
from datetime import datetime, timedelta, timezone
from tempfile import mkstemp
from threading import Barrier, Thread
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


def create_test_client():
    _, db_path = mkstemp(suffix='.sqlite3')
    configure_database(f'sqlite:///{db_path}')
    with app.app_context():
        db.drop_all()
        init_db()
    return app.test_client()


def create_session_payload(hours_from_now=48, capacity=2):
    start_time = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    return {
        'title': '測試課程',
        'start_time': start_time.isoformat(),
        'duration_minutes': 60,
        'capacity': capacity,
        'price': 1000,
    }


def test_create_session_sets_created_by_admin():
    client = create_test_client()
    response = client.post(
        '/sessions',
        json=create_session_payload(),
        headers={'X-User-Id': '123e4567-e89b-12d3-a456-426614174000'},
    )

    assert response.status_code == 201

    with app.app_context():
        session = db.session.get(WorkshopSession, response.get_json()['id'])
        assert session.created_by == 'admin'


def test_second_reservation_is_waitlisted_when_session_is_full():
    client = create_test_client()
    create_response = client.post('/sessions', json=create_session_payload(capacity=1))
    session_id = create_response.get_json()['id']

    first_response = client.post(
        f'/sessions/{session_id}/reservations',
        json={},
        headers={'X-User-Id': 'user-1'},
    )
    second_response = client.post(
        f'/sessions/{session_id}/reservations',
        json={},
        headers={'X-User-Id': 'user-2'},
    )

    assert first_response.status_code == 201
    assert first_response.get_json()['status'] == 'confirmed'
    assert second_response.status_code == 201
    assert second_response.get_json()['status'] == 'waitlist'


def test_parallel_reservations_respect_capacity_limit():
    client = create_test_client()
    create_response = client.post('/sessions', json=create_session_payload(capacity=1))
    session_id = create_response.get_json()['id']

    barrier = Barrier(2)
    statuses = []
    errors = []

    def reserve_in_thread(user_id):
        try:
            barrier.wait(timeout=5)
            thread_client = app.test_client()
            response = thread_client.post(
                f'/sessions/{session_id}/reservations',
                json={},
                headers={'X-User-Id': user_id},
            )
            statuses.append(response.get_json()['status'])
        except Exception as exc:
            errors.append(exc)

    threads = [
        Thread(target=reserve_in_thread, args=('parallel-user-1',)),
        Thread(target=reserve_in_thread, args=('parallel-user-2',)),
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert sorted(statuses) == ['confirmed', 'waitlist']

    with app.app_context():
        reservations = Reservation.query.filter_by(session_id=session_id).order_by(Reservation.id.asc()).all()
        assert [reservation.status for reservation in reservations] == ['confirmed', 'waitlist']


def test_cancelling_confirmed_reservation_promotes_waitlist():
    client = create_test_client()
    create_response = client.post('/sessions', json=create_session_payload(capacity=1, hours_from_now=72))
    session_id = create_response.get_json()['id']

    first_response = client.post(
        f'/sessions/{session_id}/reservations',
        json={},
        headers={'X-User-Id': 'user-1'},
    )
    second_response = client.post(
        f'/sessions/{session_id}/reservations',
        json={},
        headers={'X-User-Id': 'user-2'},
    )

    cancel_response = client.delete(
        f"/reservations/{first_response.get_json()['reservation_id']}",
        headers={'X-User-Id': 'user-1'},
    )

    assert cancel_response.status_code == 200

    with app.app_context():
        promoted = db.session.get(Reservation, second_response.get_json()['reservation_id'])
        assert promoted.status == 'confirmed'
