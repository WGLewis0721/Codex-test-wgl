###############################################################################
# iam.tf – IAM role, instance profile, and least-privilege inline policies
#           granting the EC2 instance access to S3 and CloudWatch Logs
###############################################################################

###############################################################################
# IAM Role – assumed by EC2 via the instance metadata service
###############################################################################

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    sid     = "AllowEC2AssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_role" {
  name               = "${var.project_name}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  description        = "Role assumed by the ITSM agent EC2 instance"

  tags = {
    Name = "${var.project_name}-ec2-role"
  }
}

###############################################################################
# Instance Profile – wraps the role so it can be attached to an EC2 instance
###############################################################################

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name

  tags = {
    Name = "${var.project_name}-ec2-profile"
  }
}

###############################################################################
# Policy – S3 read/write scoped to the documentation bucket only
###############################################################################

data "aws_iam_policy_document" "s3_access" {
  # Allow listing only the specific bucket (not all buckets)
  statement {
    sid    = "AllowBucketList"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [aws_s3_bucket.docs.arn]
  }

  # Allow read/write on objects within the bucket
  statement {
    sid    = "AllowObjectReadWrite"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:GetObjectVersion",
    ]
    resources = ["${aws_s3_bucket.docs.arn}/*"]
  }
}

resource "aws_iam_policy" "s3_access" {
  name        = "${var.project_name}-s3-access"
  description = "Least-privilege S3 access to the ITSM documentation bucket"
  policy      = data.aws_iam_policy_document.s3_access.json

  tags = {
    Name = "${var.project_name}-s3-access"
  }
}

resource "aws_iam_role_policy_attachment" "s3_access" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.s3_access.arn
}

###############################################################################
# Policy – CloudWatch Logs: create log groups/streams and put log events
###############################################################################

data "aws_iam_policy_document" "cloudwatch_logs" {
  statement {
    sid    = "AllowCWLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogGroups",
      "logs:DescribeLogStreams",
    ]
    # Scoped to log groups within the current account and region
    resources = [
      "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/itsm-agent*",
      "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/itsm-agent*:*",
    ]
  }
}

resource "aws_iam_policy" "cloudwatch_logs" {
  name        = "${var.project_name}-cloudwatch-logs"
  description = "Allow the EC2 instance to write logs to CloudWatch"
  policy      = data.aws_iam_policy_document.cloudwatch_logs.json

  tags = {
    Name = "${var.project_name}-cloudwatch-logs"
  }
}

resource "aws_iam_role_policy_attachment" "cloudwatch_logs" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.cloudwatch_logs.arn
}

###############################################################################
# Policy – CloudWatch Metrics: allow the CloudWatch agent to publish custom metrics
###############################################################################

data "aws_iam_policy_document" "cloudwatch_metrics" {
  statement {
    sid    = "AllowCWMetrics"
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricData",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:ListMetrics",
    ]
    resources = ["*"] # CloudWatch PutMetricData does not support resource-level restrictions
  }

  # Allow the CloudWatch agent to read instance metadata for dimension population
  statement {
    sid    = "AllowEC2Describe"
    effect = "Allow"
    actions = [
      "ec2:DescribeVolumes",
      "ec2:DescribeTags",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "cloudwatch_metrics" {
  name        = "${var.project_name}-cloudwatch-metrics"
  description = "Allow the EC2 instance to publish custom CloudWatch metrics"
  policy      = data.aws_iam_policy_document.cloudwatch_metrics.json

  tags = {
    Name = "${var.project_name}-cloudwatch-metrics"
  }
}

resource "aws_iam_role_policy_attachment" "cloudwatch_metrics" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.cloudwatch_metrics.arn
}

###############################################################################
# Attach AWS-managed SSM policy – enables Session Manager access
# (optional but recommended as an SSH alternative with full audit trail)
###############################################################################

resource "aws_iam_role_policy_attachment" "ssm_managed" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
