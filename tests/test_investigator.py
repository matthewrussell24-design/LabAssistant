from labassistant.investigator import investigate, investigate_observations
from labassistant.models import Experiment, Observation


def _obs(label, category="chromatography_import", severity="normal", recommendation=None, evidence="e"):
    return Observation(
        label=label,
        category=category,
        evidence=evidence,
        severity=severity,
        recommendation=recommendation,
    )


def test_complete_interpretable_experiment():
    observations = [
        _obs("Injections found"),
        _obs("Chromatogram signal available"),
        _obs("Peak table available"),
        _obs("Acquisition method available"),
    ]
    report = investigate_observations(observations, experiment_id="x", technique="HPLC")

    assert report.is_complete is True
    assert report.is_interpretable is True
    assert report.completeness_gaps == []
    assert "HPLC experiment" in report.what_happened
    # Findings expose the five canonical questions.
    questions = [finding.question for finding in report.findings]
    assert questions == [
        "What happened?",
        "Is the experiment complete?",
        "Is anything missing?",
        "Can the experiment be interpreted?",
        "What additional information would improve confidence?",
    ]


def test_review_completeness_gap_blocks_interpretation():
    observations = [
        _obs(
            "No injections found",
            category="data_completeness",
            severity="review",
            recommendation="Confirm the archive is a sequence export.",
        ),
    ]
    report = investigate_observations(observations)

    assert report.is_complete is False
    assert report.is_interpretable is False
    assert any("No injections found" in gap for gap in report.completeness_gaps)
    assert report.interpretation_blockers
    assert "Confirm the archive is a sequence export." in report.confidence_improvers


def test_watch_gap_limits_but_does_not_block():
    observations = [
        _obs("Injections found"),
        _obs("Chromatogram signal available"),
        _obs(
            "Missing peak table",
            category="data_completeness",
            severity="watch",
            recommendation="Export a peak table for quantitative analysis.",
        ),
    ]
    report = investigate_observations(observations)

    assert report.is_complete is False
    assert report.is_interpretable is True  # qualitative interpretation still possible
    interp = next(f for f in report.findings if f.question == "Can the experiment be interpreted?")
    assert interp.answer.startswith("Partially")
    assert "Export a peak table for quantitative analysis." in report.confidence_improvers


def test_empty_observations_not_interpretable():
    report = investigate_observations([])

    assert report.is_interpretable is False
    assert report.interpretation_blockers
    assert "nothing to interpret" in report.what_happened.lower()


def test_confidence_improvers_are_deduped():
    rec = "Export a peak table for quantitative analysis."
    observations = [
        _obs("Missing peak table", category="data_completeness", severity="watch", recommendation=rec),
        _obs("Peak tailing increased", severity="watch", recommendation=rec),
    ]
    report = investigate_observations(observations)

    assert report.confidence_improvers.count(rec) == 1


def test_investigate_consumes_experiment_object():
    experiment = Experiment(
        experiment_id="exp1",
        label="Run",
        technique="HPLC",
        observations=[_obs("Injections found"), _obs("Peak table available")],
    )
    report = investigate(experiment)

    assert report.experiment_id == "exp1"
    assert report.is_interpretable is True
