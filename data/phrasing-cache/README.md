# Phrasing cache

Model-written sentences that passed the output guard (`agents/output_guard.py`), one JSON file per
claim: `<deployment>/<prompt version>/<claim hash>.json`. The key is the hash of the
language-independent claim object the model saw (`agents.phraser.model_input`), the deployment
name and the prompt version, so a changed claim, model or prompt never reuses an old sentence.
Each file records its origin (source, deployment, creation time, guard).

Replays read this folder offline (`python -m agents.run_match --phraser azure` without Azure
settings), and every cached sentence passes the output guard again before it is used, so an edited
file cannot put an unguarded sentence in the stream.

Entries are written only by a live run (`tools/azure_live_check.py`, or `run_match --phraser azure`
with Azure settings). Until such a run happens this folder holds no sentences.
