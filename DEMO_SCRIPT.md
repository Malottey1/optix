# Optix demo script (about 110 seconds)

Screen recording of the dashboard served by the Optix API (`uvicorn service.app:app`, then
http://127.0.0.1:8000/#/live at 1920x1080), plus two terminal shots. Fictional teams and synthetic
data only. Microsoft technologies are named in text and voice only: no logos, no third-party marks,
no music (voice only, or silence).

| Time | Shot | On screen | Spoken |
|---|---|---|---|
| 0:00-0:10 | Title card | "Optix: match insights that are true and not misleading" | "A number on a broadcast can be true and still mislead. Optix makes sure every insight is both true and fair, and shows the evidence." |
| 0:10-0:25 | Live Center, kick-off | Scoreboard chip reads **Live stream**; the first cards arrive | "This is a synthetic match, streamed live from the Optix server over server-sent events. Every card was computed by a deterministic engine and checked by a Verifier before any sentence was written." |
| 0:25-0:42 | Live Center, a rewritten card | Open the field-tilt card; toggle Before / After; the reason line | "Here the Analyst first said one side held most of the territory. True, but they were leading and sitting deep. The Verifier blocked it and sent it back; the published version carries that context." |
| 0:42-0:55 | Evidence drawer | Click Evidence: event chain on the pitch, the event table | "Every claim is a claim object: metric, value and the event IDs behind it. Click any card and you see exactly which events back it." |
| 0:55-1:05 | Language switch | Settings: Spanish, then French; the numbers stay identical | "Translation happens after verification, and a guard re-checks that every number in every language matches the claim." |
| 1:05-1:22 | Tech Blueprint, Microsoft and Azure panel | The status list: verified by tests / built, not verified live | "The agents run as a Microsoft Agent Framework workflow with a block-and-revise edge. An Azure OpenAI model in Azure AI Foundry may reword an approved claim, using Microsoft Entra ID, but an output guard rejects any new number, team or prediction and falls back to the template. This panel says honestly what is verified by tests and what is built but not yet verified live." |
| 1:22-1:35 | Terminal: guard tests | `python -m pytest -q tests/test_phraser.py tests/test_workflow.py` passing | "These tests feed the guard hostile model replies: altered numbers, other teams, betting language, a wrong decimal comma. Every one is rejected." |
| 1:35-1:45 | Terminal: audit | `python -m agents.audit verify out/audit.jsonl`, then the same after editing one line: chain broken | "Every publication goes into a hash-chained audit log. Change one record and verification fails: tamper-evident, with OpenTelemetry spans ready for Application Insights." |
| 1:45-1:50 | End card | "Optix" and the repository URL | "Optix. Fast insights you can trust. github.com/Malottey1/optix" |

Recording notes:
- Prepare the audit shot with `python -m agents.run_match --audit out/audit.jsonl` beforehand.
- Keep the browser at 1920x1080 so every Live visual is on the first screen.
- If the API is not running, the chip reads Replay: say "replay" instead of "live" in the second shot.

Repository: https://github.com/Malottey1/optix
