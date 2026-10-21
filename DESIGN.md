---
name: LexBridge
description: A split-flap departures board for India's criminal law renumbering
colors:
  housing: "#1c1e21"
  housing-hi: "#25282c"
  bezel: "#0e0f11"
  flap-top: "#35383d"
  flap-bottom: "#2a2c31"
  flap-char: "#f1ede2"
  code-amber: "#ffbe2e"
  status-go: "#4cc47e"
  status-wait: "#f59a3a"
  status-stop: "#f07161"
  dim: "#9298a0"
  paper: "#eef0f2"
  paper-ink: "#15171a"
  paper-muted: "#50565e"
  rule: "#3a3d43"
typography:
  flap:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(13px, 1.45vw, 21px)"
    fontWeight: 600
    lineHeight: 1.42
    letterSpacing: "normal"
  display:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(2rem, 4.4vw, 3rem)"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.05em"
  label:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.12em"
  body:
    fontFamily: "Barlow, Helvetica Neue, Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
rounded:
  flap: "2px"
  control: "6px"
  board: "10px"
  paper: "0"
spacing:
  row: "6px"
  group: "22px"
components:
  ask-key:
    backgroundColor: "{colors.flap-char}"
    textColor: "{colors.bezel}"
    typography: "{typography.display}"
    rounded: "{rounded.control}"
    padding: "14px 26px"
  cite:
    backgroundColor: "{colors.bezel}"
    textColor: "{colors.code-amber}"
    rounded: "{rounded.flap}"
    padding: "4px 12px"
  question-field:
    backgroundColor: "{colors.bezel}"
    textColor: "{colors.flap-char}"
    rounded: "{rounded.control}"
    padding: "12px 14px"
  notice:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.paper-ink}"
    rounded: "{rounded.paper}"
    padding: "22px 24px 20px"
---

# Design System: LexBridge

## Overview

On 1 July 2024 every section number in India's criminal law changed. LexBridge is a split-flap departures board: the answer arrives as rows of flaps that turn from blank (or from the last answer) to the sections that apply, showing each section's code, number, its counterpart in the other code, its title, and whether it was cited or only a source. While the answer is being checked the flaps scramble; that is the loading state.

The world is a painted charcoal housing with a recessed bezel. Prose that a board cannot carry (the answer, the statute text) is printed on paper sheets pinned beneath it. One committed dark theme: a real board has no daytime mode.

## Colors

### Primary
- **Code amber** (`code-amber`): only for code letters (IPC/BNS) and citation chips. Never for status, controls or body text.

### Neutral
- **Housing** and **housing-hi**: the page and hover/selected rows.
- **Bezel**: the recessed board and input wells.
- **Flap top / flap bottom**: the two painted halves of every flap; **flap-char** is the cream lettering.
- **Paper / paper-ink / paper-muted**: printed sheets under the board.

### Named Rules
- **Status Is Not The Accent.** `status-go`, `status-wait`, `status-stop` mean answered, needs a date, and outside the codes or failed. They appear on the status column, the cited-row light, the message row and the notice's status flap, and nowhere else.
- **No Glow.** Depth comes from the bezel's inset shadow and the flap split line; no coloured halos.

## Typography

Barlow Condensed for everything that lives on the board or labels it; Barlow for prose. Both self-hosted (latin subsets) from @fontsource.

### Hierarchy
- **Flap** text is uppercase, one character per cell, cut at the column width.
- **Display**: the housing nameplate, tracked caps.
- **Label**: field and column labels, tracked caps.
- **Body**: answers, statute text and notes, at 65 to 70 characters a line.

## Layout

One column, max 1240px: a raised housing panel holding the nameplate, the changeover readout (IPC, 01 JUL 2024, BNS on flaps) and the console (question, date clock, Ask key); then the board, papers (answer notice beside the opened section), proof, footer. The board has five rows and a message row. Below 760px each row stacks: code, number and counterpart on one line (the renumbering is the point), the title beneath; the status column gives way and cited rows keep their green left-edge light.

## Elevation & Depth

The board is recessed (inset shadow), flaps sit proud by one pixel, paper sheets cast a soft drop shadow onto the housing. The Ask key has a short base shadow that collapses when pressed.

## Shapes

Flaps 2px, controls 6px, board 10px, paper square (paper is cut, not moulded).

## Components

### Split-flap strip
A fixed-width row of cells. Changing its text turns only the cells whose character changed, forward through the drum (space, A to Z, 0 to 9, punctuation), one step every 32ms; reduced motion shows the final text at once. Flaps are `aria-hidden`; each board row is a button whose label reads the row in plain words.

### Date clock
Day, month and year flaps plus the code in force for that date. The real control is a native date input laid transparent over the flaps, so typing, the picker and assistive technology all work.

### Notice and section sheet
Square paper sheets. The notice carries its status as a flap stamp beside the heading (ANSWERED, NEEDS DATE, NOT COVERED). Section text is reflowed from the gazette's printed line breaks, keeping breaks before sub-sections, Explanations and Illustrations.

### Buttons
The Ask key is the only filled control: cream, like a flap, with a dark legend and a short base that collapses when pressed. Example questions and secondary actions are outlined condensed caps; text actions are underlined.

### Receipt view (second style)
A Board | Receipt switch in each header picks the page style; the choice is remembered per browser and `/?view=receipt` links to it. The receipt view is its own scoped world (`.kiosk-page` tokens in `receipt.css`, loaded only when chosen): a graphite help-desk kiosk with a pale-blue screen and a yellow Print key, and the answer printed as thermal paper (Sometype Mono, torn edge) ending in a Code 128 barcode of the trace id. An opened section prints as a second slip beneath. Same logic, states and accessibility as the board; only the presentation differs. The board's rules (amber for code letters only, no light theme) govern the board view only.

## Do's and Don'ts

### Do:
- Show every section number on flaps, with its counterpart in the other code.
- Let the board scramble while the answer is checked, and settle only the cells that change.
- Keep model output as text; never render it as markup.

### Don't:
- Don't add a light theme or a second accent hue.
- Don't put prose on the flaps; long text belongs on paper.
- Don't flip cells whose value did not change.
