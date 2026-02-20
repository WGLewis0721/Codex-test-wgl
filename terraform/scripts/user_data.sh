#!/usr/bin/env bash
###############################################################################
# user_data.sh – EC2 bootstrap script for the ITSM Tier 1 agent
#
# Variables injected by Terraform templatefile():
#   s3_bucket_name  – S3 bucket used for documentation storage
#   ollama_model    – Default Ollama model to pull (e.g. llama3)
#   aws_region      – AWS region (used for CloudWatch agent config)
#   log_group_name  – CloudWatch log group name
###############################################################################

set -euo pipefail

LOG_FILE="/var/log/itsm-bootstrap.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== ITSM Agent bootstrap started at $(date -u) ==="
echo "  S3 bucket  : ${s3_bucket_name}"
echo "  Ollama model: ${ollama_model}"
echo "  AWS region : ${aws_region}"
echo "  Log group  : ${log_group_name}"

###############################################################################
# 1. System updates and base packages
###############################################################################

dnf update -y
dnf install -y \
  git \
  curl \
  wget \
  unzip \
  python3 \
  python3-pip \
  docker \
  amazon-cloudwatch-agent

###############################################################################
# 2. Mount and format the secondary data volume (/dev/sdf → /data)
###############################################################################

DATA_DEVICE="/dev/sdf"
MOUNT_POINT="/data"

# Wait for the device to be available (up to 60 s)
for i in $(seq 1 12); do
  if [ -b "$DATA_DEVICE" ]; then break; fi
  echo "Waiting for $DATA_DEVICE... ($i/12)"
  sleep 5
done

if [ -b "$DATA_DEVICE" ]; then
  # Only format if the device has no filesystem
  if ! blkid "$DATA_DEVICE"; then
    mkfs.xfs "$DATA_DEVICE"
  fi
  mkdir -p "$MOUNT_POINT"
  # Add to fstab for persistence across reboots
  DEVICE_UUID=$(blkid -s UUID -o value "$DATA_DEVICE")
  echo "UUID=$DEVICE_UUID $MOUNT_POINT xfs defaults,nofail 0 2" >> /etc/fstab
  mount -a
  echo "Data volume mounted at $MOUNT_POINT"
else
  echo "WARNING: Data device $DATA_DEVICE not found, skipping mount"
fi

###############################################################################
# 3. Docker setup
###############################################################################

systemctl enable --now docker
usermod -aG docker ec2-user

###############################################################################
# 4. Ollama installation
###############################################################################

OLLAMA_DATA_DIR="$MOUNT_POINT/ollama"
mkdir -p "$OLLAMA_DATA_DIR"

# Install Ollama using the official installer
curl -fsSL https://ollama.com/install.sh | sh

# Configure Ollama to store models on the data volume
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf <<EOF
[Service]
Environment="OLLAMA_MODELS=$OLLAMA_DATA_DIR"
EOF

systemctl daemon-reload
systemctl enable --now ollama

# Wait for Ollama to be ready before pulling the model
echo "Waiting for Ollama service..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama is ready."
    break
  fi
  sleep 5
done

# Pull the configured model
ollama pull "${ollama_model}" && echo "Model ${ollama_model} pulled successfully."

###############################################################################
# 5. OpenWebUI (Docker container)
###############################################################################

OPENWEBUI_DATA="$MOUNT_POINT/openwebui"
mkdir -p "$OPENWEBUI_DATA"

docker run -d \
  --name open-webui \
  --restart always \
  -p 8080:8080 \
  -v "$OPENWEBUI_DATA:/app/backend/data" \
  -e OLLAMA_BASE_URL=http://host-gateway:11434 \
  --add-host=host-gateway:host-gateway \
  ghcr.io/open-webui/open-webui:main

###############################################################################
# 6. FastAPI ITSM backend (placeholder – replace with real application image)
###############################################################################

APP_DATA="$MOUNT_POINT/app"
mkdir -p "$APP_DATA"

# Pull documentation index from S3 on startup
aws s3 sync "s3://${s3_bucket_name}/knowledge-base/" "$APP_DATA/knowledge-base/" \
  --region "${aws_region}" || echo "WARNING: S3 sync failed (bucket may be empty)"

# TODO: Replace the placeholder image with your actual ITSM FastAPI application
# docker run -d \
#   --name itsm-backend \
#   --restart always \
#   -p 8000:8000 \
#   -v "$APP_DATA:/app/data" \
#   -e S3_BUCKET="${s3_bucket_name}" \
#   -e AWS_DEFAULT_REGION="${aws_region}" \
#   your-ecr-registry/itsm-backend:latest

###############################################################################
# 7. CloudWatch agent configuration
###############################################################################

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<CWCONFIG
{
  "agent": {
    "metrics_collection_interval": 60,
    "logfile": "/var/log/amazon-cloudwatch-agent.log"
  },
  "metrics": {
    "append_dimensions": {
      "InstanceId": "$${aws:InstanceId}"
    },
    "metrics_collected": {
      "mem": {
        "measurement": ["mem_used_percent"],
        "metrics_collection_interval": 60
      },
      "disk": {
        "measurement": ["disk_used_percent"],
        "metrics_collection_interval": 60,
        "resources": ["/"]
      },
      "cpu": {
        "measurement": ["cpu_usage_active"],
        "metrics_collection_interval": 60,
        "totalcpu": true
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/itsm-bootstrap.log",
            "log_group_name": "${log_group_name}",
            "log_stream_name": "{instance_id}/bootstrap",
            "retention_in_days": 90
          },
          {
            "file_path": "/var/log/messages",
            "log_group_name": "${log_group_name}",
            "log_stream_name": "{instance_id}/system",
            "retention_in_days": 90
          }
        ]
      }
    },
    "log_stream_name": "{instance_id}/default"
  }
}
CWCONFIG

/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
  -s

systemctl enable amazon-cloudwatch-agent

###############################################################################
# 8. Done
###############################################################################

echo "=== ITSM Agent bootstrap completed at $(date -u) ==="
