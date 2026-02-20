###############################################################################
# outputs.tf – Key values surfaced after `terraform apply`
###############################################################################

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------

output "vpc_id" {
  description = "ID of the deployed VPC."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets."
  value       = aws_subnet.private[*].id
}

output "security_group_id" {
  description = "ID of the ITSM agent security group."
  value       = aws_security_group.itsm_agent.id
}

# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

output "instance_id" {
  description = "EC2 instance ID of the ITSM agent."
  value       = aws_instance.itsm_agent.id
}

output "instance_type_used" {
  description = "Effective EC2 instance type (reflects use_gpu setting)."
  value       = aws_instance.itsm_agent.instance_type
}

output "ami_id" {
  description = "AMI ID used to launch the instance."
  value       = data.aws_ami.amazon_linux_2023.id
}

output "public_ip" {
  description = "Elastic IP address (public) assigned to the ITSM agent instance."
  value       = aws_eip.itsm_agent.public_ip
}

output "private_ip" {
  description = "Private IP address of the ITSM agent instance."
  value       = aws_instance.itsm_agent.private_ip
}

output "openwebui_url" {
  description = "URL to access the OpenWebUI interface."
  value       = "http://${aws_eip.itsm_agent.public_ip}:${var.openwebui_port}"
}

output "fastapi_url" {
  description = "URL to access the FastAPI ITSM backend."
  value       = "http://${aws_eip.itsm_agent.public_ip}:${var.fastapi_port}"
}

output "ssh_command" {
  description = "Example SSH command to connect to the instance."
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_eip.itsm_agent.public_ip}"
}

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

output "s3_bucket_name" {
  description = "Name of the ITSM documentation S3 bucket."
  value       = aws_s3_bucket.docs.id
}

output "s3_bucket_arn" {
  description = "ARN of the ITSM documentation S3 bucket."
  value       = aws_s3_bucket.docs.arn
}

output "s3_bucket_region" {
  description = "AWS region where the S3 bucket resides."
  value       = aws_s3_bucket.docs.region
}

# ---------------------------------------------------------------------------
# IAM
# ---------------------------------------------------------------------------

output "iam_role_arn" {
  description = "ARN of the IAM role attached to the EC2 instance."
  value       = aws_iam_role.ec2_role.arn
}

output "iam_instance_profile_name" {
  description = "Name of the IAM instance profile."
  value       = aws_iam_instance_profile.ec2_profile.name
}

# ---------------------------------------------------------------------------
# CloudWatch
# ---------------------------------------------------------------------------

output "log_group_name" {
  description = "Name of the primary CloudWatch log group."
  value       = aws_cloudwatch_log_group.itsm_agent.name
}

output "dashboard_url" {
  description = "Direct URL to the CloudWatch operational dashboard."
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.itsm_agent.dashboard_name}"
}
