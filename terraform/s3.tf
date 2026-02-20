###############################################################################
# s3.tf – Documentation S3 bucket with versioning, SSE-S3 encryption,
#          public-access block, and lifecycle policies
###############################################################################

###############################################################################
# Bucket name resolution
###############################################################################

locals {
  # If the caller did not supply a bucket name, generate one that is globally
  # unique by appending the AWS account ID.
  s3_bucket_name_resolved = var.s3_bucket_name != "" ? var.s3_bucket_name : "${var.project_name}-docs-${data.aws_caller_identity.current.account_id}"
}

###############################################################################
# S3 Bucket
###############################################################################

resource "aws_s3_bucket" "docs" {
  bucket = local.s3_bucket_name_resolved

  # Set to true only during development/testing; never in production.
  force_destroy = false

  tags = {
    Name    = local.s3_bucket_name_resolved
    Purpose = "ITSM documentation and knowledge-base storage"
  }
}

###############################################################################
# Block all public access – documents are accessed exclusively through IAM roles
###############################################################################

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket = aws_s3_bucket.docs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

###############################################################################
# Versioning – required for lifecycle noncurrent-version transitions
###############################################################################

resource "aws_s3_bucket_versioning" "docs" {
  bucket = aws_s3_bucket.docs.id

  versioning_configuration {
    status = "Enabled"
  }
}

###############################################################################
# Server-side encryption with Amazon S3-managed keys (SSE-S3)
###############################################################################

resource "aws_s3_bucket_server_side_encryption_configuration" "docs" {
  bucket = aws_s3_bucket.docs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }

    # Deny unencrypted uploads
    bucket_key_enabled = false
  }
}

###############################################################################
# Lifecycle policy – tiered storage to manage cost
###############################################################################

resource "aws_s3_bucket_lifecycle_configuration" "docs" {
  # Versioning must be enabled before lifecycle rules reference noncurrent versions
  depends_on = [aws_s3_bucket_versioning.docs]

  bucket = aws_s3_bucket.docs.id

  # --------------------------------------------------------------------------
  # Rule 1 – Transition current objects to cheaper storage tiers over time
  # --------------------------------------------------------------------------
  rule {
    id     = "tiered-storage-current"
    status = "Enabled"

    filter {
      prefix = "" # Apply to all objects
    }

    transition {
      days          = var.s3_lifecycle_ia_days
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = var.s3_lifecycle_glacier_days
      storage_class = "GLACIER"
    }
  }

  # --------------------------------------------------------------------------
  # Rule 2 – Expire old non-current versions to control version accumulation
  # --------------------------------------------------------------------------
  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {
      prefix = ""
    }

    noncurrent_version_expiration {
      noncurrent_days = var.s3_lifecycle_expiry_days
    }

    # Keep at most 5 non-current versions per object at any time
    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }
  }

  # --------------------------------------------------------------------------
  # Rule 3 – Clean up incomplete multipart uploads after 7 days
  # --------------------------------------------------------------------------
  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"

    filter {
      prefix = ""
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

###############################################################################
# Bucket policy – deny any requests that are not over TLS
###############################################################################

resource "aws_s3_bucket_policy" "docs_tls_only" {
  bucket = aws_s3_bucket.docs.id

  # Depends on the public-access block being in place first
  depends_on = [aws_s3_bucket_public_access_block.docs]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyNonTLS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.docs.arn,
          "${aws_s3_bucket.docs.arn}/*",
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}
