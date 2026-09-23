---
type: cog [0.1]
name: cog-merge-findings-candidate
description: "Merge detector findings across batches and repeats with traceable provenance."
version: "0.1.0"
manifest: cog.yaml
manifest_schema: openteams/cog-manifest [0.1]
license: Apache-2.0
---

# cog-merge-findings-candidate

This pure code Cog consolidates one detector kind's batch-and-repeat results. It is the reusable consolidation step between detector fan-out and cog-rank-next-up, cog-compose-proposals, and human review. It is a fresh candidate, not an automatic replacement for cog-merge-findings. The reference implementation is neither included nor imported.

The task is `run(bundle, grant, journal)`, returning `(payload, problems)`. The host invokes run with `--bundle`; the host owns the execution envelope. The payload contains abstained, findings, provenance, and authority_use. Model requirements are none, locality is local, reaches is empty, authority_use is always [], and grant and journal are unused. Runtime work is bounded by the supplied finite input; it performs no I/O. The supplied jsonschema dependency validates in-memory data; no additional dependencies are needed.

Input and output schemas are the accepted reference schemas, including their descriptions and $defs. Batches are aligned positionally with repeat lists. Nulls are failed repeats. An unreadable detector object produces an error `result-shape` and is skipped without refusing the step. Invalid top-level input produces check_input problems. An out-of-batch finding produces error `finding-outside-batch` and is dropped; its otherwise valid answer remains accepted. Problems do not themselves decide host success or acceptance: ok:true may carry problems.

Overlap keys are sorted distinct item-id tuples and relationship values. Dependency keys are ordered (blocking, blocked) pairs and basis values. Keys sort lexicographically using Python string/tuple order. Findings receive m-1 through m-n in that order. Each group keeps the source with most citations, then longest citation, then earliest input batch and repeat; an exact tie within a repeat keeps its first finding. Kept finding fields, including overlap item_ids order and multiplicity, remain unchanged except finding_id. All finding text is copied verbatim, and instruction-like text remains data.

Support counts distinct (batch_id, repeat) occurrences, even if multiple findings in a repeat name the same relationship. Every occurrence still competes for text. The denominator counts schema-valid, non-null answers whose batch contains every named item, including answers with no findings. There is no support threshold. Support is observation frequency, not truth, probability, or confidence.

Different values for an overlap key remain separate and produce one warn `findings-disagree` per relationship. Dependency stated-wins is a declared policy: a stated edge absorbs inferred occurrences without a disagreement warning. Stated support and occurrences remain stated-only. also_inferred carries distinct inferred-repeat count, longest inferred rationale (earliest on ties), and sorted unique qualified sources. Those sources also appear in source_finding_ids. An empty rationale represents null source rationales; otherwise rationale text is copied without rewriting. Stated-wins does not prove a citation correct.

All source references are sorted unique (batch_id, repeat, source_finding_id) triples. Every provenance entry carries cut_item_ids: sorted unique named items cut in batches represented by that entry's occurrences. Missing cuts means none; only cut item ids affect merging. Folded inferred batches do not add stated occurrences or cuts. Unknown cut metadata is ignored. Abstained is the conjunction of accepted answers' abstained flags. With no accepted answers it is true and warn `no-results` is emitted, including null-plus-unreadable-only input.

The independent validation surrounding this unit is the Op's per-repeat Gates, host input/output schema validation, downstream Op Gates, and human review. Detectors' own contract checks and this Cog's check_input, check_output, and tests are package checks, not independent Guards or acceptance authorities. check_output validates shapes and recomputes the deterministic contract to check grounding, ordering, support, sources, cuts, folds, and text selection. Tests use independent expected observations rather than using that recomputation as their oracle.

Unsupported work includes running detectors, cross-kind merging, inventing or rewriting findings, resolving disagreements beyond stated-wins, dropping low-support findings, model calls, network, subprocesses, filesystem effects, use of grants or journals, and new infrastructure.

Prohibitions, exactly as accepted:

- model_calls
- network_access
- external_effects
- adjudicating_disagreements_beyond_stated_wins
- dropping_findings_for_low_support
- inventing_findings
- cross_kind_merging
- building_detectors
- modifying_cog_merge_findings
- additional_third_party_dependencies

Tests cover happy, insufficient, adversarial, boundary, and invalid inputs; schema bytes and embedded definitions; both complete consumer requests; closed-consumer discrimination; and malformed output. No execution is claimed in this handoff.

## Reference comparison handoff

`tests/fixtures/shared-cases.json` is a portable list of named, schema-valid bundles with independently specified expected payloads and problem check/severity pairs. The host feeds each bundle to both implementations and compares payloads and problems. Candidate tests require no reference installation. The host must report full problem-detail differences as well as behavioral differences; expected problem pairs intentionally do not assert the reference's unavailable wording.

The caller-supplied differential-v1 record reports a measured, intentional dependency ordering divergence: the unchanged reference sorts dependency edges by (blocked, blocking), while this accepted contract and candidate sort by (blocking, blocked). Three of 54 reference fixtures differ only in output ordering and m-IDs; all 54 relationship/provenance pairs match. This result is reported from supplied evidence, not independently executed or authenticated by this author. The candidate retains the accepted ordering; the algorithm is not changed to hide the difference.

Other intentional clarifications relative to ambiguous reference documentation are: no-results fires whenever there are no accepted answers, including unreadable-only input; overlap item_ids stay in the selected source's order; exact within-repeat ties retain first occurrence; folded inferred batches do not add stated cut_item_ids. Key-to-id order is invariant under batch permutation, but tied text selection and occurrence order follow input order. No other behavioral divergence is intended. The host must investigate any other difference rather than accepting it silently.

The reference's compose-proposals fixture is known stale. Current supplied consumer fixtures are authoritative here. Tests report that baseline drift as a warning, not a suite failure. The stale fixture and reference source are not supplied, so the host owns their actual comparison. Tests pin the supplied schema bytes and compare serialized embedded $defs byte-for-byte with standalone fixtures; schema changes must be reviewed explicitly.
