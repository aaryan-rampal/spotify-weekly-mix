"""Shared time handling.

All wall-clock time in this project is expressed in US Eastern time
(``America/New_York``, which follows EST/EDT daylight-saving transitions)
rather than UTC. Import :func:`now` instead of calling
``datetime.datetime.now`` directly so timestamps and ISO-week boundaries are
consistent across the codebase.
"""

import datetime
from zoneinfo import ZoneInfo

# America/New_York observes daylight saving, so this is "EST" in winter and
# "EDT" in summer. The ``tzdata`` package is a dependency so this resolves even
# on slim images without system zoneinfo data.
EASTERN = ZoneInfo("America/New_York")


def now() -> datetime.datetime:
    """Return the current time as a timezone-aware datetime in US Eastern."""
    return datetime.datetime.now(EASTERN)
