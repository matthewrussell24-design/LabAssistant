import json
from pathlib import Path

import labassistant.api_readiness as api
from labassistant.application import AGENT_API_VERSION, ExperimentListing
from labassistant.history import ExperimentRecordNotFoundError


class StubRead:
    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        return self.payload


HISTORY_ACCESS = api.LocalReadAccessContext(
    subject="local-user",
    client_id="labassistant-ui",
    origin="local",
    scopes=(api.HISTORY_READ,),
)
MEMORY_ACCESS = api.LocalReadAccessContext(
    subject="local-user",
    client_id="labassistant-cli",
    origin="local",
    scopes=(api.MEMORY_READ,),
)

GOLDEN_SHAPE = json.loads(
    (Path(__file__).parent / "fixtures" / "api_contract_shape.json").read_text()
)


def assert_golden_fields(payload, expected):
    for path, fields in expected.items():
        value = payload
        if path:
            for part in path.split("."):
                value = value[part]
        assert sorted(value) == sorted(fields)


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
    monkeypatch.setattr(
        api,
        "retrieve_history_overview",
        lambda: StubRead(
            {
                "summaries": [{"id": index} for index in range(3)],
                "trend_points": [{"id": index} for index in range(4)],
                "api_version": AGENT_API_VERSION,
            }
        ),
    )
    monkeypatch.setattr(
        api,
        "retrieve_experiment",
        lambda record_id: StubRead(
            {
                "record_id": record_id,
                "saved_at": "2026-07-15T12:00:00+00:00",
                "label": "Run 1",
                "measurement_count": 2,
                "api_version": AGENT_API_VERSION,
            }
        ),
    )
    monkeypatch.setattr(
        api,
        "retrieve_related_context",
        lambda question, **kwargs: StubRead(
            {
                "question": question,
                "relevant_experiments": [],
                "relevant_observations": [{"id": 1}],
                "supporting_evidence": [],
                "hypotheses": [],
                "recommendations": [],
                "related_notes": [],
                "source_files": [],
                "missing_information": [],
                "confidence": "Low",
                "caveats": [],
                "api_version": AGENT_API_VERSION,
            }
        ),
    )
    monkeypatch.setattr(
        api,
        "retrieve_research_journal",
        lambda **kwargs: StubRead(
            {
                "keyword": kwargs.get("keyword", ""),
                "tag": kwargs.get("tag", ""),
                "instrument": kwargs.get("instrument", ""),
                "sample": kwargs.get("sample", ""),
                "entries": [
                    {
                        "entry_id": f"entry-{index}",
                        "created_at": "2026-07-15",
                        "title": f"Entry {index}",
                        "experiment_id": None,
                        "instrument": None,
                        "tags": [],
                        "samples": [],
                        "key_observations": [],
                        "hypotheses": [],
                        "recommendations": [],
                        "source_files": [],
                        "notes": ["note"],
                    }
                    for index in range(3)
                ],
                "markdown": "unbounded",
                "api_version": AGENT_API_VERSION,
            }
        ),
    )

    parameters = {
        "describe_platform": {},
        "describe_agent_access": {},
        "list_experiments": {"limit": 1, "offset": 0},
        "retrieve_history_overview": {"limit": 2, "offset": 1},
        "retrieve_experiment": {"record_id": "record-1"},
        "retrieve_related_context": {
            "question": "What changed?",
            "tags": ["dls"],
            "limit": 5,
        },
        "retrieve_research_journal": {
            "keyword": "aggregation",
            "tag": "dls",
            "limit": 2,
            "offset": 1,
        },
    }

    assert tuple(parameters) == api.CANDIDATE_READS
    payloads = {}
    for capability, request in parameters.items():
        access_context = None
        if capability in api.REQUIRED_SCOPES:
            access_context = (
                MEMORY_ACCESS
                if api.REQUIRED_SCOPES[capability] == api.MEMORY_READ
                else HISTORY_ACCESS
            )
        result = api.invoke_candidate_read(
            capability, request, access_context=access_context
        )
        payload = result.to_dict()
        payloads[capability] = payload
        assert payload["ok"] is True
        assert payload["api_version"] == AGENT_API_VERSION
        assert payload["capability"] == capability
        assert json.loads(json.dumps(payload, allow_nan=False)) == payload

    assert set(payloads) == set(GOLDEN_SHAPE["success"])
    for capability, payload in payloads.items():
        assert_golden_fields(payload, GOLDEN_SHAPE["success"][capability])

    listings = api.invoke_candidate_read(
        "list_experiments", {"limit": 1}, access_context=HISTORY_ACCESS
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
        "pagination": {
            "offset": 0,
            "limit": 1,
            "returned": 1,
            "total": 1,
            "has_more": False,
        },
        "api_version": AGENT_API_VERSION,
    }

    history = api.invoke_candidate_read(
        "retrieve_history_overview",
        {"limit": 2, "offset": 1},
        access_context=HISTORY_ACCESS,
    ).data
    assert [item["id"] for item in history["summaries"]] == [1, 2]
    assert history["pagination"]["trend_points"]["has_more"] is True

    journal = api.invoke_candidate_read(
        "retrieve_research_journal",
        {"limit": 2, "offset": 1},
        access_context=MEMORY_ACCESS,
    ).data
    assert [entry["entry_id"] for entry in journal["entries"]] == [
        "entry-1",
        "entry-2",
    ]
    assert "Entry 0" not in journal["markdown"]
    assert journal["pagination"]["total"] == 3

    context = api.invoke_candidate_read(
        "retrieve_related_context",
        {"question": "What changed?", "limit": 5},
        access_context=MEMORY_ACCESS,
    ).data
    assert context["pagination"]["relevant_observations"] == {
        "offset": 0,
        "limit": 5,
        "returned": 1,
        "total": None,
        "has_more": None,
    }
    assert context["pagination"]["caveats"]["has_more"] is False


def test_candidate_boundary_rejects_access_and_internal_collaborators(monkeypatch):
    denied = api.invoke_candidate_read("retrieve_history_overview")
    assert denied.error.code == api.ACCESS_DENIED
    for context in (
        api.LocalReadAccessContext("", "labassistant-ui", "local", (api.HISTORY_READ,)),
        api.LocalReadAccessContext("user", "unknown", "local", (api.HISTORY_READ,)),
        api.LocalReadAccessContext("user", "labassistant-ui", "loopback", (api.HISTORY_READ,)),
        api.LocalReadAccessContext("user", "labassistant-ui", "local", (api.MEMORY_READ,)),
    ):
        assert (
            api.invoke_candidate_read(
                "retrieve_history_overview", access_context=context
            ).error.code
            == api.ACCESS_DENIED
        )

    called = False

    def history():
        nonlocal called
        called = True
        return StubRead({"summaries": [], "trend_points": []})

    monkeypatch.setattr(api, "retrieve_history_overview", history)
    rejected = api.invoke_candidate_read(
        "retrieve_history_overview",
        {"history_path": "/tmp/foreign.jsonl"},
        access_context=HISTORY_ACCESS,
    )
    assert rejected.error.code == api.INVALID_INPUT
    assert called is False

    rejected = api.invoke_candidate_read(
        "retrieve_related_context",
        {"question": "Why?", "store": object()},
        access_context=MEMORY_ACCESS,
    )
    assert rejected.error.code == api.INVALID_INPUT
    assert "store" in rejected.error.message

    for parameters in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        rejected = api.invoke_candidate_read(
            "list_experiments",
            parameters,
            access_context=HISTORY_ACCESS,
        )
        assert rejected.error.code == api.INVALID_INPUT


def test_candidate_boundary_maps_expected_and_unexpected_failures(monkeypatch):
    unsupported = api.invoke_candidate_read("save_experiment_history")
    assert unsupported.error.code == api.UNSUPPORTED_EVIDENCE

    invalid = api.invoke_candidate_read(
        "retrieve_experiment", {"record_id": ""}, access_context=HISTORY_ACCESS
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
        access_context=HISTORY_ACCESS,
    )
    assert missing_result.error.code == api.NOT_FOUND
    assert "missing" not in missing_result.error.message

    def broken():
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(api, "retrieve_history_overview", broken)
    failure = api.invoke_candidate_read(
        "retrieve_history_overview", access_context=HISTORY_ACCESS
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
    assert list(api.ERROR_CODES) == GOLDEN_SHAPE["error"]["codes"]
    for code in api.ERROR_CODES:
        payload = api.APIErrorEnvelope(
            api_version=AGENT_API_VERSION,
            capability="candidate",
            error=api.APIError(code=code, message="message"),
        ).to_dict()
        assert_golden_fields(
            payload,
            {
                "": GOLDEN_SHAPE["error"][""],
                "error": GOLDEN_SHAPE["error"]["error"],
            },
        )
