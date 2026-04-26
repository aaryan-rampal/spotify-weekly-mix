def should_try_generative(
    generative_runtime_ms: int,
    generative_runtime_target_ms: int,
    generative_failed_attempts: int,
    max_generative_failed_attempts: int,
) -> bool:
    """Return whether the next attempt should use Last.fm discovery."""
    return (
        generative_runtime_ms < generative_runtime_target_ms
        and generative_failed_attempts < max_generative_failed_attempts
    )
