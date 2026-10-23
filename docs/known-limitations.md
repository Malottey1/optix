# Known limitations

Honest list of what Optix does not do, or does only partly. Live status of every Microsoft / Azure
piece is in docs/AZURE.md (generated from repo facts); this page explains the gaps.

- **The guard's language check is a heuristic.** `agents/output_guard.language_of` counts common
  function words per language. It is tuned so every template sentence reads as its own language (a
  test enforces that), but it is not a language model: a very short or unusual model sentence can be
  rejected (the template is then used, which is safe), and a sentence that mixes languages with
  enough function words of the requested one could pass this one check (the number, entity and
  forbidden-phrase checks still apply).
- **No Event Hubs adapter.** Events are replayed from files in process; the service streams the
  already-verified insights. Ingesting from Azure Event Hubs is not built.
- **The Azure OpenAI client and the Application Insights export are not verified live** (as of the
  status in docs/AZURE.md: "built, not verified live", live check "not run"). They have only run
  against a fake model client and a fake connection string. `tools/azure_live_check.py` is the way to
  verify them; until it runs with Azure settings, nothing Azure-hosted is claimed to work.
- **Deployment is not exercised.** The image build and the Bicep compile run in CI (when
  infra/ci-verified.json records it, docs/AZURE.md says so), but no resource has ever been deployed.
- **Old screenshots keep the old team code.** `docs/screens/` and `docs/screens-v2/` are history
  and still show `NOR`; the team was renamed `NTG` everywhere else, and `docs/screens-v3/` shows the
  current dashboard.
- **docs/robustness.md section 4 (pooled Verifier rules) predates a Verifier change.** Its
  field-tilt row was measured before 09c3836 changed that rule; sections 1-3 are current (confirmed
  with the repaired tool on seed 2026). Current Verifier recall is in docs/verifier-recall.md.
- **Exported stream files carry no wall-clock fields.** `emitted_latency_ms` and `verified_at` are
  `null` in web/public/data so exports are reproducible; the measured values are in the gitignored
  `out/runtime.jsonl` of each run.
