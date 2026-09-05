variable "project_name" {
  description = "Project name prefix."
  type        = string
}

variable "environment" {
  description = "Environment name."
  type        = string
}

variable "source_documents_bucket_name" {
  description = "Source documents bucket name."
  type        = string
}

variable "source_documents_bucket_arn" {
  description = "Source documents bucket ARN."
  type        = string
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

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
