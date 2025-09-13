# bootstrap/main.tf
# Purpose: Create the S3 bucket and DynamoDB table used by Terraform remote state/locking.
# This stack uses a *local* backend (intentionally), so it can bootstrap the remote backend.

terraform {
  required_version = ">= 1.0"
  backend "local" {}
}

provider "aws" {
  region = "il-central-1"
}

# >>> CHANGE THESE TWO NAMES (bucket must be globally unique) <<<
locals {
  bucket_name = "max-tfstate-bucket"  # e.g. "yuval-dadjokes-tfstate-ilc"
  table_name  = "tf-locks"            # e.g. "dadjokes-tf-locks"
}

# S3 bucket for Terraform state (versioned + SSE + public access blocked)
resource "aws_s3_bucket" "tf_state" {
  bucket        = local.bucket_name
  force_destroy = false
  tags = {
    Project = "dadjokes"
    Purpose = "terraform-state"
  }
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket                  = aws_s3_bucket.tf_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Optional: expire old non-current object versions after 30 days
resource "aws_s3_bucket_lifecycle_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}

# DynamoDB table for Terraform state locking
resource "aws_dynamodb_table" "tf_locks" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  attribute {
    name = "LockID"
    type = "S"
  }
  tags = {
    Project = "dadjokes"
    Purpose = "terraform-lock"
  }
}

output "state_bucket" { value = aws_s3_bucket.tf_state.bucket }
output "lock_table"   { value = aws_dynamodb_table.tf_locks.name }
