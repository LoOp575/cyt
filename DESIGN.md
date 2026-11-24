# CYT Design Notes

## Overview
CYT is a dense crypto research terminal. The product UI prioritizes traceable market evidence, compact data, and explicit model uncertainty. Neuron is a monitoring and audit workspace, not a trading signal sales page.

## Colors
- Existing application tokens remain canonical: pine/emerald for positive or active states, rose for negative contribution, gold/amber for pending or caution, warm paper for the main canvas, and ink for primary text.
- Neuron's neural topology uses a dedicated dark instrument panel: `#0B1916` background, `#16352C` node fill, `#6EE7B7` core signal, and `#FB7185` negative contribution. These are scoped visualization colors, not global theme replacements.

## Typography
- Display: existing `font-display` stack for section titles.
- Body: existing Inter/system sans stack.
- Data: existing monospace utility stack for prices, timestamps, weights, and probabilities.

## Layout
- Desktop: wide research workspace with a dark topology hero, compact metric row, and tabbed detail panels.
- Mobile: stacked hero and metrics, horizontally scrollable tabs, and horizontally scrollable journal table.
- Data panels preserve existing `.card`, `.micro-label`, `.chip`, and `.btn` primitives.

## Elevation & Depth
- Existing card borders and shadows remain canonical. The neural canvas uses inset contrast instead of a new global shadow system.

## Shapes
- Existing rounded-xl / rounded-2xl vocabulary is retained. Avoid pill-shaped data containers except status chips.

## Components
- Neuron topology: one SVG visualization; node and synapse geometry is stable across states. Connection thickness represents absolute weight; connection color represents the signed contribution.
- Journal: semantic read-only table, horizontally scrollable on narrow viewports.
- Status: text labels accompany all color-coded states.

## Do's and Don'ts
- Do show missing data as missing; do not fill it with fabricated examples.
- Do distinguish a UI clock from a verified scheduler.
- Do not present tanh score mapping as calibrated probability.
- Do not silently replace Champion weights. Candidate promotion requires out-of-sample validation.
