import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from weekly_mix_selection import should_try_generative


def test_generative_attempts_stop_after_failed_limit():
    assert not should_try_generative(
        generative_runtime_ms=3_000,
        generative_runtime_target_ms=10_000,
        generative_failed_attempts=5,
        max_generative_failed_attempts=5,
    )


def test_generative_attempts_continue_below_failed_limit():
    assert should_try_generative(
        generative_runtime_ms=3_000,
        generative_runtime_target_ms=10_000,
        generative_failed_attempts=4,
        max_generative_failed_attempts=5,
    )
