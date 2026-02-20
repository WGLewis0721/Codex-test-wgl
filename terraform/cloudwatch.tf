###############################################################################
# cloudwatch.tf – Log groups, metric alarms (CPU, disk), and a dashboard
###############################################################################

###############################################################################
# Log Groups
###############################################################################

resource "aws_cloudwatch_log_group" "itsm_agent" {
  name              = "/itsm-agent"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "/itsm-agent"
  }
}

resource "aws_cloudwatch_log_group" "itsm_agent_app" {
  name              = "/itsm-agent/application"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "/itsm-agent/application"
  }
}

resource "aws_cloudwatch_log_group" "itsm_agent_ollama" {
  name              = "/itsm-agent/ollama"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "/itsm-agent/ollama"
  }
}

###############################################################################
# Local: SNS actions list (empty when no SNS ARN is provided)
###############################################################################

locals {
  alarm_actions = var.alarm_sns_arn != "" ? [var.alarm_sns_arn] : []
}

###############################################################################
# CloudWatch Metric Alarms
###############################################################################

# --------------------------------------------------------------------------
# High CPU utilisation alarm
# Uses the built-in AWS/EC2 CPUUtilization metric (no agent required)
# --------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "${var.project_name}-cpu-high"
  alarm_description   = "EC2 CPU utilisation exceeded ${var.cpu_alarm_threshold}% for 5 consecutive minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 60 # seconds
  statistic           = "Average"
  threshold           = var.cpu_alarm_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    InstanceId = aws_instance.itsm_agent.id
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = {
    Name = "${var.project_name}-cpu-high"
  }
}

# --------------------------------------------------------------------------
# High disk utilisation alarm
# Requires the CloudWatch agent to publish the CWAgent/disk_used_percent metric
# --------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "disk_high" {
  alarm_name          = "${var.project_name}-disk-high"
  alarm_description   = "Root disk utilisation exceeded ${var.disk_alarm_threshold}% for 5 consecutive minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "disk_used_percent"
  namespace           = "CWAgent"
  period              = 60
  statistic           = "Average"
  threshold           = var.disk_alarm_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    InstanceId = aws_instance.itsm_agent.id
    path       = "/"
    fstype     = "xfs"
    device     = "nvme0n1p1"
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = {
    Name = "${var.project_name}-disk-high"
  }
}

# --------------------------------------------------------------------------
# High memory utilisation alarm
# Requires the CloudWatch agent to publish the CWAgent/mem_used_percent metric
# --------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "memory_high" {
  alarm_name          = "${var.project_name}-memory-high"
  alarm_description   = "Memory utilisation exceeded 85% for 5 consecutive minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "mem_used_percent"
  namespace           = "CWAgent"
  period              = 60
  statistic           = "Average"
  threshold           = 85
  treat_missing_data  = "notBreaching"

  dimensions = {
    InstanceId = aws_instance.itsm_agent.id
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = {
    Name = "${var.project_name}-memory-high"
  }
}

# --------------------------------------------------------------------------
# Instance status check alarm – detects hardware/hypervisor failures
# --------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "instance_status" {
  alarm_name          = "${var.project_name}-status-check-failed"
  alarm_description   = "EC2 instance or system status check failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    InstanceId = aws_instance.itsm_agent.id
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = {
    Name = "${var.project_name}-status-check-failed"
  }
}

###############################################################################
# CloudWatch Dashboard
###############################################################################

resource "aws_cloudwatch_dashboard" "itsm_agent" {
  dashboard_name = "${var.project_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      # ------------------------------------------------------------------
      # Title widget
      # ------------------------------------------------------------------
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "## ITSM Agent – Operational Dashboard"
        }
      },

      # ------------------------------------------------------------------
      # CPU Utilisation
      # ------------------------------------------------------------------
      {
        type   = "metric"
        x      = 0
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "CPU Utilisation (%)"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/EC2", "CPUUtilization", "InstanceId", aws_instance.itsm_agent.id,
              { label = "CPU %", stat = "Average", period = 60, color = "#1f77b4" }
            ]
          ]
          yAxis = { left = { min = 0, max = 100 } }
          annotations = {
            horizontal = [{ value = var.cpu_alarm_threshold, label = "Alarm threshold", color = "#d62728" }]
          }
        }
      },

      # ------------------------------------------------------------------
      # Memory Utilisation (requires CWAgent)
      # ------------------------------------------------------------------
      {
        type   = "metric"
        x      = 8
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Memory Utilisation (%)"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["CWAgent", "mem_used_percent", "InstanceId", aws_instance.itsm_agent.id,
              { label = "Memory %", stat = "Average", period = 60, color = "#ff7f0e" }
            ]
          ]
          yAxis = { left = { min = 0, max = 100 } }
          annotations = {
            horizontal = [{ value = 85, label = "Alarm threshold", color = "#d62728" }]
          }
        }
      },

      # ------------------------------------------------------------------
      # Disk Utilisation (requires CWAgent)
      # ------------------------------------------------------------------
      {
        type   = "metric"
        x      = 16
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Disk Utilisation – / (%)"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["CWAgent", "disk_used_percent", "InstanceId", aws_instance.itsm_agent.id,
              "path", "/", "fstype", "xfs", "device", "nvme0n1p1",
              { label = "Disk %", stat = "Average", period = 60, color = "#2ca02c" }
            ]
          ]
          yAxis = { left = { min = 0, max = 100 } }
          annotations = {
            horizontal = [{ value = var.disk_alarm_threshold, label = "Alarm threshold", color = "#d62728" }]
          }
        }
      },

      # ------------------------------------------------------------------
      # Network In/Out
      # ------------------------------------------------------------------
      {
        type   = "metric"
        x      = 0
        y      = 7
        width  = 12
        height = 6
        properties = {
          title  = "Network Traffic (bytes)"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/EC2", "NetworkIn", "InstanceId", aws_instance.itsm_agent.id,
              { label = "Network In", stat = "Sum", period = 60, color = "#1f77b4" }
            ],
            ["AWS/EC2", "NetworkOut", "InstanceId", aws_instance.itsm_agent.id,
              { label = "Network Out", stat = "Sum", period = 60, color = "#ff7f0e" }
            ]
          ]
        }
      },

      # ------------------------------------------------------------------
      # Log insights widget – application errors
      # ------------------------------------------------------------------
      {
        type   = "log"
        x      = 12
        y      = 7
        width  = 12
        height = 6
        properties = {
          title              = "Application Error Log (last 1 hour)"
          view               = "table"
          region             = var.aws_region
          query              = "SOURCE '${aws_cloudwatch_log_group.itsm_agent_app.name}' | fields @timestamp, @message | filter @message like /(?i)(error|exception|critical)/ | sort @timestamp desc | limit 50"
          insightRuleMetrics = []
        }
      },

      # ------------------------------------------------------------------
      # Alarm status widget
      # ------------------------------------------------------------------
      {
        type   = "alarm"
        x      = 0
        y      = 13
        width  = 24
        height = 3
        properties = {
          title = "Active Alarms"
          alarms = [
            aws_cloudwatch_metric_alarm.cpu_high.arn,
            aws_cloudwatch_metric_alarm.disk_high.arn,
            aws_cloudwatch_metric_alarm.memory_high.arn,
            aws_cloudwatch_metric_alarm.instance_status.arn,
          ]
        }
      }
    ]
  })
}
