output "name" {
  description = "DynamoDB table name."
  value       = aws_dynamodb_table.this.name
}

output "arn" {
  description = "DynamoDB table ARN."
  value       = aws_dynamodb_table.this.arn
}

output "id" {
  description = "DynamoDB table ID."
  value       = aws_dynamodb_table.this.id
}

output "index_arns" {
  description = "DynamoDB GSI ARNs."
  value = [
    for gsi in var.global_secondary_indexes :
    "${aws_dynamodb_table.this.arn}/index/${gsi.name}"
  ]
}

output "stream_arn" {
  description = "DynamoDB Streams ARN when streams are enabled."
  value       = aws_dynamodb_table.this.stream_arn
}
