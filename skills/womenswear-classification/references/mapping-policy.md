# Taxonomy Mapping Policy

Use the following preference order:

1. Exact registered label or alias supported by the evidence span.
2. Registered child node whose meaning is fully supported by the source.
3. Registered parent node when the evidence is not specific enough for a child.
4. Unresolved when multiple nodes remain plausible or no registered node applies.

An Agent may choose among visible candidates, but platform code validates node existence, taxonomy version, confidence range, and evidence-span provenance.
