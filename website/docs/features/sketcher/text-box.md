---
description:
  "Place engraved text, labels, and serial numbers on a sketch with the Rayforge text box tool."
---

# Text Box

The text box tool (`G+T`) places text on the sketch as editable geometry — engraved text, labels,
and serial numbers. Text boxes are fully parametric: the glyphs live inside a constrained frame, so
they re-solve whenever the frame is moved or dimensioned.

![A wordmark and a part label](/screenshots/addons-sketcher-tool-text-box.webp)

## Creating and Editing Text

1. Pick the text box tool from the pie menu, the **Sketch** menu, or press `G+T`.
2. Click where you want the text to start: a text box appears at the click point and the tool
   switches straight into editing.
3. Type the text — the box resizes itself to fit as you type.
4. Press `Enter` or `Escape` to finish editing.

To edit an existing text box, click inside it. Double-click selects a word, triple-click the whole
line, and text can be selected and replaced like in any text editor, including `Ctrl+C`/`Ctrl+V`,
undo/redo, and paste mid-edit.

## Font Properties

![The font properties panel](/screenshots/addons-sketcher-tool-text-box-font-properties.webp)

The **Font Properties** panel in the sidebar controls the appearance of the text box selected in the
canvas:

- **Font family** — choose from the installed system fonts.
- **Custom font** — choose a font you installed yourself (see [Custom Fonts](#custom-fonts)).
- **Font size** — in points.
- **Bold** and **Italic** toggles.

## Text Transforms

The same panel can change how the text is laid out inside its frame:

- **Mirror** — flips the text left to right, for engraving the back of a transparent material.
- **Reverse Characters** — writes the characters in reverse order without flipping them.
- **Vertical** — stacks upright characters from top to bottom.
- **Rotation** — turns the text around the centre of its frame. The frame itself stays horizontal.
- **Upside Down** — a shortcut for a rotation of 180°.

While one of these is active you can still type into the text box, but clicking no longer places the
caret inside the text.

## Knock-out Text

Turn on **Knock-out** to engrave a plate with the text left blank. The plate is the text frame grown
by the **Knock-out Margin** on every side. The outline contains the plate and the letters; the fill
covers the plate except for the letters.

The enclosed parts of letters such as O, A and B are not kept, so knock-out text is meant for
engraving, not for cutting stencils.

## Text on a Path

Text can follow a line, an arc, a circle or a curve:

1. Select the text box together with the shape it should follow.
2. Activate **Follow Path** in the Font Properties panel.

- **Path Side** — **Outside** places the text on the left of the path direction; **Inside** places
  it on the other side and reverses the reading direction, so text on the inside of a circle reads
  upright at the bottom.
- **Path Alignment** — start, centre or end of the path.
- **Path Offset** — shifts the text along the path.
- **Bottom Text** — on a circle, a second line of text that is centred at the bottom on the inside,
  while the main text is centred at the top on the outside. Both read upright, which makes a round
  stamp or seal.

To release the text, select only the text box and activate **Follow Path** again. If the shape is
deleted, the text returns to its frame.

Text on a path keeps its font size, and mirror, vertical, rotation and knock-out do not apply to it.
A path is a single shape; text does not continue from one line or arc onto the next.

## Custom Fonts

Use **Install Font…** to add a `.ttf` or `.otf` file. Installed fonts appear in the **Custom Font**
list on every sketch, and **Remove Custom Font** deletes the selected one.

Fonts are stored on your computer, not inside the project file. When a project uses a font that is
not installed, the panel shows **Font Not Installed** and a substitute font is used until you
install the font or pick another one.

## Presets

A preset stores the font and the text style, but not the text itself or the path it follows. Type a
name into **Save as Preset** to store the settings of the selected text box, pick a name from
**Preset** to apply it, and use **Delete Preset** to remove the selected preset. Applying a preset
is a single undo step.

## Serial Numbers

**Insert Serial Number** adds `{serial()}` to the text. It shows the current value of a counter, and
the counter moves on by one step each time a job is sent to the machine or exported as G-code.
Framing, previews and cancelled or failed jobs do not use up a number.

Counters are shared by all documents and are managed under **Settings → Serial Numbers**, where each
counter has a start value, step, zero padding, prefix and suffix. Use `{serial("name")}` to show a
specific counter.

## A Parametric Frame

A text box is not a raster image: its glyphs are real sketch geometry, laid out inside a frame
defined by an origin and width and height points. The frame is drawn dashed as construction
geometry, so it serves as a layout reference and never ends up in the toolpaths when the sketch is
manufactured. Like everything else in the sketcher the frame is constrained, so it can be
dimensioned like any other geometry — change the width constraint and the text re-solves to fill the
box.

Clicking inside a text box with the [fill tool](fill.md) toggles the fill of the text glyphs instead
of creating a region fill.

## Template Expressions

Text boxes accept **template expressions**: anything in curly braces is evaluated when the sketch
solves, so labels can display live values such as dimensions, dates, or unique serial numbers. See
[Template expressions in text boxes](expressions.md#template-expressions-in-text-boxes) for details
and the built-in functions.
