# Classmate facts integration

The classroom has two companion actors. They select facts from an already prepared
list; hovering and interacting never call Ollama or any other model.

When ingestion has produced source-backed facts and a document is selected, dispatch:

```js
window.dispatchEvent(new CustomEvent("study-material-facts", {
  detail: {
    documentId: "document-id",
    facts: [
      {documentId: "document-id", text: "An extracted fact.", source: "Week 5, slide 3"}
    ]
  }
}));
```

Replace the list whenever the active document changes. Dispatch an empty list when
it is deselected or removed. Only entries matching the active document, with both
text and source, are shown. Each classmate takes a stable position in the list so
their tooltip and conversation show the same fact. Random sampling of a larger
fact bank can happen before dispatch, without using an agent.

Until ingestion provides real facts, classmates show a neutral study greeting.
No document facts are fabricated.
