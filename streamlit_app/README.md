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

- Guiar al usuario con un contrato explicito de indicadores principales.
- Permitir pegado manual con Ctrl + V dentro del contrato.
- Validar el contrato con reglas especializadas y errores claros.
- Parsear el texto hacia JSON normalizado para procesamiento posterior.
- Construir el JSON final del snapshot con timestamp de Bogota.
- Enviar el snapshot validado hacia DynamoDB.
- Mantener el codigo, fixtures y QA de Streamlit dentro de `streamlit_app/`.
