import json

import labassistant.api_readiness as api
from labassistant.application import AGENT_API_VERSION, ExperimentListing
from labassistant.history import ExperimentRecordNotFoundError


class StubRead:
    def __init__(self, name: str):
        self.name = name

    def to_dict(self):
        return {"name": self.name, "api_version": AGENT_API_VERSION}


def test_all_candidate_reads_produce_deterministic_json_envelopes(monkeypatch):
    monkeypatch.setattr(
        api,
        "list_experiments",
        lambda: (
            ExperimentListing(
                record_id="record-1",
                saved_at="2026-07-15T12:00:00+00:00",
                label="Run 1",
                measurement_count=2,
            ),
        ),
    )
    monkeypatch.setattr(api, "retrieve_history_overview", lambda: StubRead("history"))
    monkeypatch.setattr(
        api, "retrieve_experiment", lambda record_id: StubRead(record_id)
    )
    monkeypatch.setattr(
        api,
        "retrieve_related_context",
        lambda question, **kwargs: StubRead(question),
    )
    monkeypatch.setattr(
        api,
        "retrieve_research_journal",
        lambda **kwargs: StubRead("journal"),
    )

    parameters = {
        "describe_platform": {},
        "describe_agent_access": {},
        "list_experiments": {},
        "retrieve_history_overview": {},
        "retrieve_experiment": {"record_id": "record-1"},
        "retrieve_related_context": {
            "question": "What changed?",
            "tags": ["dls"],
            "limit": 5,
        },
        "retrieve_research_journal": {
            "keyword": "aggregation",
            "tag": "dls",
        },
    }

    assert tuple(parameters) == api.CANDIDATE_READS
    for capability, request in parameters.items():
        result = api.invoke_candidate_read(
            capability,
            request,
            access_granted=True,
        )
        payload = result.to_dict()
        assert payload["ok"] is True
        assert payload["api_version"] == AGENT_API_VERSION
        assert payload["capability"] == capability
        assert json.loads(json.dumps(payload, allow_nan=False)) == payload

    listings = api.invoke_candidate_read(
        "list_experiments", access_granted=True
    ).to_dict()
    assert listings["data"] == {
        "items": [
            {
                "record_id": "record-1",
                "saved_at": "2026-07-15T12:00:00+00:00",
                "label": "Run 1",
                "measurement_count": 2,
                "api_version": AGENT_API_VERSION,
            }
        ],
        "api_version": AGENT_API_VERSION,
    }


def test_candidate_boundary_rejects_access_and_internal_collaborators(monkeypatch):
    denied = api.invoke_candidate_read("retrieve_history_overview")
    assert denied.error.code == api.ACCESS_DENIED
    assert (
        api.invoke_candidate_read(
            "retrieve_history_overview", access_granted="yes"
        ).error.code
        == api.ACCESS_DENIED
    )

    called = False

    def history():
        nonlocal called
        called = True
        return StubRead("history")

    monkeypatch.setattr(api, "retrieve_history_overview", history)
    rejected = api.invoke_candidate_read(
        "retrieve_history_overview",
        {"history_path": "/tmp/foreign.jsonl"},
        access_granted=True,
    )
    assert rejected.error.code == api.INVALID_INPUT
    assert called is False

    rejected = api.invoke_candidate_read(
        "retrieve_related_context",
        {"question": "Why?", "store": object()},
        access_granted=True,
    )
    assert rejected.error.code == api.INVALID_INPUT
    assert "store" in rejected.error.message


def test_candidate_boundary_maps_expected_and_unexpected_failures(monkeypatch):
    unsupported = api.invoke_candidate_read("save_experiment_history")
    assert unsupported.error.code == api.UNSUPPORTED_EVIDENCE

    invalid = api.invoke_candidate_read(
        "retrieve_experiment", {"record_id": ""}, access_granted=True
    )
    assert invalid.error.code == api.INVALID_INPUT
    assert api.invoke_candidate_read(42).error.code == api.INVALID_INPUT
    assert (
        api.invoke_candidate_read(
            "describe_platform", [("path", "/tmp")]
        ).error.code
        == api.INVALID_INPUT
    )

    def missing(record_id):
        raise ExperimentRecordNotFoundError(record_id)

    monkeypatch.setattr(api, "retrieve_experiment", missing)
    missing_result = api.invoke_candidate_read(
        "retrieve_experiment",
        {"record_id": "missing"},
        access_granted=True,
    )
    assert missing_result.error.code == api.NOT_FOUND
    assert "missing" not in missing_result.error.message

    def broken():
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(api, "retrieve_history_overview", broken)
    failure = api.invoke_candidate_read(
        "retrieve_history_overview", access_granted=True
    )
    assert failure.error.code == api.INTERNAL_FAILURE
    assert "secret" not in failure.error.message
    assert json.loads(json.dumps(failure.to_dict())) == failure.to_dict()


def test_error_code_catalog_is_stable_and_complete():
    assert api.ERROR_CODES == (
        "invalid_input",
        "not_found",
        "conflict",
        "unsupported_evidence",
        "access_denied",
        "internal_failure",
    )
