"""Optix agents: plain Python classes around the deterministic engine.

Ingest -> Analyst -> Verifier -> (Analyst revision loop) -> Narrative -> Personalization, run by
agents.orchestrator.Orchestrator. No agent computes a number itself: the Analyst asks engine.claims
for claim objects, the Verifier is engine.verifier, and the Narrative fills templates with the
verified params. No external API calls.
"""
