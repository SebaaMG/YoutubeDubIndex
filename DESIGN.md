---
version: alpha
name: Desktop Dark Catalog
description: Screenshot-derived visual system for the desktop YouTube dub discovery app.
colors:
  primary: "#070B10"
  surface: "#0D1218"
  panel: "#111820"
  panelAlt: "#151B22"
  control: "#10161E"
  border: "#2A3542"
  borderSoft: "#202A35"
  text: "#F4F7FC"
  textMuted: "#A6AFBF"
  textDim: "#8A94A6"
  accent: "#25C8F5"
  accentBlue: "#1F7AF2"
  accentGreen: "#38D88C"
  accentPurple: "#B466FF"
typography:
  body:
    fontFamily: Segoe UI
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.4
  heading:
    fontFamily: Segoe UI
    fontSize: 28px
    fontWeight: 800
    lineHeight: 1.2
  nav:
    fontFamily: Segoe UI
    fontSize: 17px
    fontWeight: 700
    lineHeight: 1.2
  label:
    fontFamily: Segoe UI
    fontSize: 15px
    fontWeight: 700
    lineHeight: 1.25
rounded:
  sm: 6px
  md: 8px
  lg: 10px
spacing:
  xs: 6px
  sm: 10px
  md: 16px
  lg: 24px
  xl: 34px
components:
  app-background:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.text}"
  panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
  button-primary:
    backgroundColor: "{colors.accentBlue}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
  button-topbar:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
  input:
    backgroundColor: "{colors.control}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
---

## Overview

The app uses a dense, native desktop layout on a near-black canvas. The UI should feel like a focused media-indexing tool: compact navigation, sharp card edges, strong cyan accents, and restrained blue primary actions.

## Colors

The darkest "Mis videos" screen defines the base. Use `#070B10` for the app canvas, `#0D1218` for the navigation/status bands, `#111820` for panels, and `#151B22` for repeated video cards. Cyan is reserved for active navigation, badges, status counts, and icon highlights.

## Typography

Use Segoe UI throughout to match the Windows-native screenshots. Headings are bold and compact, form labels are semibold, and muted metadata stays cool gray.

## Layout

Desktop pages use 34px side gutters. The catalog page is intentionally dense with a five-column video grid, a single filter row, and compact cards. Dashboard content is centered, while the source manager uses a two-column form/table layout.

## Shapes

Use 8px to 10px radii for most UI surfaces. Avoid pill-heavy shapes except small language/status chips.

## Components

Primary buttons are saturated blue inside forms and source actions. The topbar CTA uses bright cyan with dark text when the compact "Mis videos" treatment is active. Tables use transparent cells inside a bordered shell.

## Do's and Don'ts

Do preserve the screenshots' dark canvas, cyan active states, compact card grid, and Windows-native typography. Do not introduce warm palettes, marketing hero sections, oversized cards, decorative gradients, or rounded card stacks.
