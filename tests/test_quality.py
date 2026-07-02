from labassistant.quality import (
    STATUS_NORMAL,
    STATUS_REVIEW,
    STATUS_WATCH,
    classify_distribution_warnings,
    flag_severity,
    status_from_warnings,
)


def test_classify_distribution_warnings_marks_review_signals():
    warnings = classify_distribution_warnings(
        pdi=0.55,
        secondary_peak=220.0,
        tail_index=5.2,
        width_ratio=9.0,
        has_repeated_measurements=False,
        has_distribution_columns=True,
    )

    assert warnings == ["High PDI", "Secondary peak", "Large-particle tail", "Broad distribution"]
    assert status_from_warnings(warnings) == STATUS_REVIEW


def test_classify_distribution_warnings_treats_moderate_pdi_as_watch_for_curves_only():
    curve_warnings = classify_distribution_warnings(
        pdi=0.31,
        secondary_peak=None,
        tail_index=None,
        width_ratio=None,
        has_repeated_measurements=False,
        has_distribution_columns=True,
    )
    repeated_warnings = classify_distribution_warnings(
        pdi=0.31,
        secondary_peak=None,
        tail_index=None,
        width_ratio=None,
        has_repeated_measurements=True,
        has_distribution_columns=True,
    )

    assert curve_warnings == ["Moderate PDI"]
    assert repeated_warnings == []
    assert status_from_warnings(curve_warnings) == STATUS_WATCH
    assert status_from_warnings(repeated_warnings) == STATUS_NORMAL


def test_quality_flags_missing_distribution_columns():
    warnings = classify_distribution_warnings(
        pdi=None,
        secondary_peak=None,
        tail_index=None,
        width_ratio=None,
        has_repeated_measurements=False,
        has_distribution_columns=False,
    )

    assert warnings == ["Distribution columns need review"]
    assert flag_severity("Distribution columns need review") == "watch"
    assert flag_severity("High PDI") == "review"
