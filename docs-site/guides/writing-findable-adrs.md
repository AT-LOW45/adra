---
title: Writing ADRs an agent can find
description: Why a coding agent misses the convention you wrote down, and what to change.
date: 2026-11-22
---

# Writing ADRs an agent can find

<!--
DRAFT — not written yet.

Measured findings from tuning this knowledge base, to draw on. All numbers are the
relevance score for the query against the ADR, as the Search Tuning page reports them.

1. ADRs get written in the vocabulary of their SOLUTION; agents search in the
   vocabulary of their PROBLEM.

   ADR-005 "Async Operations with UI Feedback", same task, four phrasings:

     0.550  show a loading spinner while saving a form
     0.636  show a loading spinner during an async api call
     0.627  disable a button while an async call is running
     0.601  submit a form and show an error toast on failure

   It named its own hook and said "async", but never "form" or "saving".

   Adding one sentence to the front of its Context:

     "When a user saves a form, we need to show a loading spinner, disable the save
      button while the request is in flight, and show an error if it fails."

   took the first query from 0.550 to 0.744. Across six phrasings, five improved and
   the floor rose from 0.542 to 0.578 — the floor being what matters, since the weakest
   query is what sets the threshold.

2. SPECIFIC BEATS COMPREHENSIVE — the counterintuitive one.

   ADR-005's Scope listed five situations (form, list, delete, button) and scored
   0.501, second-worst of its six chunks. Listing many topics gives a vector strongly
   about nothing. One vivid scenario scored higher even for the OTHER five queries.

   So stuffing in keywords makes it worse, not better.

3. ONLY THE BEST-MATCHING CHUNK COUNTS.

   An ADR is scored by its single strongest section, so concentrating the task
   language in one place beats sprinkling it everywhere. Per-chunk scores for
   "show a loading spinner while saving a form":

     0.526  # ADR-005: Async Operations with UI Feedback   (title)
     0.501  ## Scope
     0.583  ## Context          <- the deciding chunk
     0.550  ## Decision
     0.499  ## Implementation
     0.519  ## Consequences

4. THE TITLE IS ITS OWN CHUNK, and appears nowhere else. Chunks carry only their own
   heading, so the H1 contributes to exactly one chunk:

     0.523  "Async Operations with UI Feedback"
     0.658  "Loading Spinners, Disabled Buttons and Errors for Async Actions"

5. A HEADING GLUED TO THE END OF A SENTENCE SILENTLY DESTROYS THE SECTION.

   ADR-005 had "...inconsistently across the app.## Decision" on one line. Markdown
   only treats ## as a heading at the start of a line, so the chunker never split
   there and both Context and Decision were buried inside Scope's chunk. Nothing in
   the UI showed this — the sections simply weren't there. Fixing it alone moved the
   weak query from 0.550 to 0.583.

6. SCORES ARE NOT PERCENTAGES. They bunch into a narrow band, so read the gap, not the
   absolute. Every ADR scored 0.44–0.59 for a query none of them covered:

     0.593  ADR-006      <- "sort a list of dicts by a key" matched an endpoint-layering
     0.501  ADR-002         ADR, because its code example contains list[dict]
     0.480  ADR-001
     0.472  ADR-004
     0.457  ADR-005
     0.438  ADR-003

Note for sharing: this should be useful to someone who never installs Adra. "Check
whether the first sentence of each section describes the problem or the solution"
works in any text editor.
-->
