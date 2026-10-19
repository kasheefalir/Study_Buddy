"""Candidate query clarification instruction; not enabled in production."""

FOLLOWUP_GUIDANCE = """
The query must stand alone without dialogue. Name the subject explicitly even
when reuse_evidence is true. Resolve pronouns using the prior material request
and recent dialogue; never return only 'explain that' or 'give an example'.
Preserve the operation in latest_message: a request for a hypothetical example
must remain a request for a hypothetical example, not just a definition or
simplification. intent.query is a hint, not authority over latest_message.
For a new subject, use the new subject rather than the previous topic. Preserve
all parts and qualifications. Reusing evidence does not excuse an unresolved
query. A query describes what to look for; it must not assert an answer.
"""
