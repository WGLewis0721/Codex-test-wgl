###############################################################################
# variables.tf – All input variables with descriptions and sensible defaults
###############################################################################

# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region in which all resources are deployed."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used to prefix all resource names (lower-case, no spaces)."
  type        = string
  default     = "itsm-agent"
}

variable "environment" {
  description = "Deployment environment label (dev | staging | prod)."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "List of CIDR blocks for public subnets (one per AZ)."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "List of CIDR blocks for private subnets (one per AZ)."
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

variable "availability_zones" {
  description = "List of Availability Zones to deploy subnets into. Must match length of subnet CIDR lists."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "admin_cidr" {
  description = "CIDR block allowed to reach the EC2 instance on port 22 (SSH). Restrict to your corporate/VPN egress IP."
  type        = string
  default     = "0.0.0.0/0" # Override in terraform.tfvars for production!

  validation {
    condition     = can(cidrnetmask(var.admin_cidr))
    error_message = "admin_cidr must be a valid CIDR block (e.g. 203.0.113.10/32)."
  }
}

# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

variable "instance_type" {
  description = "EC2 instance type used when GPU is NOT required."
  type        = string
  default     = "t3.large"
}

variable "gpu_instance_type" {
  description = "EC2 instance type used when use_gpu = true (e.g. g4dn.xlarge)."
  type        = string
  default     = "g4dn.xlarge"
}

variable "use_gpu" {
  description = "Set to true to deploy a GPU-enabled instance (uses gpu_instance_type)."
  type        = bool
  default     = false
}

variable "key_name" {
  description = "Name of an existing EC2 Key Pair to enable SSH access."
  type        = string
  # No default – must be supplied in terraform.tfvars or via -var flag.
}

variable "root_volume_size_gb" {
  description = "Size (GiB) of the root EBS volume."
  type        = number
  default     = 50
}

variable "data_volume_size_gb" {
  description = "Size (GiB) of the secondary data EBS volume (model storage, etc.)."
  type        = number
  default     = 100
}

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

variable "ollama_model" {
  description = "Default Ollama model to pull during bootstrap (e.g. llama3, mistral)."
  type        = string
  default     = "llama3.2:3b"
}

variable "openwebui_port" {
  description = "TCP port on which the OpenWebUI service listens."
  type        = number
  default     = 8080
}

variable "fastapi_port" {
  description = "TCP port on which the FastAPI ITSM backend listens."
  type        = number
  default     = 8000
}

# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------

variable "s3_bucket_name" {
  description = "Globally unique name for the documentation S3 bucket. Leave empty to auto-generate from project_name + account ID."
  type        = string
  default     = ""
}

variable "s3_lifecycle_ia_days" {
  description = "Days after which objects transition to STANDARD_IA storage class."
  type        = number
  default     = 90
}

variable "s3_lifecycle_glacier_days" {
  description = "Days after which objects transition to GLACIER storage class."
  type        = number
  default     = 365
}

variable "s3_lifecycle_expiry_days" {
  description = "Days after which non-current object versions are permanently deleted."
  type        = number
  default     = 730
}

# ---------------------------------------------------------------------------
# CloudWatch
# ---------------------------------------------------------------------------

variable "log_retention_days" {
  description = "Number of days to retain logs in the CloudWatch log group."
  type        = number
  default     = 90
}

variable "memory_alarm_threshold" {
  description = "Memory utilization percentage that triggers the high-memory alarm."
  type        = number
  default     = 85
}

variable "cpu_alarm_threshold" {
  description = "CPU utilization percentage that triggers the high-CPU alarm."
  type        = number
  default     = 80
}

variable "disk_alarm_threshold" {
  description = "Disk utilization percentage that triggers the high-disk alarm."
  type        = number
  default     = 85
}

variable "alarm_sns_arn" {
  description = "ARN of an existing SNS topic to receive CloudWatch alarm notifications. Leave empty to skip SNS actions."
  type        = string
  default     = ""
}
