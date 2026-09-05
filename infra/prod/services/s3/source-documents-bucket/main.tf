module "bucket" {
  source = "../../../../modules/s3/private-bucket"

  name = "${var.project_name}-${var.environment}-source-documents"
  tags = var.tags
}

resource "aws_s3_bucket_notification" "eventbridge" {
  bucket = module.bucket.bucket_id

  eventbridge = true
}
