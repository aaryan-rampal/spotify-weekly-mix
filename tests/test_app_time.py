import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app_time


def test_now_is_eastern_and_aware():
    current = app_time.now()

    assert current.tzinfo is not None
    assert current.tzinfo is app_time.EASTERN
    assert current.utcoffset() is not None


def test_eastern_zone_observes_daylight_saving():
    import datetime

    winter = datetime.datetime(2026, 1, 15, 12, tzinfo=app_time.EASTERN)
    summer = datetime.datetime(2026, 7, 15, 12, tzinfo=app_time.EASTERN)

    # EST is UTC-5, EDT is UTC-4.
    assert winter.utcoffset() == datetime.timedelta(hours=-5)
    assert summer.utcoffset() == datetime.timedelta(hours=-4)
