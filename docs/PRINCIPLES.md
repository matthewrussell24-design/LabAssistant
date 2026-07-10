# LabAssistant Principles

> *Every architectural decision should reinforce these principles. When tradeoffs arise, these principles take precedence over convenience.*

---

# Purpose

LabAssistant exists to transform laboratory data into scientific understanding.

It is not simply a data viewer.

It is not simply an LIMS.

It is not simply an AI chatbot.

LabAssistant is an Experiment Intelligence Platform.

Its purpose is to help scientists think more clearly, preserve institutional knowledge, and accelerate scientific discovery.

---

# Principle 1
## Scientific Understanding Before Software Features

Every feature should improve scientific understanding.

Avoid building features simply because they are technically interesting.

Ask:

> Does this help a scientist reach better conclusions?

If not, reconsider it.

---

# Principle 2
## Evidence Before Conclusions

Every conclusion must be traceable.

Raw measurements become evidence.

Evidence supports observations.

Observations support findings.

Findings support hypotheses.

Hypotheses support investigations.

Investigations lead to conclusions.

Every conclusion should preserve its provenance.

---

# Principle 3
## Instrument Independence

LabAssistant should never become "the DLS application."

Every instrument is simply another source of evidence.

Scientific reasoning should remain consistent regardless of whether the data originated from:

- DLS
- Chromatography
- Microscopy
- Flow Cytometry
- Mass Spectrometry
- Instruments not yet imagined

The reasoning engine should outlive every individual instrument integration.

---

# Principle 4
## Humans Remain in Control

LabAssistant augments scientists.

It does not replace scientific judgment.

Recommendations are recommendations.

Evidence is transparent.

Reasoning is inspectable.

Scientists make the final decision.

---

# Principle 5
## Explain Everything

The platform should never produce unexplained conclusions.

Users should always be able to answer:

- Why was this observation generated?
- Why was this hypothesis suggested?
- What evidence supports this finding?

Reasoning should be visible.

---

# Principle 6
## Preserve Scientific Memory

Scientific knowledge should accumulate.

LabAssistant should become the laboratory's long-term memory.

Experiments should not disappear after reports are written.

Observations should remain searchable.

Ideas should be preserved.

Institutional knowledge should grow over years.

---

# Principle 7
## Design for Reuse

Every capability should be reusable.

The UI should not own scientific workflows.

APIs should reuse the same capabilities.

Future AI agents should use the same capabilities.

One implementation.

Many interfaces.

---

# Principle 8
## Incremental Evolution

Prefer small architectural improvements over sweeping rewrites.

Protect existing workflows whenever practical.

Maintain backwards compatibility whenever reasonable.

Refactor deliberately.

---

# Principle 9
## Documentation Is Part of the Product

Architecture is documentation.

Prompts are documentation.

Standards are documentation.

Current project state is documentation.

Documentation is never an afterthought.

It is part of the software.

---

# Principle 10
## Build for the Next Decade

Optimize for what LabAssistant can become.

Do not optimize only for today's experiments.

Prefer decisions that remain correct as:

- more instruments are added
- more laboratories adopt the platform
- more AI capabilities emerge
- larger datasets appear

Think in decades.

---

# Principle 11
## AI Is a Collaborator

AI assists.

AI reasons.

AI documents.

AI recommends.

AI accelerates development.

AI does not replace scientific responsibility.

Every recommendation should be explainable.

---

# Principle 12
## Simplicity Over Cleverness

The simplest architecture that supports future growth is usually the correct one.

Avoid unnecessary abstraction.

Avoid speculative frameworks.

Avoid complexity without purpose.

Clear systems outlive clever systems.

---

# Our Standard

When uncertain, ask:

1. Does this improve scientific understanding?
2. Does this preserve evidence?
3. Does this make future development easier?
4. Would another scientist understand this in five years?
5. Would another AI agent understand this in five minutes?

If the answer to any of these questions is "no," reconsider the design.