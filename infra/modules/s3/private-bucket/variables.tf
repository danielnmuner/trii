variable "name" {
  description = "S3 bucket name."
  type        = string
}

variable "versioning_enabled" {
  description = "Enable bucket versioning."
  type        = bool
  default     = true
}

variable "force_destroy" {
  description = "Allow bucket objects to be destroyed with Terraform."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
