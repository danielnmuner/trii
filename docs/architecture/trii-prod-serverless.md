# Trii prod serverless

## Goal

This architecture keeps a single simple synchronous flow with clear separation of responsibilities:

- the user sends a prompt with instructions,
- `api_handler` receives the request and persists operational data,
- `ai_handler` reads context only when the prompt needs it,
- `ai_handler` invokes Bedrock,
- the answer returns to the user in the same request.

## Runtime shape

This version removes SQS because the expected traffic is extremely low and the request can be handled synchronously.

The architecture now uses:

- `API Gateway`
- one Lambda for synchronous API handling: `api_handler`
- one Lambda for AI orchestration: `ai_handler`
- `Bedrock Nova Pro`
- DynamoDB tables for business persistence and optional AI context
- S3 for source documents and optional AI context

## Data sources

### DynamoDB tables

- `trii-prod-current-snapshots`
- `trii-prod-stock-orders`
- `trii-prod-parsed-invoices`

### S3 bucket

- `trii-prod-source-documents`

## Proposed flow

1. Streamlit sends a prompt and instructions to `API Gateway`.
2. `API Gateway` invokes `api_handler`.
3. `api_handler` persists business data when the request is about snapshots, orders, invoices, or source documents.
4. When the request is an AI prompt, `api_handler` invokes `ai_handler`.
5. `ai_handler` decides whether the prompt requires additional context.
6. If needed, `ai_handler` reads from one or more DynamoDB tables.
7. If needed, `ai_handler` can also read document metadata or related references from S3.
8. `ai_handler` invokes `Bedrock Nova Pro`.
9. `ai_handler` returns the final answer to `api_handler`.
10. `api_handler` returns the response to the user through `API Gateway`.

## Important decision

This architecture is intentionally synchronous.

Because the expected concurrency is usually `1` and at most around `2`, adding SQS would add operational complexity without a clear payoff right now.

Keeping `ai_handler` separate from `api_handler` still makes sense because it preserves a cleaner boundary:

- `api_handler` owns transport and persistence.
- `ai_handler` owns prompt orchestration, optional context lookup, and Bedrock integration.

## Naming conventions

- Project: `trii`
- Environment: `prod`
- Resource prefix: `trii-prod-<service>`

Examples:

- `trii-prod-http-api`
- `trii-prod-api-handler`
- `trii-prod-ai-handler`
- `trii-prod-current-snapshots`
- `trii-prod-stock-orders`
- `trii-prod-parsed-invoices`
- `trii-prod-source-documents`

## Recommended Terraform layout

```text
infra/
  modules/
    apigateway/
      http-api/
    lambda/
      python-function/
    dynamodb/
      current-snapshots-table/
      stock-orders-table/
      parsed-invoices-table/
    s3/
      source-documents-bucket/
  prod/
    services/
      apigateway/
        http-api/
      lambda/
        api-handler/
        ai-handler/
      dynamodb/
        current-snapshots-table/
        stock-orders-table/
        parsed-invoices-table/
      s3/
        source-documents-bucket/
      bedrock/
        nova-pro/
```

## Artifacts

- Source script: `generated-diagrams/trii-prod/serverless-runtime.py`
- Rendered diagram: `generated-diagrams/trii-prod/serverless-runtime.png`
