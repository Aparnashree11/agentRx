# AgentRx benchmark releases

This folder contains immutable releases of the benchmark data already used by
the project. The baseline files are byte-for-byte copies of the existing local
inputs and labels. They have not been cleaned, normalized, filtered, or
converted. The manifests preserve the original source paths for provenance, but
the frozen release artifacts are self-contained and do not depend on those
original folders being present.

## Baseline releases

- `tau_retail/baseline/v1.0.0/manifest.json`
- `magentic_one/baseline/v1.0.0/manifest.json`

Each manifest records the original project paths, the copied artifact paths,
trajectory IDs, row counts, and SHA-256 checksums. Tau Retail freezes the 29
failed trajectories and their 29 labels. Magentic-One freezes all 58 trajectory
files and the existing 44 labels; only those 44 annotated IDs have benchmark
labels. The Tau release is scoped to the 29 failed trajectories and does not
include the broader 100-row Tau pool.

## Adding reworded datasets

Create a new release directory rather than editing a released version. For
example:

```text
data/benchmark_versions/tau_retail/step_decoy/v1.0.0/
  trajectories.jsonl
  manifest.json
```

Copy the corresponding baseline artifacts into the new release, change only
the trajectory text needed for that rewording, and leave the source baseline
untouched. The new manifest should identify its parent baseline release and
checksum, store a checksum for every artifact, and record the generation model,
prompt version or hash, settings, and seed. Record the label-preservation check
and its result. Reuse the baseline annotations when labels are unchanged. Keep
each domain and rewording type in its own release path. Never overwrite an
existing release; changes to model-visible trajectory content create a new
version.
