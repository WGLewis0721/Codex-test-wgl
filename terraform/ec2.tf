###############################################################################
# ec2.tf – EC2 instance, Elastic IP, key pair reference, and EBS volumes
#
# The instance type is selected automatically based on the `use_gpu` variable:
#   use_gpu = false  →  var.instance_type      (default: t3.large)
#   use_gpu = true   →  var.gpu_instance_type  (default: g4dn.xlarge)
###############################################################################

###############################################################################
# Key Pair – reference an existing key; Terraform will not create or delete it
###############################################################################

data "aws_key_pair" "deployer" {
  key_name = var.key_name
}

###############################################################################
# Local values
###############################################################################

locals {
  # Select instance type based on GPU flag
  effective_instance_type = var.use_gpu ? var.gpu_instance_type : var.instance_type

  # Resolve effective S3 bucket name (may be auto-generated in s3.tf)
  effective_s3_bucket_name = var.s3_bucket_name != "" ? var.s3_bucket_name : "${var.project_name}-docs-${data.aws_caller_identity.current.account_id}"
}

###############################################################################
# EC2 Instance
###############################################################################

resource "aws_instance" "itsm_agent" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = local.effective_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.itsm_agent.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  key_name               = data.aws_key_pair.deployer.key_name

  # Bootstrap the instance; variables are interpolated into the script at deploy time
  user_data = templatefile("${path.module}/scripts/user_data.sh", {
    s3_bucket_name = local.effective_s3_bucket_name
    ollama_model   = var.ollama_model
    aws_region     = var.aws_region
    log_group_name = "/itsm-agent"
  })

  # Ensure CloudWatch agent can write before the instance bootstraps
  depends_on = [aws_cloudwatch_log_group.itsm_agent]

  # Root volume
  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size_gb
    encrypted             = true
    delete_on_termination = true

    tags = {
      Name = "${var.project_name}-root-volume"
    }
  }

  # Secondary data volume for model weights and application data
  ebs_block_device {
    device_name           = "/dev/sdf"
    volume_type           = "gp3"
    volume_size           = var.data_volume_size_gb
    encrypted             = true
    delete_on_termination = false # Preserve data on instance replacement

    tags = {
      Name = "${var.project_name}-data-volume"
    }
  }

  # Enable detailed monitoring for 1-minute CloudWatch metrics
  monitoring = true

  metadata_options {
    # Require IMDSv2 to mitigate SSRF-based metadata attacks
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tags = {
    Name        = "${var.project_name}-instance"
    InstanceUse = var.use_gpu ? "GPU" : "CPU"
  }
}

###############################################################################
# Elastic IP – stable public IP that survives instance stop/start
###############################################################################

resource "aws_eip" "itsm_agent" {
  instance = aws_instance.itsm_agent.id
  domain   = "vpc"

  # Ensure the IGW exists before allocating the EIP
  depends_on = [aws_internet_gateway.main]

  tags = {
    Name = "${var.project_name}-eip"
  }
}
