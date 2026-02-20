###############################################################################
# main.tf – Provider configuration and optional remote state backend
#
# Adjust the backend block to match your organisation's state storage.
# The local backend is used by default; uncomment the S3 backend block and
# populate the bucket/key/region values to store state remotely.
###############################################################################

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # --------------------------------------------------------------------------
  # Remote state backend (recommended for team use).
  # Uncomment and configure before running `terraform init` for the first time.
  # --------------------------------------------------------------------------
  # backend "s3" {
  #   bucket         = "your-tfstate-bucket"
  #   key            = "itsm-agent/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "your-tfstate-lock-table"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

###############################################################################
# Data sources
###############################################################################

# Latest Amazon Linux 2023 AMI (x86_64)
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
}

# Resolve the current AWS account ID and caller identity
data "aws_caller_identity" "current" {}

# Resolve the current AWS region (useful in ARN constructions)
data "aws_region" "current" {}
