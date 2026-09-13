# Ship 30 for 30 Essay Skill

A reusable skill (not a one-line prompt) that turns grounded transcript
evidence into a ~1,250-word Ship 30 for 30-style essay. Ship 30 for 30 is a
writing method for short, high-signal online essays: a strong hook, one
central idea, a clear narrative arc, and a concrete, usable takeaway --
written to be read on a phone in under 6 minutes.

## Pipeline

```
Grounded transcript context (from search_transcripts)
        |
        v
1. Identify central insight        -- what is the ONE idea this essay is about?
2. Identify tension / problem       -- what makes this non-obvious or hard?
3. Extract supporting evidence      -- claims tied to specific retrieved excerpts
        |
        v
   Ship30Outline (validated Pydantic object, schema.py)
        |
        v
4. Construct hook                  -- first 1-2 sentences, no throat-clearing
5. Narrative progression            -- problem -> evidence -> reframe
6. Practical insight                -- the "so what"
7. Useful takeaway                  -- one thing the reader can do this week
        |
        v
   Full markdown draft (writer.py)
        |
        v
8. Validate (validator.py)          -- word count band, headings, bullets, bold
        |
        v
   Markdown artifact
```

## Why two model calls instead of one

Stage 1 produces a small, structured `Ship30Outline` (central insight,
tension, evidence list, hook, practical insight, takeaway) as JSON. Stage 2
expands that outline into full prose. Splitting it this way means:

- The essay's evidence is pinned to specific retrieved excerpts *before* any
  prose is written, so the writer stage can't quietly invent a supporting
  anecdote -- it can only elaborate on evidence that already passed through
  the structured outline.
- We can reject/flag an outline whose evidence list is empty (i.e. retrieval
  didn't surface enough to write a grounded essay) before spending a second,
  more expensive generation call.
- It keeps each prompt small and fast, which matters when running on a local
  Ollama model on CPU.

A single mega-prompt was considered and rejected: it produced essays that
occasionally cited a paraphrased "fact" with no traceable source, which
violates the grounding contract (architecture.md, "Grounding contract").

## Grounding rule

If retrieval returns fewer than 2 relevant chunks, the skill refuses to
fabricate an essay and instead tells the user retrieval was insufficient
(see `writer.py: generate_ship30`). Every `EvidencePoint` in the outline must
carry the source title and an excerpt that is a substring of (or very close
paraphrase check against) retrieved content -- outlines with unverifiable
evidence are flagged with a validation warning rather than silently trusted.

## Output contract

- Markdown, ~1,250 words (target band: 938-1,563, i.e. +/-25%, since "approximately"
  is explicitly the assignment's own word choice)
- >=2 headings (skimmable structure)
- >=2 bullet lists
- >=2 bold emphasis spans (selective, not decorative)
- One explicit, concrete takeaway in the closing section
