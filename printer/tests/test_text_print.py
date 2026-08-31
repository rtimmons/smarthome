from __future__ import annotations

import importlib
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import printer_service.presets as presets
from printer_service.text_idempotency import (
    STATE_OUTCOME_UNKNOWN,
    TextPrintIdempotencyStore,
)
from printer_service.text_print import (
    LABEL_MARGIN_PX,
    TextPrintValidationError,
    canonical_request_hash,
    render_text_label,
    validate_text_print_request,
)


FIXED_TIME = datetime(2026, 8, 31, 14, 5, 6, tzinfo=timezone(timedelta(hours=-4)))
BASE_REQUEST = {
    "version": 1,
    "filename": "scorebot-game-42.png",
    "title": "CRIBBAGE",
    "lines": ["RED    121", "BLUE    96", "TURN: RED"],
    "footer": "Printed {{Timestamp}}",
}


@pytest.fixture
def text_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    presets.reset_cached_store()
    monkeypatch.setenv("PRINTER_BACKEND", "file")
    monkeypatch.setenv("PRINTER_OUTPUT_PATH", str(tmp_path / "printer-output.png"))
    monkeypatch.setenv("PRINTED_LABELS_DIR", str(tmp_path / "printed-labels"))
    monkeypatch.setenv(
        "TEXT_PRINT_IDEMPOTENCY_DB", str(tmp_path / "text-print-idempotency.sqlite3")
    )
    monkeypatch.setenv("BROTHER_LABEL", "62")
    app_module = importlib.import_module("printer_service.app")
    app_module = importlib.reload(app_module)
    monkeypatch.setattr(
        app_module,
        "mongo_health",
        lambda: {"configured": False, "ok": True},
    )
    flask_app = app_module.create_app(text_print_clock=lambda: FIXED_TIME)
    return app_module, flask_app, tmp_path


def _post(client, key: str, payload: object = BASE_REQUEST):
    return client.post(
        "/text/print",
        json=payload,
        headers={"Idempotency-Key": key},
    )


def test_text_print_renders_archives_dispatches_and_replays_once(
    text_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_module, flask_app, tmp_path = text_environment
    dispatches: list[tuple[int, int]] = []

    def fake_dispatch(image, _config, *, target_spec=None):
        assert target_spec.printable_px == (720, 390)
        dispatches.append(image.size)
        return tmp_path / "printer-output.png"

    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch)
    client = flask_app.test_client()

    first = _post(client, "game-42")
    first_payload = first.get_json()
    assert first.status_code == 200
    assert first_payload["status"] == "sent"
    assert first_payload["idempotency_key"] == "game-42"
    assert first_payload["idempotent_replay"] is False
    assert first_payload["rendered_at"] == FIXED_TIME.isoformat()
    assert first_payload["metrics"]["width_px"] == 720
    assert first_payload["metrics"]["height_px"] == 390
    assert first_payload["printed_label"]["name"] == "scorebot-game-42.png"
    assert first_payload["printed_label"]["print_count"] == 1

    def replay_must_not_render(*_args, **_kwargs):
        raise AssertionError("An idempotent replay must not render again.")

    monkeypatch.setattr(app_module, "render_text_label", replay_must_not_render)
    replay = _post(client, "game-42")
    replay_payload = replay.get_json()

    assert replay.status_code == 200
    assert replay_payload == {**first_payload, "idempotent_replay": True}
    assert dispatches == [(720, 390)]
    assert len(list((tmp_path / "printed-labels").glob("*.png"))) == 1
    assert len(list((tmp_path / "printed-labels").glob("*.json"))) == 1


def test_text_print_success_replays_after_app_reconstruction(
    text_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_module, first_app, _tmp_path = text_environment
    dispatch_count = 0

    def fake_dispatch(*_args, **_kwargs):
        nonlocal dispatch_count
        dispatch_count += 1
        return None

    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch)
    first = _post(first_app.test_client(), "persistent-success")
    assert first.status_code == 200

    second_app = app_module.create_app(text_print_clock=lambda: FIXED_TIME + timedelta(days=1))
    second = _post(second_app.test_client(), "persistent-success")

    assert second.status_code == 200
    assert second.get_json()["idempotent_replay"] is True
    assert second.get_json()["rendered_at"] == FIXED_TIME.isoformat()
    assert dispatch_count == 1


def test_text_print_conflicting_payload_returns_409(text_environment) -> None:
    _app_module, flask_app, _tmp_path = text_environment
    client = flask_app.test_client()
    assert _post(client, "conflict-key").status_code == 200

    conflict_payload = {**BASE_REQUEST, "lines": ["A DIFFERENT SCORE"]}
    conflict = _post(client, "conflict-key", conflict_payload)

    assert conflict.status_code == 409
    assert conflict.get_json()["code"] == "idempotency_conflict"


def test_concurrent_duplicate_is_in_progress_and_never_dispatches_twice(
    text_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_module, flask_app, _tmp_path = text_environment
    dispatch_started = threading.Event()
    permit_dispatch_to_finish = threading.Event()
    dispatch_count = 0
    first_response: list[Any] = []

    def blocked_dispatch(*_args, **_kwargs):
        nonlocal dispatch_count
        dispatch_count += 1
        dispatch_started.set()
        assert permit_dispatch_to_finish.wait(timeout=5)
        return None

    monkeypatch.setattr(app_module, "dispatch_image", blocked_dispatch)

    def send_first_request() -> None:
        with flask_app.test_client() as client:
            first_response.append(_post(client, "concurrent-key"))

    worker = threading.Thread(target=send_first_request)
    worker.start()
    assert dispatch_started.wait(timeout=5)
    duplicate = _post(flask_app.test_client(), "concurrent-key")
    permit_dispatch_to_finish.set()
    worker.join(timeout=5)

    assert duplicate.status_code == 409
    assert duplicate.get_json()["code"] == "in_progress"
    assert len(first_response) == 1
    assert first_response[0].status_code == 200
    assert dispatch_count == 1


def test_printer_failure_is_persisted_as_non_retriable_outcome_unknown(
    text_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_module, flask_app, tmp_path = text_environment
    dispatch_count = 0

    def unavailable_printer(*_args, **_kwargs):
        nonlocal dispatch_count
        dispatch_count += 1
        raise OSError("response lost")

    monkeypatch.setattr(app_module, "dispatch_image", unavailable_printer)
    client = flask_app.test_client()
    first = _post(client, "unknown-key")
    replay = _post(client, "unknown-key")

    assert first.status_code == 503
    assert first.get_json()["code"] == "outcome_unknown"
    assert first.get_json()["idempotent_replay"] is False
    assert replay.status_code == 503
    assert replay.get_json()["code"] == "outcome_unknown"
    assert replay.get_json()["idempotent_replay"] is True
    assert dispatch_count == 1
    assert len(list((tmp_path / "printed-labels").glob("*.png"))) == 1


@pytest.mark.parametrize("was_dispatching", [False, True])
def test_stale_active_operation_becomes_outcome_unknown_on_reconstruction(
    text_environment, monkeypatch: pytest.MonkeyPatch, was_dispatching: bool
) -> None:
    app_module, _flask_app, tmp_path = text_environment
    text_request = validate_text_print_request(BASE_REQUEST)
    payload_hash = canonical_request_hash(text_request)
    store = TextPrintIdempotencyStore(tmp_path / "text-print-idempotency.sqlite3")
    reservation = store.reserve("stale-key", payload_hash, FIXED_TIME.isoformat())
    assert reservation.reserved is True
    if was_dispatching:
        store.mark_dispatching("stale-key", payload_hash)

    dispatched = False

    def must_not_dispatch(*_args, **_kwargs):
        nonlocal dispatched
        dispatched = True

    monkeypatch.setattr(app_module, "dispatch_image", must_not_dispatch)
    reconstructed_app = app_module.create_app(text_print_clock=lambda: FIXED_TIME)
    response = _post(reconstructed_app.test_client(), "stale-key")

    assert response.status_code == 503
    assert response.get_json()["code"] == STATE_OUTCOME_UNKNOWN
    assert response.get_json()["idempotent_replay"] is True
    assert dispatched is False


def test_definite_archive_failure_releases_key_for_safe_retry(
    text_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_module, flask_app, _tmp_path = text_environment
    original_archive = app_module.PrintedLabelStore.archive
    archive_calls = 0
    dispatch_count = 0

    def fail_once(store, *args, **kwargs):
        nonlocal archive_calls
        archive_calls += 1
        if archive_calls == 1:
            raise OSError("disk temporarily unavailable")
        return original_archive(store, *args, **kwargs)

    def fake_dispatch(*_args, **_kwargs):
        nonlocal dispatch_count
        dispatch_count += 1
        return None

    monkeypatch.setattr(app_module.PrintedLabelStore, "archive", fail_once)
    monkeypatch.setattr(app_module, "dispatch_image", fake_dispatch)
    client = flask_app.test_client()

    failed = _post(client, "safe-retry")
    retried = _post(client, "safe-retry")

    assert failed.status_code == 503
    assert failed.get_json()["code"] == "storage_unavailable"
    assert retried.status_code == 200
    assert dispatch_count == 1


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ({"version": 2, "lines": ["A"]}, "version must equal 1"),
        ({"version": True, "lines": ["A"]}, "version must equal 1"),
        ({"version": 1, "lines": []}, "between one and six"),
        ({"version": 1, "lines": ["A"] * 7}, "between one and six"),
        ({"version": 1, "lines": [12]}, "lines[0] must be a string"),
        ({"version": 1, "lines": ["A\nB"]}, "control characters"),
        ({"version": 1, "lines": ["\nA"]}, "control characters"),
        ({"version": 1, "lines": ["{{timestamp}}"]}, "Unknown template variable"),
        ({"version": 1, "lines": ["A"], "surprise": True}, "Unknown request field"),
        ({"version": 1, "lines": ["A" * 257]}, "at most 256"),
        (
            {
                "version": 1,
                "title": "T" * 256,
                "lines": ["L" * 256] * 6,
                "footer": "F" * 200,
            },
            "at most 2,000",
        ),
    ],
)
def test_text_print_rejects_invalid_requests_without_consuming_key(
    text_environment, payload: object, expected_error: str
) -> None:
    _app_module, flask_app, _tmp_path = text_environment
    response = _post(flask_app.test_client(), "reusable-invalid-key", payload)

    assert response.status_code == 400
    assert response.get_json()["code"] == "invalid_request"
    assert expected_error in response.get_json()["error"]


def test_invalid_headers_and_content_type_are_rejected(text_environment) -> None:
    _app_module, flask_app, _tmp_path = text_environment
    client = flask_app.test_client()

    missing_key = client.post("/text/print", json=BASE_REQUEST)
    non_ascii_key = _post(client, "not-ASCII-🙂")
    wrong_content_type = client.post(
        "/text/print",
        data="{}",
        headers={"Idempotency-Key": "plain-text"},
        content_type="text/plain",
    )

    assert missing_key.status_code == 400
    assert "Idempotency-Key header is required" in missing_key.get_json()["error"]
    assert non_ascii_key.status_code == 400
    assert "printable ASCII" in non_ascii_key.get_json()["error"]
    assert wrong_content_type.status_code == 400
    assert wrong_content_type.get_json()["error"] == "Content-Type must be application/json."


def test_validation_trims_edges_preserves_internal_spaces_and_hashes_canonically() -> None:
    first = validate_text_print_request(
        {
            "version": 1,
            "title": "  SCORE  ",
            "lines": ["  RED    121  ", "BLUE    96"],
            "footer": "  {{Time}}  ",
        }
    )
    second = validate_text_print_request(
        {
            "footer": "{{Time}}",
            "lines": ["RED    121", "BLUE    96"],
            "title": "SCORE",
            "version": 1,
        }
    )

    assert first.lines == ("RED    121", "BLUE    96")
    assert first.title == "SCORE"
    assert canonical_request_hash(first) == canonical_request_hash(second)


def test_timestamp_substitution_and_rendering_are_deterministic() -> None:
    text_request = validate_text_print_request(BASE_REQUEST)

    first = render_text_label(text_request, render_time=FIXED_TIME)
    second = render_text_label(text_request, render_time=FIXED_TIME)

    assert first.image.mode == "1"
    assert first.image.size == (720, 390)
    assert first.lines == ("RED    121", "BLUE    96", "TURN: RED")
    assert first.footer == "Printed 2026-08-31 14:05:06 -0400"
    assert first.rendered_at == "2026-08-31T14:05:06-04:00"
    assert first.image.tobytes() == second.image.tobytes()


def test_rendering_rejects_content_that_cannot_fit() -> None:
    text_request = validate_text_print_request({"version": 1, "lines": ["W" * 256]})

    with pytest.raises(TextPrintValidationError, match="cannot fit"):
        render_text_label(text_request, render_time=FIXED_TIME)


def test_blank_ordered_lines_are_valid_and_reserve_vertical_space() -> None:
    text_request = validate_text_print_request({"version": 1, "lines": ["FIRST", "", "THIRD"]})

    rendered = render_text_label(text_request, render_time=FIXED_TIME)

    assert rendered.lines == ("FIRST", "", "THIRD")
    assert rendered.image.size == (720, 390)


def test_text_sections_are_left_aligned_inside_tenth_inch_margins() -> None:
    text_request = validate_text_print_request(
        {
            "version": 1,
            "title": "MMMM",
            "lines": ["MMMM"],
            "footer": "MMMM",
        }
    )

    rendered = render_text_label(text_request, render_time=FIXED_TIME)
    pixels = rendered.image.load()
    assert pixels is not None
    black_rows = [
        y
        for y in range(rendered.image.height)
        if any(pixels[x, y] == 0 for x in range(rendered.image.width))
    ]
    groups: list[list[int]] = []
    for y in black_rows:
        if not groups or y > groups[-1][-1] + 1:
            groups.append([y])
        else:
            groups[-1].append(y)

    assert LABEL_MARGIN_PX == 30
    assert len(groups) == 3
    for group in groups:
        leftmost_ink = min(
            x for y in group for x in range(rendered.image.width) if pixels[x, y] == 0
        )
        # Font side bearings vary by size, but every section starts at the same
        # 30 px layout edge rather than being centered independently.
        assert LABEL_MARGIN_PX <= leftmost_ink <= LABEL_MARGIN_PX + 5
    assert black_rows[0] >= LABEL_MARGIN_PX
    assert black_rows[-1] < rendered.image.height - LABEL_MARGIN_PX


def test_success_retention_is_at_least_30_days_and_uncertain_records_are_indefinite(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "retention.sqlite3"
    payload_hash = "a" * 64
    current_time = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    store = TextPrintIdempotencyStore(db_path, clock=lambda: current_time[0])

    for key, state in (("success-key", "success"), ("unknown-key", "outcome_unknown")):
        store.reserve(key, payload_hash, current_time[0].isoformat())
        store.mark_dispatching(key, payload_hash)
        store.finish(
            key,
            payload_hash,
            state=state,
            http_status=200 if state == "success" else 503,
            response_body={"idempotency_key": key},
        )

    current_time[0] += timedelta(days=30)
    at_thirty_days = TextPrintIdempotencyStore(db_path, clock=lambda: current_time[0])
    at_thirty_days.initialize()
    assert at_thirty_days.lookup("success-key") is not None
    assert at_thirty_days.lookup("unknown-key") is not None

    current_time[0] += timedelta(seconds=1)
    after_thirty_days = TextPrintIdempotencyStore(db_path, clock=lambda: current_time[0])
    after_thirty_days.initialize()
    assert after_thirty_days.lookup("success-key") is None
    assert after_thirty_days.lookup("unknown-key") is not None


def test_success_record_contains_durable_terminal_response(text_environment) -> None:
    _app_module, flask_app, tmp_path = text_environment
    assert _post(flask_app.test_client(), "durable-response").status_code == 200

    with sqlite3.connect(tmp_path / "text-print-idempotency.sqlite3") as connection:
        row = connection.execute(
            """
            SELECT state, rendered_at, archived_label_id, http_status, response_body
            FROM text_print_operations WHERE idempotency_key = ?
            """,
            ("durable-response",),
        ).fetchone()

    assert row is not None
    assert row[0] == "success"
    assert row[1] == FIXED_TIME.isoformat()
    assert row[2]
    assert row[3] == 200
    assert '"idempotent_replay":false' in row[4]
