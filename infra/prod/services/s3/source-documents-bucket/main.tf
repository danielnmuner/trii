module "bucket" {
  source = "../../../../modules/s3/private-bucket"

  name = "${var.project_name}-${var.environment}-source-documents"
  tags = var.tags
}
