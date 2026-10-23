# Optix: match insights that are true and not misleading

**The problem.** Live football graphics move fast, and a number can be true and still mislead: a
side "dominating territory" while it protects a lead, twenty shots worth almost nothing, a creator
whose chances are mostly corners. Language models make it worse: fluent with numbers they never checked.

**What Optix does.** Optix turns a synthetic event stream into live talking points and overlays
with their evidence. A deterministic engine computes every
number, a two-part Verifier fact-checks the claim against the event log and asks whether a true fact
would mislead in context (game state, sample size, metric limits), and only then is a sentence
written. A blocked claim goes back to the Analyst to be rewritten with its context, or it is dropped.
The dashboard shows before and after.

**Where Microsoft fits.** The agents run as a Microsoft Agent Framework workflow with a deterministic
Verifier and a conditional block-and-revise edge. An Azure OpenAI model in Azure AI Foundry, called
with Microsoft Entra ID, may only reword a claim the Verifier already approved; it sees the claim
object, never the events. Every reply passes an output guard (same numbers in each language's own
format, no new teams or players, no predictions, length and language) or the template is used and
the rejection is logged. OpenTelemetry spans target Application Insights, every publication
lands in a hash-chained audit log, and a FastAPI service streams verified insights over server-sent
events to the dashboard, packaged for Azure Container Apps.

**Honest status.** The workflow, guard, telemetry, audit log and live stream are verified by tests.
The Azure services are built, not yet verified live; docs/AZURE.md shows which is which.

**Why it matters.** Studio teams get speed without losing trust in the number on screen.
