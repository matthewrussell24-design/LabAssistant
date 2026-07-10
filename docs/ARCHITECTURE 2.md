# LabAssistant Architecture Notes

This file is a legacy duplicate kept only for compatibility with older local
handoffs.

Use `docs/ARCHITECTURE.md` as the canonical architecture document and
`docs/STANDALONE_APP.md` for the standalone app and future agent-access
direction.

Current architecture direction:

```text
Streamlit shell now, future app shell later
  -> application queries and commands
  -> Experiment / Observation / Measurement core
  -> ingestion, reasoning, memory, reports
  -> read-only agent access after the service layer is stable
```

Do not add speculative agent infrastructure, autonomous lab actions, instrument
control, or remote API hosting before the human app workflows and application
service layer are stable.
