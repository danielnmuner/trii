variable "name" {
  description = "DynamoDB table name."
  type        = string
}

variable "hash_key" {
  description = "Primary partition key name."
  type        = string
}

variable "range_key" {
  description = "Primary sort key name."
  type        = string
  default     = null
}

variable "attributes" {
  description = "Attribute definitions used by the table and GSIs."
  type = list(object({
    name = string
    type = string
  }))
}

variable "global_secondary_indexes" {
  description = "Global secondary indexes."
  type = list(object({
    name            = string
    hash_key        = string
    range_key       = optional(string)
    projection_type = optional(string, "ALL")
  }))
  default = []
}

variable "billing_mode" {
  description = "DynamoDB billing mode."
  type        = string
  default     = "PAY_PER_REQUEST"
}

variable "point_in_time_recovery_enabled" {
  description = "Enable point in time recovery."
  type        = bool
  default     = true
}

variable "stream_enabled" {
  description = "Enable DynamoDB Streams for the table."
  type        = bool
  default     = false
}

variable "stream_view_type" {
  description = "DynamoDB Streams view type when streams are enabled."
  type        = string
  default     = "NEW_IMAGE"
}

variable "ttl_enabled" {
  description = "Enable DynamoDB TTL for the table."
  type        = bool
  default     = false
}

variable "ttl_attribute_name" {
  description = "Attribute name used by DynamoDB TTL when enabled."
  type        = string
  default     = null
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
