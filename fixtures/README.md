# Trii Fixtures

This directory contains normalized JSON fixtures for clipboard-style text copied from the Trii web UI.

These fixtures are **processing-first contracts**. They are not intended for rendering, API responses, or UI reuse.

## Goals

- Define the exact Python-ready shape expected from the parser.
- Keep only fields that support calculations, screening, or decision logic.
- Remove UI-only metadata such as navigation links or presentational labels.

## Directory layout

```text
fixtures/
  trii/
    stocks/
      <symbol_lower>/
        <section_name>/
          <symbol_lower>-<asset_name_snake_case>.json
```

## File naming

- Filename format: `<symbol_lower>-<asset_name_snake_case>.json`
- Example: `pfaval-aval_preferencial.json`

## Contract conventions

- All keys use English `snake_case`.
- Contracts should be as flat as possible without losing meaning.
- Currency values are normalized as numeric `float` values in COP.
- Integer quantities remain integers.
- Dates use ISO `YYYY-MM-DD` when available.
- URLs, tabs, UI labels, and other non-operational metadata should be excluded unless they drive logic.

## Current sections

- `stock_snapshot`
- `technical_oscillators`
- `technical_moving_averages`
- `support_and_resistance`
