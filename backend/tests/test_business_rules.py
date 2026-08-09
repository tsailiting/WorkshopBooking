from app import normalize_datetime
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


def test_normalize_datetime_adds_timezone():
    naive = datetime(2030, 8, 12, 10, 0)
    aware = normalize_datetime(naive)
    assert aware.tzinfo is not None


def test_future_session_time_is_not_ended():
    future = datetime(2030, 8, 12, 10, 0, tzinfo=timezone.utc)
    assert normalize_datetime(future) > datetime.now(timezone.utc)
