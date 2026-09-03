variable "project_name" {
  description = "Project name prefix."
  type        = string
}

variable "environment" {
  description = "Environment name."
  type        = string
}

variable "current_snapshots_table_name" {
  description = "Current snapshots table name."
  type        = string
}

variable "current_snapshots_table_arn" {
  description = "Current snapshots table ARN."
  type        = string
}

variable "current_snapshots_index_arns" {
  description = "Current snapshots table index ARNs."
  type        = list(string)
}

variable "snapshot_ingestion_checksums_table_name" {
  description = "Snapshot ingestion checksums table name."
  type        = string
}

variable "snapshot_ingestion_checksums_table_arn" {
  description = "Snapshot ingestion checksums table ARN."
  type        = string
}

variable "snapshot_ingestion_checksums_index_arns" {
  description = "Snapshot ingestion checksums table index ARNs."
  type        = list(string)
}

variable "stock_orders_table_name" {
  description = "Stock orders table name."
  type        = string
}

variable "stock_orders_table_arn" {
  description = "Stock orders table ARN."
  type        = string
}

variable "stock_orders_index_arns" {
  description = "Stock orders table index ARNs."
  type        = list(string)
}

variable "parsed_invoices_table_name" {
  description = "Parsed invoices table name."
  type        = string
}

variable "parsed_invoices_table_arn" {
  description = "Parsed invoices table ARN."
  type        = string
}

variable "parsed_invoices_index_arns" {
  description = "Parsed invoices table index ARNs."
  type        = list(string)
}

variable "historic_stats_table_name" {
  description = "Historic stats table name."
  type        = string
}

variable "historic_stats_table_arn" {
  description = "Historic stats table ARN."
  type        = string
}

variable "historic_stats_index_arns" {
  description = "Historic stats table index ARNs."
  type        = list(string)
}

variable "processed_stats_events_table_name" {
  description = "Processed stats events table name."
  type        = string
}

variable "processed_stats_events_table_arn" {
  description = "Processed stats events table ARN."
  type        = string
}

variable "processed_stats_events_index_arns" {
  description = "Processed stats events table index ARNs."
  type        = list(string)
}

variable "daily_closing_snapshots_table_name" {
  description = "Daily closing snapshots table name."
  type        = string
}

variable "daily_closing_snapshots_table_arn" {
  description = "Daily closing snapshots table ARN."
  type        = string
}

variable "daily_closing_snapshots_index_arns" {
  description = "Daily closing snapshots table index ARNs."
  type        = list(string)
}

variable "session_vectors_table_name" {
  description = "Session vectors table name."
  type        = string
}

variable "session_vectors_table_arn" {
  description = "Session vectors table ARN."
  type        = string
}

variable "session_vectors_index_arns" {
  description = "Session vectors table index ARNs."
  type        = list(string)
}

variable "analytics_catalog_table_name" {
  description = "Analytics catalog table name."
  type        = string
}

variable "analytics_catalog_table_arn" {
  description = "Analytics catalog table ARN."
  type        = string
}

variable "analytics_catalog_table_index_arns" {
  description = "Analytics catalog table index ARNs."
  type        = list(string)
}

variable "source_documents_bucket_name" {
  description = "Source documents bucket name."
  type        = string
}

variable "source_documents_bucket_arn" {
  description = "Source documents bucket ARN."
  type        = string
}

variable "api_gateway_shared_token" {
  description = "Shared token required by API Gateway clients."
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
