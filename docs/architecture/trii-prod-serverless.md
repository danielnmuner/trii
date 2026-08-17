# Trii prod serverless

## Goal

This architecture separates synchronous API handling, persistent business data, source document storage, and asynchronous AI processing with the fewest moving parts that still keep the design reliable.

## Data model

The current target model uses three DynamoDB tables and one S3 bucket for source documents only.

### DynamoDB tables

- `trii-prod-current-snapshots`: latest parsed and enriched market snapshot records.
- `trii-prod-stock-orders`: normalized order records derived from sources such as `orders-trii.csv`.
- `trii-prod-parsed-invoices`: normalized invoice records derived from XML invoices such as `nuco-factura.xml`.

### S3 bucket

- `trii-prod-source-documents`: original source files only, such as brokerage statements, invoice PDFs, invoice XML files, and similar documents.

Important: processed JSON should not be stored in S3. The important business data lives in DynamoDB.

## Lambda strategy

Given the expected load of roughly 100 API requests per day, the architecture can be reduced safely to two Lambdas:

- `api_handler`: one synchronous Lambda behind API Gateway for all HTTP routes.
- `process_ai_job`: one asynchronous Lambda that consumes SQS and invokes Bedrock Nova Pro.

This keeps the system simple without mixing synchronous HTTP handling with asynchronous queue processing.

## Proposed flow

1. Streamlit sends requests to `API Gateway`.
2. `api_handler` routes by path and method.
3. For snapshots, `api_handler` validates the payload, writes the current snapshot to DynamoDB, and enqueues an AI job in SQS.
4. For orders, `api_handler` writes normalized order records to the orders table.
5. For invoices, `api_handler` stores the original documents in S3 and writes the parsed invoice record to the invoices table.
6. For snapshot reads, `api_handler` returns the latest snapshot state from DynamoDB.
7. `process_ai_job` consumes the queue, reads the snapshot from DynamoDB, invokes `Bedrock Nova Pro`, and updates the snapshot record in DynamoDB.

## Important decision

Even with low traffic, the asynchronous Lambda that consumes SQS should not reply to the original HTTP request. The reliable pattern here is:

- return quickly with a `snapshot_id` and an initial status;
- process AI work in the background;
- query the latest state through a read endpoint.

If real-time updates are needed later, the natural evolution would be WebSocket API, SSE, or a separate notification channel.

## Naming conventions

- Project: `trii`
- Environment: `prod`
- Resource prefix: `trii-prod-<service>`

Examples:

- `trii-prod-http-api`
- `trii-prod-api-handler`
- `trii-prod-process-ai-job`
- `trii-prod-current-snapshots`
- `trii-prod-stock-orders`
- `trii-prod-parsed-invoices`
- `trii-prod-source-documents`
- `trii-prod-ai-jobs`

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
    sqs/
      standard-queue/
  prod/
    services/
      apigateway/
        http-api/
      lambda/
        api-handler/
        process-ai-job/
      dynamodb/
        current-snapshots-table/
        stock-orders-table/
        parsed-invoices-table/
      s3/
        source-documents-bucket/
      sqs/
        ai-jobs-queue/
      bedrock/
        nova-pro/
```

## Artifacts

- Source script: `generated-diagrams/trii-prod/serverless-runtime.py`
- Rendered diagram: `generated-diagrams/trii-prod/serverless-runtime.png`
