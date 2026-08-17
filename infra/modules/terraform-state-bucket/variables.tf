variable "bucket_name" {
  description = "Name of the Terraform state S3 bucket."
  type        = string
}

variable "common_tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
}
