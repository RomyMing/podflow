from src.core.provider_errors import classify_provider_error, pause_for_provider_error
from src.pipeline.context import TaskStage


def test_dashscope_arrearage_is_billing_pause():
    info = classify_provider_error("DashScope failed: Arrearage - account is in arrears", "dashscope")

    assert info is not None
    assert info.reason_code == "provider_billing_required"
    assert info.provider_error_code == "Arrearage"


def test_invalid_key_is_user_fixable_pause():
    info = classify_provider_error("InvalidApiKey: check your API key", "openai")

    assert info is not None
    assert info.reason_code == "provider_invalid_api_key"


def test_regular_pipeline_error_is_not_provider_pause():
    assert classify_provider_error("ffmpeg failed to decode audio", "dashscope") is None


def test_dashscope_websocket_timeout_is_unavailable_pause():
    # The exact failure that hard-failed a real task and restarted the whole pipeline.
    info = classify_provider_error(
        "websocket connection could not established within 5s. Please check your network "
        "connection, firewall settings, or server status.",
        "dashscope",
    )
    assert info is not None
    assert info.reason_code == "provider_unavailable"


def test_ssl_eof_is_unavailable_pause():
    info = classify_provider_error(
        "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol",
        "dashscope",
    )
    assert info is not None
    assert info.reason_code == "provider_unavailable"


def test_connection_refused_is_unavailable_pause():
    info = classify_provider_error("HTTPSConnectionPool: Max retries exceeded (Connection refused)", "elevenlabs")
    assert info is not None
    assert info.reason_code == "provider_unavailable"


def test_billing_error_takes_priority_over_generic_timeout_wording():
    # Specific billing markers are listed before connectivity markers, so they win.
    info = classify_provider_error("Arrearage: request timed out due to overdue bill", "dashscope")
    assert info is not None
    assert info.reason_code == "provider_billing_required"


def test_pause_for_provider_error_excludes_transient_when_requested():
    # In-loop callers pass include_transient=False so connectivity errors keep retrying.
    exc = TimeoutError("websocket connection could not established within 5s")
    assert (
        pause_for_provider_error(
            exc, provider="dashscope", stage=TaskStage.SYNTHESIZING,
            prefix="x", include_transient=False,
        )
        is None
    )
    # After retries are exhausted (default), the same error pauses.
    paused = pause_for_provider_error(exc, provider="dashscope", stage=TaskStage.SYNTHESIZING, prefix="x")
    assert paused is not None
    assert paused.reason_code == "provider_unavailable"


def test_pause_for_provider_error_still_pauses_permanent_errors_in_loop():
    # Permanent problems pause immediately even with include_transient=False.
    paused = pause_for_provider_error(
        "Arrearage: account in arrears", provider="dashscope", stage=TaskStage.SYNTHESIZING,
        prefix="x", include_transient=False,
    )
    assert paused is not None
    assert paused.reason_code == "provider_billing_required"
