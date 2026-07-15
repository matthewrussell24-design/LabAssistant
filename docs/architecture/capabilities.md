# LabAssistant Capability Layer

The capability layer is the public language of LabAssistant. It describes what
a scientist can ask the platform to do independently of Streamlit, a future
desktop client, CLI, HTTP transport, or agent SDK.

Interfaces should call a capability when one exists instead of constructing or
mutating domain models directly. Domain models remain the scientific core;
capabilities own workflow entry, validation, orchestration, and stable outputs.

## Design Rules

- Name capabilities after scientific workflows, not implementation functions.
- Keep capability contracts independent of transport and interface framework.
- Prefer read-only, versioned outputs at external-facing boundaries.
- Preserve provenance and deterministic validation across every caller type.
- Keep parsers instrument-specific and reasoning instrument-independent.
- Add a capability only when it represents a coherent user intent.
- Preserve existing Python entry points while callers migrate incrementally.

The initial in-process registry lives in `labassistant.application`. It exposes
metadata and direct callable references. It is not an HTTP router, dependency
container, command bus, authentication layer, or permission system.

## Capability Audit

Existing application operations:

- Describe the platform and future agent-access policy.
- Assemble DLS evidence into an `Experiment`.
- Assemble chromatography evidence into an `Experiment`.
- Produce a read-only `ExperimentSnapshot`.
- Save an experiment and related hypotheses, recommendations, and notes to
  scientific memory.

Established DLS narrative, health, control-chart, and replicate diagnostics now
cross application contracts, including forward-scatter/circulation and
orthogonal filtration reads, dual-angle aggregation assessment, and per-sample
and per-angle summaries. The shared metrics projection used by visualizations
now crosses the same boundary; Streamlit reconstructs pandas only for display,
charting, and CSV export. Distribution-series evidence now also crosses the
boundary while normalization, reference deltas, Plotly, and UI state remain in
Streamlit. Raw evidence inspection and export now use typed point tables,
metadata fields, and source diagnostics; pandas display, downloads, selection,
and source-preview truncation remain in the shell. Correlogram visualization
and paired-angle distribution overlays are now also driven by immutable series.
Streamlit retains sample selection, angle labels, colors, and chart composition.
History comparison and related-run capabilities now also accept parsed DLS
samples directly while retaining established measurement callers.
The explicit history-save command resolves parsed samples inside the
application boundary and still copies evidence before adding append lineage.
Reviewed circulation-time retrieval and mutation now also cross explicit
parsed-sample contracts while Streamlit retains session and widget state.
Reviewed filtration reads, single-sample mutation, and CSV batch attachment now
cross the same boundary with ordered matching results.

### Streamlit Dependency Audit

The task 049 audit classified every direct `app.py` import outside
`labassistant.application`:

| Dependency | UI ownership | Decision |
| --- | --- | --- |
| Aggregation index thresholds and quality status/warning constants | Chart reference lines, badge colors, and warning copy | Intentional presentation dependency |
| `format_metric` | Display-only number and unit formatting | Intentional presentation dependency |
| Filtration rubric, pressure labels/conversions, and validation helpers | Widget choices, reviewed input parsing, and normalized-value preview | Intentional input dependency |
| `FiltrationMeasurement` | Typed payload for the reviewed application command | Intentional in-process command data |
| Circulation-time unit conversions | Widget choices and session-value validation | Intentional input dependency |
| `ParsedSample` | Streamlit workspace/session state and local type annotations | Transitional UI state |

`RelationshipAnalysis` was the only dead domain dependency: it widened a
renderer annotation after all callers had migrated to immutable application
relationship summaries, so task 049 removed it. No remaining import performs
workflow orchestration, persistence, or scientific claim construction in
Streamlit.

This completes extraction for the current human workflows. Task 050 then
introduced the presentation-neutral `DLSSampleEvidence` structural protocol and
`DLSWorkspaceEvidence` local adapter. Application, interpretation, observation,
and trend modules now import that neutral contract; `labassistant.view_models`
is a compatibility facade whose `ParsedSample` name aliases the workspace
adapter for existing Streamlit and test callers.

The protocol deliberately treats tabular `data` as opaque. Task 051 added the
frozen, pandas-free `DLSMeasurementMetrics` projection over authoritative
summary metrics, derived metrics, metadata, flags, and provenance. Both the
immutable `retrieve_dls_metrics` application read and the legacy pandas metrics
table now use that projection, so mutable workspace metric overrides cannot
change their results. Task 052 migrated ordered warning evidence and immutable
per-sample summaries to the same Measurement-first projection. Task 053 then
migrated decision scoring, attention rows, narrative warning
selection, and distribution-confidence wording to the Measurement-first
projection. Task 054 migrated DLS observation
ordering, evidence values, severity, and correlogram findings to Measurement
flags and the frozen projection; observation normalization no longer reads the
workspace dictionary. Task 055 migrated immutable distribution selection,
signals, points, and peaks to authoritative `Measurement.distributions`; the
workspace adapter remains only for arbitrary raw-table inspection.

## Implemented Capability Catalog

| Stable name | Python entry point | Status |
| --- | --- | --- |
| `describe_platform` | `app_manifest` | Available |
| `describe_agent_access` | `agent_access_policy` | Available |
| `import_dls_experiment` | `dls_experiment_from_samples` | Available; structural local DLS evidence input |
| `analyze_dls_dataset` | `analyze_dls_dataset` | Available; used by desktop prototype |
| `analyze_dls_uploads` | `analyze_dls_uploads` | Available; used by Streamlit DLS upload workflow |
| `rank_dls_decisions` | `rank_dls_decisions` | Available; used by Streamlit DLS Decision Brief |
| `compose_dls_narrative` | `compose_dls_narrative` | Available; used by Streamlit DLS findings and Data Story |
| `summarize_dls_health` | `summarize_dls_health` | Available; used by Streamlit DLS health strip |
| `analyze_dls_trend_diagnostics` | `analyze_dls_trend_diagnostics` | Available; used by Streamlit control and replicate diagnostics |
| `retrieve_dls_circulation_time` | `retrieve_dls_circulation_time` | Available; used by Streamlit circulation-time prefill |
| `set_dls_circulation_time` | `set_dls_circulation_time` | Available; explicit reviewed Streamlit evidence mutation |
| `analyze_dls_forward_scatter_trends` | `analyze_dls_forward_scatter_trends` | Available; used by Streamlit circulation explorer |
| `retrieve_dls_filtration_measurement` | `retrieve_dls_filtration_measurement` | Available; used by Streamlit filtration prefill and current-evidence display |
| `set_dls_filtration_measurement` | `set_dls_filtration_measurement` | Available; explicit reviewed Streamlit evidence mutation |
| `attach_dls_filtration_measurements` | `attach_dls_filtration_measurements` | Available; explicit reviewed Streamlit CSV attachment |
| `analyze_filtration_follow_up_trends` | `analyze_filtration_follow_up_trends` | Available; used by Streamlit filtration follow-up |
| `generate_filtration_relationship_hypothesis` | `generate_filtration_relationship_hypothesis` | Available; used by Streamlit filtration hypothesis callout |
| `assess_dls_aggregation` | `assess_dls_aggregation` | Available; used by Streamlit dual-angle comparison |
| `summarize_dls_samples` | `summarize_dls_samples` | Available; used by Streamlit sample cards and inspection list |
| `retrieve_dls_angle_details` | `retrieve_dls_angle_details` | Available; used by Streamlit per-angle detail table |
| `retrieve_dls_metrics` | `retrieve_dls_metrics` | Available; used by Streamlit charts, raw table, and CSV export |
| `retrieve_dls_distributions` | `retrieve_dls_distributions` | Available; used by Streamlit distribution visualizations |
| `retrieve_dls_raw_evidence` | `retrieve_dls_raw_evidence` | Available; used by Streamlit raw evidence inspection and export |
| `retrieve_dls_correlograms` | `retrieve_dls_correlograms` | Available; used by Streamlit correlogram diagnostics |
| `retrieve_dls_paired_angle_overlays` | `retrieve_dls_paired_angle_overlays` | Available; used by Streamlit dual-angle distribution comparison |
| `import_chromatography_experiment` | `chromatography_experiment_from_preview` | Available, transitional input |
| `analyze_chromatography_source` | `analyze_chromatography_source` | Available; used by Streamlit chromatography preview |
| `analyze_filtration_csv` | `analyze_filtration_csv` | Available; used by Streamlit filtration follow-up |
| `generate_observations` | `generate_observations` | Available; shared DLS, chromatography, and filtration normalization |
| `list_experiments` | `list_experiments` | Available; used by desktop History timeline |
| `compare_experiments` | `compare_experiments` | Available; used by Streamlit History panel |
| `find_related_experiments` | `find_related_experiments` | Available; used by Streamlit History panel |
| `retrieve_history_overview` | `retrieve_history_overview` | Available; used by Streamlit History panel |
| `retrieve_experiment` | `retrieve_experiment` | Available; first used by Streamlit history loader |
| `retrieve_experiment_summary` | `build_experiment_snapshot` | Available |
| `investigate_experiment` | `investigate_experiment` | Available; composed by experiment brief preview |
| `produce_experiment_brief` | `produce_experiment_brief` | Available; used by Streamlit Experiment Brief |
| `retrieve_related_context` | `retrieve_related_context` | Available; used by Streamlit memory panel |
| `retrieve_research_journal` | `retrieve_research_journal` | Available; used by Streamlit Research Journal |
| `add_scientific_note` | `add_scientific_note` | Available; explicit Streamlit journal write |
| `save_experiment_history` | `save_experiment_history` | Available; explicit Streamlit history write |
| `save_scientific_memory` | `save_experiment_to_memory` | Available |

`list_capabilities()` returns immutable `CapabilityContract` metadata.
`get_capability(name)` resolves one stable name or raises `KeyError`. Callers
invoke the referenced Python handler directly; the registry adds no transport.
`app_manifest()` publishes transport-neutral catalog metadata without exposing
Python handlers or domain objects.

## Describe Platform

**Name:** `describe_platform`

**Purpose:** Describe the LabAssistant product boundary, primary human surface,
and future access direction.

**Inputs:** None.

**Outputs:** A plain dictionary containing product identity, direction, primary
surface, and agent-access policy.

**Expected Errors:** None under normal operation.

**Caller Types:** Human UI, Agent, CLI, Future API.

## Describe Agent Access

**Name:** `describe_agent_access`

**Purpose:** Describe the reviewed boundaries and non-goals for future agent
clients without creating an agent runtime.

**Inputs:** None.

**Outputs:** An immutable `AgentAccessPolicy` with a dictionary representation.

**Expected Errors:** None under normal operation.

**Caller Types:** Human UI, Agent, CLI, Future API.

## Import DLS Experiment

**Name:** `import_dls_experiment`

**Purpose:** Assemble already parsed DLS sample evidence into an experiment and
generate its normalized observations.

**Inputs:** Objects conforming to `DLSSampleEvidence`, plus an optional
experiment label and source-file names. Existing `ParsedSample` callers remain
compatible through the `DLSWorkspaceEvidence` alias. This is an in-process
structural contract, not a serialized transport request.

**Outputs:** An `Experiment` containing DLS measurements, observations,
provenance metadata, and a generated identifier.

**Expected Errors:** `TypeError` or `AttributeError` for malformed sample input.
Parser errors occur before this capability and are not yet normalized into
application-level errors.

**Caller Types:** Human UI, CLI, Future API. Agent use should wait for reviewed
file/provenance handling.

## Analyze Chromatography Source

**Name:** `analyze_chromatography_source`

**Purpose:** Import and analyze a chromatography CSV or OpenLab `.olax` source
without requiring a shell to select importers, build mass-balance reasoning, or
handle temporary archive files.

**Inputs:** A path or seekable uploaded source, optional label, and optional
source name. The `.csv` and `.olax` suffixes select the supported adapter.

**Outputs:** A versioned, frozen `ChromatographyAnalysisResult` containing an
experiment snapshot, immutable injection summaries, normalized observation
evidence, hypotheses, limitations, optional mass-balance assessment and trend
points, and archive summary counts. It contains no pandas DataFrames or mutable
measurements. The reviewed scientific-memory command accepts this result
directly; `restore_experiment()` remains available for established application
callers that explicitly need a fresh domain copy.

**Expected Errors:** `ValueError` for unsupported suffixes or invalid/empty CSV
evidence, `FileNotFoundError` for missing paths, and existing parser/archive
exceptions for malformed sources.

**Caller Types:** Human UI, CLI, Future API. Agent use is excluded pending
reviewed file and provenance handling. Streamlit is the first caller.

## Analyze Filtration CSV

**Name:** `analyze_filtration_csv`

**Purpose:** Parse filtration follow-up CSV evidence without exposing pandas or
the mutable importer result to interface shells.

**Inputs:** A path or file-like CSV source and optional source name.

**Outputs:** A versioned, frozen `FiltrationImportRead` containing immutable
measurement and trace summaries, normalized pressure/time units, warnings,
errors, missing columns, unsupported columns, and source provenance.
`restore_measurements()` returns fresh copies only for a reviewed attach action.

**Expected Errors:** Existing CSV read/parser exceptions. Missing required
columns and invalid rows remain structured diagnostics rather than exceptions.

**Caller Types:** Human UI, CLI, Future API. Agent use is excluded pending
reviewed file handling. Streamlit is the first caller; its explicit Attach
button remains responsible for matching and mutating current DLS evidence.

## Generate Observations

**Name:** `generate_observations`

**Purpose:** Normalize supported technique evidence into traceable scientific
findings through the established domain rules.

**Inputs:** A non-empty evidence list and explicit technique. DLS accepts parsed
samples; chromatography accepts measurements plus a mass-balance assessment;
filtration accepts filtration measurements.

**Outputs:** A frozen, versioned `ObservationGenerationResult` containing the
normalized technique and immutable `ObservationRead` values with label,
category, evidence, severity, confidence, source identity, and recommendation.
Internal experiment assembly can request fresh domain copies without exposing
mutable authoritative objects in serialized output.

**Expected Errors:** `ValueError` for empty evidence, unsupported techniques,
or a missing/inapplicable chromatography assessment; `TypeError` for evidence
that does not match the selected technique.

**Caller Types:** Human UI, Agent, CLI, Future API. DLS assembly,
chromatography restore, and chromatography CSV analysis are the first callers.

## Analyze Local DLS Dataset

**Name:** `analyze_dls_dataset`

**Purpose:** Run the supported multi-file DLS workflow from existing local
paths independently of any UI framework.

**Inputs:** One or more local CSV, text, XLS, or XLSX paths and an optional
experiment label.

**Outputs:** A versioned `DLSAnalysisResult` containing an
`ExperimentSnapshot`, concise immutable per-lot summaries, source paths, and
non-fatal import errors. Raw traces and mutable measurements remain inside the
scientific workflow.

**Expected Errors:** `ValueError` for an empty selection or a dataset with no
supported measurements; `FileNotFoundError` for a missing selected path;
existing parser exceptions for malformed files.

**Caller Types:** Human UI, CLI, Future API. The native AppKit desktop shell is
the first caller. Agent use is intentionally excluded.

## Analyze Uploaded DLS Evidence

**Name:** `analyze_dls_uploads`

**Purpose:** Classify, group, preview, and import uploaded multi-file DLS
evidence without coupling the application layer to Streamlit upload objects.

**Inputs:** A non-empty list of generic sources that expose a string `name` and
readable file interface. Existing CSV/XLS/XLSX classifier behavior determines
roles and lot grouping.

**Outputs:** A frozen, versioned `DLSUploadImportResult` containing immutable
group and classified-file diagnostics, plain preview rows, per-lot measurement
summaries, source names, and flattened import errors. `restore_samples()`
returns fresh parsed-sample copies for explicit workspace use and retry.

**Expected Errors:** `ValueError` for an empty selection and `TypeError` for
unnamed or unreadable sources. Established preview/parser exceptions remain
visible; unexpected grouped-import failures become structured import errors to
preserve the resilient human upload workflow.

**Caller Types:** Human UI, CLI, Future API. Streamlit is the first caller.
Agent use is excluded pending reviewed file and provenance handling.

## Rank DLS Decisions

**Name:** `rank_dls_decisions`

**Purpose:** Rank parsed DLS samples for deterministic screening attention while
keeping this technique-specific heuristic separate from the Investigator.

**Inputs:** A non-empty list of parsed DLS samples. The capability builds the
established metrics table internally, so callers do not pass pandas objects.

**Outputs:** A frozen, versioned `DLSDecisionRanking` containing best and
attention candidates, flagged and total counts, review sample labels, next-check
guidance, unusual changes, and ordered immutable `DLSAttentionRow` values. No
DataFrame crosses the application boundary.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-sample contract. Established metric validation
errors remain unchanged.

**Caller Types:** Human UI, CLI, Future API. Streamlit's DLS Decision Brief is
the first caller. Agent use is excluded because this rank is a human screening
heuristic rather than an instrument-independent reasoning contract.

## Compose DLS Narrative

**Name:** `compose_dls_narrative`

**Purpose:** Compose the established rule-based DLS findings, detailed analysis,
and trend story once, without presenting deterministic text as language-model
output.

**Inputs:** A non-empty list of parsed DLS samples. The capability builds its
metrics table internally, so callers do not pass pandas objects.

**Outputs:** A frozen, versioned `DLSNarrative` containing ordered automated-
finding, detailed-analysis, and data-story sections. Each
`DLSNarrativeSection` contains an immutable heading and bullet tuple. No
DataFrame or card-layout detail crosses the application boundary.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-sample contract. Established narrative and
trend validation errors remain unchanged.

**Caller Types:** Human UI, CLI, Future API. Streamlit is the first caller and
composes the result once per imported dataset. Agent use remains excluded while
this DLS-specific presentation contract matures.

## Summarize DLS Health

**Name:** `summarize_dls_health`

**Purpose:** Summarize the existing DLS screening score, warning-status counts,
and central metric values without treating the score as a universal scientific
quality assessment.

**Inputs:** A non-empty list of parsed DLS samples. The capability builds its
metrics table internally, so callers do not pass pandas objects.

**Outputs:** A frozen, versioned `DLSHealthOverview` containing the integer
screening score, sample/flagged/review counts, median Z-average, and median
large-particle-tail percentage. Missing medians are `None`; no formatted labels
or DataFrame crosses the boundary.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-sample contract.

**Caller Types:** Human UI, CLI, Future API. Streamlit's health strip is the
first caller. Agent use is excluded while this human screening heuristic matures.

## Analyze DLS Trend Diagnostics

**Name:** `analyze_dls_trend_diagnostics`

**Purpose:** Produce the established DLS control-limit signals and replicate-
series statistics without exposing pandas-returning trend helpers to callers.

**Inputs:** A non-empty list of parsed DLS samples. The capability builds its
metrics table internally and reads replicate evidence from each measurement.

**Outputs:** A frozen, versioned `DLSTrendDiagnostics` containing ordered tuples
of `DLSControlChartRow` and `DLSReplicateStatisticsRow`. Fields use semantic
snake-case names rather than current UI column labels; no DataFrame crosses the
application boundary.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-sample contract. Insufficient series data is a
valid result with empty row tuples.

**Caller Types:** Human UI, CLI, Future API. Streamlit's control chart and
replicate table are the first callers. Agent use is excluded while these DLS-
specific diagnostics mature.

## Retrieve DLS Circulation Time

**Name:** `retrieve_dls_circulation_time`

**Purpose:** Return explicitly reviewed circulation-time evidence without
exposing mutable measurement provenance to interface shells.

**Inputs:** One parsed DLS sample.

**Outputs:** A frozen, versioned `DLSCirculationTimeRead` containing sample name,
entered value, original unit, normalized minutes, and optional source. Missing
or malformed stored provenance returns `None`; no session key or display value
crosses the boundary.

**Expected Errors:** `TypeError` when the input does not satisfy the parsed DLS
sample contract.

**Caller Types:** Human UI, CLI, Future API. Streamlit uses the read to prefill
reviewed values. Agent use remains excluded because this is experiment-specific
operator evidence.

## Set DLS Circulation Time

**Name:** `set_dls_circulation_time`

**Purpose:** Attach, overwrite, or clear explicitly reviewed circulation-time
evidence on one parsed DLS sample.

**Inputs:** One parsed DLS sample, an optional numeric value and unit, and an
optional provenance source. `None` value or unit retains the established clear
semantics; callers decide whether a blank UI field should invoke the command.

**Outputs:** The resulting frozen `DLSCirculationTimeRead`, or `None` after a
clear. Valid writes retain the entered value/unit, normalize to minutes, and
store their reviewed source.

**Expected Errors:** `TypeError` for malformed sample inputs and `ValueError`
for unsupported non-empty units. Established numeric conversion behavior is
unchanged.

**Caller Types:** Human UI and CLI only. Agent and Future API callers are
excluded because this mutates reviewed experimental evidence. Streamlit remains
responsible for explicit input and session behavior.

## Analyze DLS Forward-Scatter Trends

**Name:** `analyze_dls_forward_scatter_trends`

**Purpose:** Analyze explicitly reviewed circulation-time evidence against
forward-angle DLS size and PDI without exposing mutable trend-domain results.

**Inputs:** A non-empty list of parsed DLS samples whose measurements may carry
reviewed circulation-time value/unit provenance. Session state and input parsing
remain outside the capability.

**Outputs:** A frozen, versioned `DLSForwardScatterTrendRead` containing ordered
`DLSForwardScatterPoint` evidence and qualified `DLSRelationshipSummary` values
for forward Z-average and PDI. Messages preserve insufficient-data constraints
and explicitly describe correlations as non-causal.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-sample contract. Missing circulation or forward-
angle evidence produces empty points and qualified messages rather than errors.

**Caller Types:** Human UI, CLI, Future API. Streamlit's circulation explorer is
the first caller. Agent use remains excluded pending broader review of user-
entered experimental-variable provenance.

## Retrieve DLS Filtration Measurement

**Name:** `retrieve_dls_filtration_measurement`

**Purpose:** Return reviewed filtration evidence without exposing mutable DLS
measurement provenance to interface shells.

**Inputs:** One parsed DLS sample.

**Outputs:** A frozen, versioned `DLSFiltrationRead` containing parsed-sample
identity and the existing immutable `FiltrationMeasurementSummary`. The nested
summary preserves difficulty, time, pressure and normalized pressure, filter,
clogging, notes, source, warnings, and trace evidence. Missing or malformed
stored provenance returns `None`.

**Expected Errors:** `TypeError` when the input does not satisfy the parsed DLS
sample contract.

**Caller Types:** Human UI, CLI, Future API. Streamlit uses this read for manual
prefill and the current attached-evidence table. Agent use remains excluded
because this is reviewed operator evidence.

## Set DLS Filtration Measurement

**Name:** `set_dls_filtration_measurement`

**Purpose:** Attach, overwrite, or clear one reviewed filtration measurement on
a parsed DLS sample.

**Inputs:** One parsed DLS sample and an optional `FiltrationMeasurement`.
`None` or a measurement without a difficulty score retains the established
clear semantics. Streamlit remains responsible for input parsing and pressure
normalization before command invocation.

**Outputs:** The resulting frozen `DLSFiltrationRead`, or `None` after a clear.

**Expected Errors:** `TypeError` for malformed parsed-sample or filtration
inputs. Established domain serialization behavior is unchanged.

**Caller Types:** Human UI and CLI only. Agent and Future API callers are
excluded because this mutates reviewed evidence.

## Attach DLS Filtration Measurements

**Name:** `attach_dls_filtration_measurements`

**Purpose:** Attach reviewed filtration measurements to current DLS samples by
the established exact sample-name matching rule.

**Inputs:** Parsed DLS samples and filtration measurements in caller order.
Empty current samples are valid and make every submitted measurement unmatched.

**Outputs:** A frozen, versioned `DLSFiltrationAttachmentResult` containing the
matched count, resulting attached reads in submitted-measurement order, and
unmatched sample names in submitted order. Repeated matches retain established
last-write-wins provenance behavior.

**Expected Errors:** `TypeError` for malformed parsed-sample or filtration
inputs.

**Caller Types:** Human UI and CLI only. Streamlit's explicit CSV attachment
button is the first caller; session prefill and user feedback remain in the
shell.

## Analyze Filtration Follow-Up Trends

**Name:** `analyze_filtration_follow_up_trends`

**Purpose:** Analyze reviewed filtration difficulty evidence against forward-
angle DLS size, PDI, and circulation time without exposing mutable trend-domain
results.

**Inputs:** A non-empty list of parsed DLS samples whose measurements may carry
reviewed filtration follow-up and circulation-time provenance. Input parsing and
evidence attachment remain outside this read capability.

**Outputs:** A frozen, versioned `FiltrationTrendRead` containing ordered
`FiltrationTrendPointRead` evidence and three qualified
`FiltrationRelationshipSummary` values. Summaries preserve Spearman method,
insufficient-data constraints, and correlation-only language.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-DLS-sample contract. Missing filtration
evidence produces empty points and qualified messages rather than errors.

**Caller Types:** Human UI, CLI, Future API. Streamlit's filtration follow-up is
the first caller. Agent use remains excluded pending broader review of ordinal,
operator-assessed evidence.

## Generate Filtration Relationship Hypothesis

**Name:** `generate_filtration_relationship_hypothesis`

**Purpose:** Qualify the working relationship hypothesis connecting circulation
time, forward-angle DLS size/PDI, and orthogonal filtration difficulty without
placing scientific claims or causal interpretation in presentation code.

**Inputs:** One immutable `DLSForwardScatterTrendRead` and one immutable
`FiltrationTrendRead` produced by the established trend capabilities.
Correlations are not recomputed, and evidence from only one stage cannot fully
qualify the two-stage hypothesis.

**Outputs:** A frozen, versioned `FiltrationRelationshipHypothesis` containing
an insufficient, partial, or qualified status, the count of five component
relationships that are currently estimable, complete application-authored
display text, and the five underlying qualified relationship messages. The
working hypothesis remains visible with proposed-not-supported language before
evidence thresholds are met; estimable results retain explicit
correlation-only, non-causal wording.

**Expected Errors:** `TypeError` when either input does not match its expected
immutable trend read.

**Caller Types:** Human UI, CLI, Future API. Streamlit's filtration callout is
the first caller. Agent use remains excluded pending broader review of ordinal,
operator-assessed evidence and hypothesis policy.

## Assess DLS Aggregation

**Name:** `assess_dls_aggregation`

**Purpose:** Apply the established dual-angle DLS aggregation screening model to
every requested sample without exposing mutable assessment-domain objects.

**Inputs:** A non-empty list of parsed DLS samples carrying angle summaries and
optional distribution, correlogram, replicate, and peak evidence.

**Outputs:** A frozen, versioned `DLSAggregationRead` containing one ordered
`DLSAggregationAssessment` per input sample, including unavailable results.
Each assessment preserves nested `DLSAngleEvidence`, immutable checklist items,
flags, index/category thresholds, confidence, corroboration counts, headline,
recommendation, and qualified summary.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-sample contract. Missing angle pairs produce an
unavailable assessment with explanatory summary rather than an error.

**Caller Types:** Human UI, CLI, Future API. Streamlit's dual-angle comparison
is the first caller. Agent use remains excluded because this is a technique-
specific screening model with transferability caveats.

## Summarize DLS Samples

**Name:** `summarize_dls_samples`

**Purpose:** Compose ordered per-sample DLS status, warning evidence, and
scientifically formatted inspection values without coupling them to card markup.

**Inputs:** A non-empty list of parsed DLS samples.

**Outputs:** A frozen, versioned `DLSSampleSummaries` containing ordered
`DLSSampleSummary` values. Each summary preserves status, warning tuple, review-
evidence sentence, and ordered `DLSMetricDisplayRow` values, including
conditional peak/tail rows and explicit missing-value strings. No HTML, CSS,
column count, or card class crosses the boundary.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-sample contract.

**Caller Types:** Human UI, CLI, Future API. Streamlit's sample cards and
“Samples To Inspect” panel are the first callers. Agent use remains excluded
while these presentation-oriented DLS summaries mature.

## Retrieve DLS Angle Details

**Name:** `retrieve_dls_angle_details`

**Purpose:** Project measurement angle summaries into stable typed rows without
exposing the pandas-returning view-model helper.

**Inputs:** A non-empty list of parsed DLS samples.

**Outputs:** A frozen, versioned `DLSAngleDetails` containing sample-major,
angle-minor `DLSAngleDetailRow` values with semantic field names for position,
counts, replicates, Z-average, PDI, maximum Z-average, primary peak, and D50.
No DataFrame or display rounding crosses the boundary.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-sample contract. Samples without angle
summaries produce an empty row tuple rather than an error.

**Caller Types:** Human UI, CLI, Future API. Streamlit's per-angle detail table
is the first caller. Agent use remains excluded while this DLS-specific read
contract matures.

## Retrieve DLS Metrics

**Name:** `retrieve_dls_metrics`

**Purpose:** Project the shared per-sample DLS metrics into stable typed rows
without exposing the pandas-returning view-model helper.

**Inputs:** A non-empty list of parsed DLS samples.

**Outputs:** A frozen, versioned `DLSMetricsProjection` containing ordered
`DLSMetricRow` values with semantic names for status, summary and distribution
metrics, optional diagnostic values, measurement metadata, and an immutable
warning tuple. Numeric values and missing values remain unformatted. No
DataFrame or display column labels cross the boundary.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-sample contract. Established missing-required-
metric errors remain unchanged.

**Caller Types:** Human UI, CLI, Future API. Streamlit's shared comparison,
diagnostic, raw-data, and CSV-export projection is the first caller. Agent use
remains excluded while this DLS-specific read contract matures.

## Retrieve DLS Distributions

**Name:** `retrieve_dls_distributions`

**Purpose:** Project DLS intensity, volume, and number distribution evidence
into stable typed series without exposing parsed-sample DataFrames or vendor
column labels to visualization shells.

**Inputs:** A non-empty list of named DLS evidence records carrying an
authoritative `Measurement`.

**Outputs:** A frozen, versioned `DLSDistributionProjection` containing samples
in import order, sample status, signal-major `DLSDistributionSeries`, filtered
positive-diameter/nonnegative-signal points, unnormalized local peaks, explicit
diameter/signal column-identification flags, and ordered available signals.
Identified signals with no usable points remain distinguishable from missing
signals. No DataFrame, normalization choice, reference choice, or chart state
crosses the boundary.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
without an authoritative `Measurement`.

**Caller Types:** Human UI, CLI, Future API. Streamlit's signal selector,
overlay, delta chart, and small multiples are the first callers. Agent use
remains excluded while this DLS-specific read contract matures.

## Retrieve DLS Raw Evidence

**Name:** `retrieve_dls_raw_evidence`

**Purpose:** Project raw DLS point tables, metadata, fallback source text, and
uploaded-file diagnostics into stable inspection records without exposing
parsed samples or pandas to interface shells.

**Inputs:** A non-empty list of parsed DLS samples and optional immutable DLS
upload-group diagnostics.

**Outputs:** A frozen, versioned `DLSRawEvidence` containing samples in import
order, vendor-shaped `DLSRawPointTable` column/row tuples, ordered
`DLSRawMetadataField` values, complete fallback source text, and grouped
`DLSRawSourceFile` diagnostics in original file order. No DataFrame, CSV,
selection state, display labels, or source-preview truncation crosses the
boundary.

**Expected Errors:** `ValueError` for no samples and `TypeError` for malformed
parsed samples, upload groups, or classified source diagnostics. Established
malformed-DataFrame errors remain unchanged.

**Caller Types:** Human UI, CLI, Future API. Streamlit's raw point, metadata,
original-file, and CSV-download tabs are the first callers. Agent use remains
excluded because this contract includes complete raw source content.

## Retrieve DLS Correlograms

**Name:** `retrieve_dls_correlograms`

**Purpose:** Project DLS correlogram traces and sample-level baseline-noise
evidence into stable typed series without exposing mutable measurements to
visualization shells.

**Inputs:** A non-empty list of parsed DLS samples.

**Outputs:** A frozen, versioned `DLSCorrelograms` containing non-empty sample
series in import order, trace points in measurement order, optional delay,
correlation, and replicate values, and one optional noise score per sample. No
DataFrame, Plotly configuration, hover template, or diagnostic label crosses
the boundary. Samples without trace points are omitted; no traces is a valid
empty result.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-sample contract. Non-numeric trace values retain
the established conversion error behavior.

**Caller Types:** Human UI, CLI, Future API. Streamlit's secondary correlogram-
quality chart is the first caller. Agent use remains excluded while this DLS-
specific visualization read matures.

## Retrieve DLS Paired-Angle Overlays

**Name:** `retrieve_dls_paired_angle_overlays`

**Purpose:** Project forward and backscatter DLS distribution evidence into
stable typed curves without exposing mutable measurements to visualization
shells.

**Inputs:** A non-empty list of parsed DLS samples.

**Outputs:** A frozen, versioned `DLSPairedAngleOverlays` containing every
sample in import order, identified curves in forward/back order, and diameter
plus normalized-intensity points in measurement order. Missing or empty curves
remain explicit through each sample's derived availability state. No sample
selection, angle display label, color, hover template, or Plotly configuration
crosses the boundary.

**Expected Errors:** `ValueError` for no samples and `TypeError` for evidence
that does not satisfy the parsed-sample contract. Non-numeric curve values
retain the established conversion error behavior.

**Caller Types:** Human UI, CLI, Future API. Streamlit's paired-angle
distribution chart is the first caller. Agent use remains excluded while this
DLS-specific visualization read matures.

## Import Chromatography Experiment

**Name:** `import_chromatography_experiment`

**Purpose:** Assemble an already parsed chromatography or OpenLab preview into
an experiment.

**Inputs:** Import preview, optional label, and optional source name. The preview
dictionary is transitional until importer result contracts stabilize.

**Outputs:** An `Experiment` containing chromatography measurements,
observations, hypotheses, assessment metadata, and source provenance.

**Expected Errors:** `TypeError`, `AttributeError`, or malformed-preview errors.
Archive and CSV parser errors occur before this boundary.

**Caller Types:** Human UI, CLI, Future API. Agent use should wait for reviewed
file/provenance handling.

## Retrieve Experiment Summary

**Name:** `retrieve_experiment_summary`

**Purpose:** Return compact, read-only experiment information without exposing
raw files, traces, measurements, or mutable observations.

**Inputs:** An existing `Experiment`.

**Outputs:** A versioned `ExperimentSnapshot` containing identity, technique,
instrument, evidence counts, and observation-category counts.

**Expected Errors:** `TypeError` or `AttributeError` when the supplied object is
not a valid experiment. A future persisted lookup capability should define
not-found errors separately.

**Caller Types:** Human UI, Agent, CLI, Future API.

## List Experiments

**Name:** `list_experiments`

**Purpose:** Enumerate persisted experiments for timeline browsing without
exposing mutable measurements or requiring an interface shell to read JSONL
storage directly.

**Inputs:** An optional history path for local or test storage.

**Outputs:** A tuple of frozen, metadata-only `ExperimentListing` records
(record id, saved time, label, measurement count, api version) ordered
newest-first. Same-second ties are broken by append order so the most recently
saved record sorts first, matching `latest_experiment`.

**Expected Errors:** None under normal operation. A missing history file yields
an empty tuple, and malformed JSONL lines are skipped so one damaged record
cannot hide the rest of the timeline.

**Caller Types:** Human UI, Agent, CLI, Future API. The native AppKit desktop
History timeline is the first caller.

## Retrieve Persisted Experiment

**Name:** `retrieve_experiment`

**Purpose:** Load one JSONL-backed experiment with its history provenance while
keeping persistence reconstruction outside interface shells.

**Inputs:** A record identifier and an optional history path for local or test
storage.

**Outputs:** A versioned, frozen `RetrievedExperiment` containing record
identity, saved time, label, and measurement count. `restore_measurements()`
returns fresh editable copies and `to_dict()` exposes metadata only.

**Expected Errors:** `ExperimentRecordNotFoundError` when the record or history
file does not exist; `MalformedExperimentRecordError` when targeted retrieval
cannot safely interpret the JSONL or measurement payload.

**Caller Types:** Human UI, Agent, CLI, Future API. The Streamlit saved DLS
experiment loader is the first caller.

## Retrieve History Overview

**Name:** `retrieve_history_overview`

**Purpose:** Return persisted experiment-level summaries and sample-level DLS
trend evidence without requiring interface shells to read JSONL or derive
history metrics.

**Inputs:** An optional history path for local or test storage.

**Outputs:** A versioned, frozen `HistoryOverview` containing immutable
`HistorySummary` and `HistoryTrendPoint` tuples. Summary order preserves JSONL
append order; trend points preserve experiment and measurement order.

**Expected Errors:** None under normal operation. Missing history yields empty
tuples and malformed lines retain the tolerant history-reader behavior.

**Caller Types:** Human UI, Agent, CLI, Future API. Streamlit is the first caller.

**Restore composition:** `restore_dls_experiment(record_id)` is a supporting
application function (not a separate catalog entry) that composes
`retrieve_experiment` with the shared DLS summary assembly and returns a
`DLSAnalysisResult`. It lets the desktop reopen a saved record through the same
read model as a fresh import without reading storage or recomputing metrics.

`restore_dls_workspace(record_id)` reuses that technique-aware reconstruction
for human shells that need editable session evidence. It returns a frozen
`DLSWorkspaceRestoreResult` containing the read-only analysis, immutable saved
record metadata, and copy-on-access parsed samples. This keeps mutable restore
access out of the native desktop's presentation-oriented `DLSAnalysisResult`
while preserving history provenance and append-new-version lineage.

`restore_chromatography_experiment(record_id)` is the corresponding
technique-aware composition for HPLC evidence. It reconstructs nested peaks and
chromatogram traces, annotates history provenance, reruns deterministic
mass-balance assessment and observation generation, and returns a frozen
`ChromatographyRestoreResult` with immutable injection summaries. DLS, empty,
and malformed chromatography records are rejected with
`MalformedExperimentRecordError`; the JSONL schema is unchanged.

## Compare Experiments

**Name:** `compare_experiments`

**Purpose:** Explain sample-level Z-average and PDI changes between current DLS
evidence and a selected or latest persisted experiment.

**Inputs:** Current parsed DLS samples or established `Measurement` objects, an
optional baseline record ID, an optional record ID to exclude from latest
selection, and an injectable history path. Mixed compatible inputs retain caller
order.

**Outputs:** A versioned, frozen `ExperimentComparison` containing immutable
sample rows, baseline metadata, drift labels, and a drifted-sample count. Empty
history produces no baseline and labels current rows as new samples.

**Expected Errors:** `TypeError` for inputs that are neither parsed DLS samples
nor DLS measurements. Explicit lookup preserves existing not-found and malformed
record errors. Automatic latest selection tolerates absent history.

**Caller Types:** Human UI, Agent, CLI, Future API. Threshold crossings do not
claim scientific causality.

## Find Related Experiments

**Name:** `find_related_experiments`

**Purpose:** Rank saved DLS samples by proximity to one query measurement using
the established size and PDI feature distance.

**Inputs:** A query parsed DLS sample or established `Measurement`, optional
top-N limit, optional record ID to exclude, and an injectable history path.

**Outputs:** A versioned, frozen `RelatedExperiments` envelope containing
immutable ranked matches. Similarity is a readability score derived from
distance, not a probability.

**Expected Errors:** `ValueError` when `top_n` is less than one and `TypeError`
for an input that is neither a parsed DLS sample nor DLS measurement. Missing or
empty history returns an empty match tuple.

**Caller Types:** Human UI, Agent, CLI, Future API. Relatedness indicates feature
proximity and must not be presented as causal evidence.

## Save Experiment History

**Name:** `save_experiment_history`

**Purpose:** Append explicitly confirmed experiment evidence to local JSONL
history without exposing the persistence writer to interface shells.

**Inputs:** One or more parsed DLS samples or established serializable
measurements, an optional label, optional loaded-record identity and label for
append-only lineage, and an injectable history path. Direct non-DLS measurement
evidence remains supported by the generic writer.

**Outputs:** A frozen, versioned `ExperimentSaveReceipt` containing record
identity, saved timestamp, normalized label, measurement count, and optional
source record identity. Evidence is copied before lineage is added, so the
active analysis is not mutated by saving.

**Expected Errors:** `ValueError` for empty evidence, `TypeError` when resolved
evidence lacks the established `to_dict()` serialization contract, and local
I/O errors when persistence fails.

**Caller Types:** Human UI and CLI only. Agent and Future API use are excluded
because this is an explicit reviewed write. Streamlit is the first caller.

## Save Scientific Memory

**Name:** `save_scientific_memory`

**Purpose:** Persist an experiment and its related hypotheses,
recommendations, tags, and optional human note as scientific memory.

**Inputs:** An established `Experiment`, parsed DLS samples, or a
`ChromatographyAnalysisResult`; an optional reviewed label, DLS source-file
names, human note, project identifier, tags, and an optional injected
`KnowledgeStore`. Direct experiments are defensively copied, DLS experiments
are assembled from copied samples, and chromatography results restore a fresh
domain copy before label changes or persistence.

**Outputs:** A frozen, versioned `ScientificMemorySaveReceipt` containing the
experiment identity, normalized or fallback label, technique, measurement
count, and optional project identifier. Success means all requested records
were accepted by the store.

**Expected Errors:** `ValueError` for empty DLS evidence, `TypeError` for
unsupported or malformed reviewed inputs, and local persistence/database
errors. Atomicity and application-level error normalization remain undefined;
callers must not imply a successful save after an exception.

**Caller Types:** Human UI and CLI. Future API or Agent callers require reviewed
write commands, authorization, audit behavior, and explicit human approval.

## Retrieve Related Scientific Context

**Name:** `retrieve_related_context`

**Purpose:** Retrieve a compact, deterministic context packet from local
scientific memory without exposing the mutable store or arbitrary payloads.

**Inputs:** A non-empty keyword question, optional required tags, positive
result limit, and injectable knowledge-store path or store.

**Outputs:** A versioned, frozen `RelatedScientificContext` containing immutable
items grouped as experiments, observations, supporting evidence, hypotheses,
recommendations, notes, and source files. Items retain identity, experiment,
project, instrument, source, tag, confidence, and timestamp provenance.

**Expected Errors:** `ValueError` for an empty question or limit below one.
Missing or empty memory returns a low-confidence packet with the established
empty-memory caveat.

**Caller Types:** Human UI, Agent, CLI, Future API. Streamlit's local-memory
context panel is the first caller.

## Retrieve Research Journal

**Name:** `retrieve_research_journal`

**Purpose:** List and export the deterministic Research Journal without
exposing its mutable store or grouping implementation.

**Inputs:** Optional keyword, tag, instrument, and sample filters plus an
injectable knowledge-store path or store.

**Outputs:** A versioned, frozen `ResearchJournalRead` containing immutable
grouped entries in newest-first order and the exact matching Markdown export.
Entries retain identity, experiment, instrument, tags, samples, observations,
hypotheses, recommendations, source files, notes, and timestamps.

**Expected Errors:** Local SQLite read errors. Empty or unmatched memory returns
an empty entry tuple and the established no-matches Markdown document.

**Caller Types:** Human UI, Agent, CLI, Future API. Streamlit's Research Journal
panel is the first caller. Standalone note creation is not part of this read query.

## Add Scientific Note

**Name:** `add_scientific_note`

**Purpose:** Persist one explicitly confirmed standalone human note to local
scientific memory and return immutable receipt metadata.

**Inputs:** Required non-empty text; optional title, instrument identifier,
tags, and injectable knowledge-store path or store. Whitespace is trimmed,
blank titles become `Research note`, blank instruments are omitted, and tags
retain the store's normalized/deduplicated ordering.

**Outputs:** A frozen `ScientificNoteReceipt` containing item ID, title,
instrument, tags, human confidence, timestamp, and API version. Note text is
not echoed in the receipt.

**Expected Errors:** `ValueError` for empty note text and local SQLite write errors.

**Caller Types:** Human UI and CLI only. The explicit Streamlit button action is
the first caller. Agent and Future API callers are intentionally excluded until
authorization, approval, and audit policies exist.

## Investigate Experiment

**Name:** `investigate_experiment`

**Purpose:** Assess experiment completeness and interpretability from its
normalized observation stream without exposing the mutable domain report.

**Inputs:** An `Experiment` containing normalized observations.

**Outputs:** A versioned, frozen `ExperimentInvestigation` containing the five
canonical question/answer findings, completeness and interpretability state,
confidence improvements, highlights, severity counts, and immutable observation
evidence with source provenance.

**Expected Errors:** `TypeError` or `AttributeError` for invalid experiment or
observation inputs. Empty observations return a valid non-interpretable result.

**Caller Types:** Human UI, Agent, CLI, Future API. The experiment brief preview
is the first composed application caller.

## Produce Experiment Brief

**Name:** `produce_experiment_brief`

**Purpose:** Compose an instrument-independent report preview from an
authoritative Experiment, with a DLS convenience composition for parsed
samples, without coupling scientific reasoning to Streamlit, document export,
or DLS-only decision ranking.

**Inputs:** One `Experiment` containing its normalized observations and evidence
counts, or a non-empty list/tuple of parsed DLS samples plus an optional label.
The parsed-sample path assembles the same DLS experiment and normalized
observations inside the application boundary; established Experiment callers
remain authoritative and unchanged.

**Outputs:** A deeply frozen, versioned `ExperimentBriefPreview` containing an
immutable experiment identity, summary, completeness and interpretability state,
five canonical report sections, and immutable observation evidence. Serialization
returns plain dictionaries and lists without exposing domain models or DataFrames.

**Expected Errors:** `ValueError` for empty parsed DLS evidence and `TypeError`
for unsupported or malformed inputs. Empty observation streams on an
authoritative Experiment produce a valid non-interpretable preview through the
established Investigator behavior.

**Caller Types:** Human UI, Agent, CLI, Future API. Streamlit's generic Experiment
Brief is the first direct caller.

## Candidate Capability Backlog

These are capability boundaries, not implemented public contracts:

| Candidate name | Scientific intent | Current owner |
| --- | --- | --- |
| `generate_hypotheses` | Generalize deterministic, evidence-linked hypotheses beyond the available filtration-specific read | Technique modules/application |

Promote candidates one at a time when an existing human workflow can become the
first real caller. Define typed inputs, stable read outputs, validation, and
focused compatibility tests during promotion.

## Error Direction

The initial capabilities preserve current exceptions for backwards
compatibility. Do not add an exception hierarchy solely for architectural
symmetry. Introduce small application-level errors only when at least two
capabilities need consistent handling for invalid input, not found, conflict,
unsupported evidence, or persistence failure.

Network status codes and authentication failures do not belong in this layer.

## Domain Boundary

Current import capabilities return `Experiment` because the human UI and
scientific core already use that model. This is a transitional in-process
contract, not permission for remote clients to mutate domain objects.

External-facing readers should prefer versioned snapshots or future report and
context contracts. New callers should not construct `Experiment`,
`Observation`, or persistence records when a capability can perform the same
workflow with validation and provenance.

## Recommended Next Step

Isolate `retrieve_dls_raw_evidence` behind an explicit raw-source adapter
contract. Preserve arbitrary table cells, metadata, source text, upload-group
diagnostics, and immutable output ordering while keeping raw vendor inspection
separate from normalized Measurement science.
