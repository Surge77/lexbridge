---
version: 1
slug: "web-src-app-tsx"
primary_target: "web/src/app.tsx"
related_targets: ["src/lexbridge/api/static/index.html"]
---

## Scope

The LexBridge page served at GET / (Operate mode). Mixed audience: public asking in plain words, legal
professionals mapping IPC numbers to BNS. One question at a time; answers in about a second.

## Direction contract

THESIS: Every section number changed on 1 July 2024; the page is a split-flap departures board that makes
the renumbering physical. It refuses the chat-box-plus-answer-card arrangement every RAG demo ships.

OWN-WORLD: Painted charcoal housing with real depth, a recessed bezel, dark painted flaps with cream lettering split by a hairline,
amber reserved for code letters, green/amber/red only for answer status. Condensed grotesk on the flaps,
plain grotesk on printed notices. No glow, no gradients beyond the flap bevel.

STORY: The visitor types what happened, sets the date on a flap clock if they know it, and the board
scrambles while the answer is checked, then settles on the sections that apply with their old and new
numbers. A printed notice under the board carries the answer prose; any row opens the section text.

FIRST VIEWPORT: Housing header with the name and the changeover date; the question strip and flap date
clock with the Ask key directly above the board; the board fills the rest of the viewport width with
five rows and a message row. Before any question, the rows show real mappings (420 to 318(4), 302 to
103(1), 379 to 303(2), 415 to 318(1)).

FORM: Split-flap departures board, list position 3 of round 2, chosen by the user. Seed 638eb8e2.
Signature interaction: only changed cells flip, and the scramble doubles as the loading state.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
