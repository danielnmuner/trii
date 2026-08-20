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

variable "snapshot_ingestion_raw_table_name" {
  description = "Snapshot ingestion raw table name."
  type        = string
}

variable "snapshot_ingestion_raw_table_arn" {
  description = "Snapshot ingestion raw table ARN."
  type        = string
}

variable "snapshot_ingestion_checksums_table_name" {
  description = "Snapshot ingestion checksums table name."
  type        = string
}

variable "snapshot_ingestion_checksums_table_arn" {
  description = "Snapshot ingestion checksums table ARN."
  type        = string
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
