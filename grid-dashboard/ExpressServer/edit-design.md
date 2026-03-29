# `/edit` Layout Editor Design

This document is the handoff reference for the experimental layout editor served
at `/edit`. It is written so a future Codex session can continue iterating
without rereading the entire implementation history.

## Purpose

The `/edit` page is a modern-browser authoring tool for experimenting with a
future layout DSL.

Core idea:

- the canonical artifact is a token grid
- the editor renders that token grid as an emoji grid
- per-cell metadata such as `press` and `activeWhen` is edited alongside the
  grid
- room-specific variants are modeled as patches/deltas over a base layout

It is intentionally an editor/prototype, not the final parser or storage layer.

## Current Scope

Implemented:

- static page at `/edit`
- no framework; plain HTML/CSS/JS
- in-memory state only
- seeded layouts for current dashboard shapes
- base + room-variant patch model
- emoji preview grid
- inspector for selected cell metadata
- legend inside inspector
- token-grid output textarea
- variant metadata JSON textarea
- pointer-based drag-to-swap for normal cells
- merged marquee/status preview for contiguous `ST` runs
- status-block drag-to-move
- status-block multi-cell resize via left/right handles
- delete/backspace clear for selected cell
- undo stack + header button

Not implemented:

- persistence
- import from `config.js`
- parsing token-grid text back into state
- exporting a final DSL format
- validating actions/state expressions against runtime code

## File Map

Primary files:

- [edit-design.md](/Users/rtimmons/Projects/smarthome/grid-dashboard/ExpressServer/edit-design.md)
- [index.html](/Users/rtimmons/Projects/smarthome/grid-dashboard/ExpressServer/src/public/edit/index.html)
- [layout-editor.css](/Users/rtimmons/Projects/smarthome/grid-dashboard/ExpressServer/src/public/css/layout-editor.css)
- [layout-editor.js](/Users/rtimmons/Projects/smarthome/grid-dashboard/ExpressServer/src/public/js/layout-editor.js)

Serving model:

- `/edit` works automatically because `src/server/index.ts` serves `src/public`
  through `express.static`
- the editor is fully standalone and does not share logic with the main
  dashboard page

## UX Layout

The page has three major areas:

1. Canvas panel
   - page title
   - layout dropdown
   - variant dropdown
   - canvas header with layout title and floating undo button
   - emoji preview grid
2. Inspector panel
   - selected cell summary
   - large square token/emoji inputs
   - alias / press / activeWhen / overrideScope / notes fields
   - scrollable legend
   - reset-variant-cell button
3. Output panel
   - token-grid output
   - metadata JSON output

Important UX assumptions:

- clicking/tapping a normal cell selects it for the inspector
- dragging a normal cell swaps it with the destination cell
- the legend should scroll inside the inspector only
- outer page scrolling should not be triggered by grid interactions

## Seeded Layouts

Current seeded layouts in `layout-editor.js`:

- `default`
- `iphone_portrait`

Current seeded variants for each layout:

- `base`
- `living_room`
- `kitchen`

These are hand-authored approximations of the live dashboard layouts. They are
not imported from the production `config.js`.

## Data Model

### Top-Level Model

Runtime state is built from `LAYOUTS` into `runtimeLayouts`.

Conceptually:

- `runtimeLayouts[]`
- each layout has:
  - `id`
  - `title`
  - `rows`
  - `cols`
  - `baseGrid`
  - `baseCells`
  - `variants`

Each variant has:

- `title`
- `patches`

Each patch is keyed by `"row,col"`.

### Cell Model

Each effective cell object has:

- `row`
- `col`
- `token`
- `emoji`
- `alias`
- `press`
- `activeWhen`
- `overrideScope`
- `notes`

### Meaning Of `press` And `activeWhen`

- `press` is the action-like string to perform on tap
- `activeWhen` is a string expression describing active state

Example:

- speaker cells use `press: Music.ToggleRoom:Kitchen`
- speaker cells use `activeWhen: in_zone:Kitchen`

The editor does not evaluate these expressions. They are strings only.

### Token Defaults

`TOKEN_LIBRARY` is the canonical seed table for default token metadata:

- token -> emoji
- token -> alias
- token -> press
- token -> activeWhen

The editor falls back to `TOKEN_LIBRARY` defaults when constructing cells.

## Important Constants

These live near the top of `layout-editor.js`:

- `EMPTY_TOKEN = '..'`
- `STATUS_TOKEN = 'ST'`
- `GRID_CELL_SIZE = 80`
- `POINTER_DRAG_THRESHOLD = 8`

`GRID_CELL_SIZE` is currently used for coarse status-bar resize math. If resize
feels too sensitive or not sensitive enough, this constant is the first place to
adjust.

## Effective Layout Model

The preview and outputs operate on `effectiveCells()`:

- start with `layout.baseCells`
- overlay `variant.patches`
- return a cloned effective-cell map

This means:

- editing `base` mutates the layout’s `baseCells`
- editing a non-base variant writes/updates patch cells only

Patch cleanup:

- when a variant cell becomes identical to the corresponding base cell, the
  patch is removed
- this happens through `cleanupPatchForKey(...)`

## Status / Banner Model

The editor treats the status/marquee region specially.

### Canonical Data Representation

In the token grid, a status bar is still represented as repeated `ST` cells.

There is no dedicated `colspan` field in the underlying model.

### Preview Representation

In the preview:

- contiguous horizontal runs of `ST` are merged into one `.editor-status-block`
- the merged block renders:
  - left anchor emoji
  - marquee viewport/track
  - right anchor emoji
  - left resize handle
  - right resize handle

### Status Run Helpers

Key functions:

- `statusRuns(layout, cells)`
- `statusRunMap(layout, cells)`
- `statusRunForCell(cellKey, runMap)`
- `applyStatusSpan(originalRun, row, startCol, length)`

### Resize Semantics

Resize works by rewriting repeated `ST` and `EMPTY_TOKEN` cells:

- if the destination span is available, the run expands/contracts
- no separate width metadata is stored

### Move Semantics

Moving a status block:

- drags the entire `ST` run as a unit
- attempts to reapply the run at the drop row/start column
- only succeeds if the entire destination span is empty or part of the original
  run

### Known Fragility

Status interactions are the most complex part of the editor. If a future session
touches them, review these functions first:

- `startStatusResize(...)`
- `startStatusMove(...)`
- `finishStatusInteraction(...)`
- `applyStatusSpan(...)`
- `canOccupyStatusSpan(...)`

## Pointer / Interaction Model

The editor currently has three interaction families:

1. Plain selection
2. Normal-cell drag-to-swap
3. Status-block move / resize

### Selection vs Drag Threshold

To avoid breaking click-to-select:

- `pointerdown` stores a pending pointer intent
- `pointermove` only upgrades that intent into a drag once movement exceeds
  `POINTER_DRAG_THRESHOLD`
- `pointerup` without enough movement becomes a plain selection

This was introduced because starting drag directly on `pointerdown` broke the
inspector selection flow.

### Normal Cell Drag

Normal cells:

- use pending pointer state first
- then promote to active drag
- update target by hit-testing with `document.elementFromPoint(...)`
- swap effective contents on pointer release

Key functions:

- `beginCellDrag(...)`
- `updateCellDragTargetFromPoint(...)`
- `finishCellDrag(...)`

### Undo Behavior

Undo snapshots are stored in `state.undoStack`.

Current rule:

- discrete mutations push a snapshot before mutating
- inspector typing uses a snapshot boundary so a burst of edits in one focus
  session does not create one undo entry per keystroke

Helpers:

- `takeSnapshot()`
- `pushUndoSnapshot()`
- `commitMutation(...)`
- `undoLastMutation()`
- `resetInspectorSnapshotBoundary()`

## Inspector Model

The inspector edits the currently selected cell.

Helper functions:

- `inspectorInputs()`
- `setInspectorDisabled(...)`
- `populateInspector(...)`
- `updateCellFromInputs()`

Token/emoji are intentionally presented as large square inputs rather than a
form with many labels because rapid visual editing matters more than formal
data-entry ergonomics.

## Legend Model

The legend is now cell-oriented, not token-oriented.

Each legend entry shows:

- emoji
- token
- `rNcM` coordinate
- alias

This is important because repeated tokens/emojis need disambiguation by actual
cell position.

Legend behavior:

- lives inside the inspector
- uses internal scrolling
- selection scrolls the relevant entry into view
- clicking a legend item selects that cell

Helper functions:

- `legendEntries()`
- `scrollLegendToSelection()`
- `renderLegend()`

## Rendering Model

Main render flow:

- `render()`
  - `populateVariantSelect()`
  - `updateHeader()`
  - `renderLegend()`
  - `renderGrid()`
  - `renderInspector()`
  - `renderOutputs()`

Notable detail:

- `renderGrid()` computes status runs once via `statusRunMap(...)`
- normal cells and merged status blocks share the same CSS grid surface

## Keyboard Model

Implemented:

- `Delete` / `Backspace` clears selected cell if focus is not inside an input
- `Cmd+Z` or `Ctrl+Z` triggers undo

There is no redo yet.

## CSS / Visual Model

Important CSS assumptions in `layout-editor.css`:

- grid uses equal-size logical slots
- emoji width does not control alignment
- `overscroll-behavior` is used to keep scrolling local
- `touch-action: none` is used on interactive grid elements

This page is allowed to use modern browser features. It does not need to match
the old-iOS compatibility constraints of the main dashboard.

## Known Issues / Tradeoffs

These are the current known compromises, not theoretical ones:

- the editor state is hand-authored and can drift from `config.js`
- token-grid output is readonly; inspector is the only editing path
- no parser exists from token-grid text back into state
- no exporter exists to a final DSL
- variants are stored as full patch-cell objects, not a purpose-built diff DSL
- status-block move/resize behavior depends on destination cells being empty
- status preview marquee text is placeholder text, not live data-driven content
- `GRID_CELL_SIZE` is hardcoded in JS and not derived from CSS
- the page has not been systematically browser-tested inside this session

## How To Continue In A New Session

If continuing work in a fresh context window:

1. Read this file first
2. Open:
   - [index.html](/Users/rtimmons/Projects/smarthome/grid-dashboard/ExpressServer/src/public/edit/index.html)
   - [layout-editor.css](/Users/rtimmons/Projects/smarthome/grid-dashboard/ExpressServer/src/public/css/layout-editor.css)
   - [layout-editor.js](/Users/rtimmons/Projects/smarthome/grid-dashboard/ExpressServer/src/public/js/layout-editor.js)
3. Preserve these invariants unless intentionally changing them:
   - token grid remains canonical
   - variants are patches over base
   - `press` and `activeWhen` stay separate
   - repeated `ST` tokens remain the canonical wide-status representation
4. Be careful around pointer interactions; the selection/drag threshold is easy
   to regress

## Recommended Next Steps

Best next investments:

1. Add import from token-grid text into state
2. Add export to a more structured DSL format
3. Import seeded layouts automatically from `config.js`
4. Derive room deltas automatically instead of hand-seeding them
5. Add redo
6. Add visual affordances for failed status-block move/resize drops
7. Add actual browser/manual testing for `/edit`

## Verification Status

Within this session:

- the editor JS has been syntax-checked repeatedly with `node -e ... new Function(...)`
- the `/edit` page has **not** been exercised end-to-end in a browser from this
  document alone

So the code is syntactically valid, but interaction behavior still depends on
manual browser testing.
