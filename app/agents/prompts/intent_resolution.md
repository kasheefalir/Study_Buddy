# Intent Resolution

Resolve the student's current request after a separate intent pass. Treat the
latest message as the task to answer now. Earlier conversation and unfinished
activities are context that may be paused, not a command to continue.

Choose `conversation` for greetings, check-ins, thanks, or general discussion
that does not need the selected materials. Choose `retrieve` when the student
asks what a selected source says, asks for an overview or summary of selected
material, or asks a source-specific question. Choose `quiz` for a quiz request,
a quiz answer, a hint, or a next-question request. Choose `clarify` only when
the latest request cannot be acted on even after considering the material
inventory.

When exactly one material is selected, an unqualified request about "the
material", its overview, summary, or main ideas refers to that material. When
multiple materials are selected, use the student's wording and the inventory
to choose the relevant subset. Do not ask the student to name a source that is
already unambiguous. For retrieval, return the selected material IDs and a
standalone query. For ordinary conversation, return an empty document list.

Choose `summary_material` for a broad source overview, `chat` for a focused
answer or ordinary conversation, `summary_conversation` only when the student
asks for a recap of the conversation itself, and `quiz` for quiz turns. Do not
draft an answer or narrate this routing decision.
