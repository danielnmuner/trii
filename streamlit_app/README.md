# Streamlit App

Primera version de Streamlit para ingestion de texto copiado desde Trii.

## Run locally

```powershell
$env:UV_CACHE_DIR='.uv-cache'
uv run streamlit run streamlit_app/app.py
```

## Run tests

```powershell
$env:UV_CACHE_DIR='.uv-cache'
uv run pytest -q streamlit_app/tests
```

## Responsabilidades

- Guiar al usuario con 4 contratos explicitos.
- Permitir pegado manual con Ctrl + V dentro de cada contrato.
- Validar cada contrato con reglas especializadas y errores claros.
- Parsear el texto hacia JSON normalizado para procesamiento posterior.
- Reconciliar los 4 contratos en un solo JSON final con timestamp de Bogota.
- Simular un envio a DynamoDB a partir del payload consolidado.
- Mantener el cÃ³digo, fixtures y QA de Streamlit dentro de `streamlit_app/`.
