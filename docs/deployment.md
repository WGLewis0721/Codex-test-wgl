# AWS Deployment Guide

This guide walks through deploying the ITSM Tier 1 Agent to AWS using Terraform. The deployment provisions a VPC, EC2 instance, S3 bucket, IAM roles, and CloudWatch monitoring in a single `terraform apply`.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Step 1: Configure terraform.tfvars](#step-1-configure-terraformtfvars)
- [Step 2: Upload Initial Documents to S3](#step-2-upload-initial-documents-to-s3)
- [Step 3: Deploy with Terraform](#step-3-deploy-with-terraform)
- [Step 4: Wait for EC2 Bootstrap](#step-4-wait-for-ec2-bootstrap)
- [Step 5: Access OpenWebUI](#step-5-access-openwebui)
- [Post-Deployment: Trigger Document Ingestion](#post-deployment-trigger-document-ingestion)
- [Updating Models](#updating-models)
- [Teardown](#teardown)

---

## Prerequisites

Ensure the following are installed and configured before proceeding.

### Tools

| Tool | Minimum Version | Install |
|------|----------------|---------|
| [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) | 2.x | `brew install awscli` |
| [Terraform](https://developer.hashicorp.com/terraform/install) | 1.6+ | `brew tap hashicorp/tap && brew install hashicorp/tap/terraform` |
| `ssh` | Any | Pre-installed on macOS/Linux |

### AWS Configuration

```bash
aws configure
# AWS Access Key ID:     <your key>
# AWS Secret Access Key: <your secret>
# Default region name:   us-east-1
# Default output format: json
```

Verify access:

```bash
aws sts get-caller-identity
```

### EC2 Key Pair

You need an existing key pair in the target AWS region. To create one:

```bash
aws ec2 create-key-pair \
  --key-name itsm-agent-key \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/itsm-agent-key.pem

chmod 400 ~/.ssh/itsm-agent-key.pem
```

Note the key name (`itsm-agent-key`) — you will set it in `terraform.tfvars`.

### Required IAM Permissions

The IAM user or role running Terraform needs permissions to create and manage: EC2, VPC, S3, IAM roles/policies, CloudWatch. For a development account, `AdministratorAccess` works. For production, scope permissions to the specific services.

---

## Step 1: Configure terraform.tfvars

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Open `terraform.tfvars` and configure the required values:

```hcl
# ── Required ──────────────────────────────────────────────────────────────────

# Your EC2 key pair name (must exist in the target region)
key_name = "itsm-agent-key"

# Restrict SSH to your IP address only — never use 0.0.0.0/0 in production
admin_cidr = "203.0.113.10/32"   # Replace with your egress IP

# ── Recommended changes ───────────────────────────────────────────────────────

aws_region   = "us-east-1"
project_name = "itsm-agent"
environment  = "dev"

# CPU-only: t3.large (default) — sufficient for llama3.2:3b
# GPU:      set use_gpu = true and gpu_instance_type = "g4dn.xlarge"
instance_type = "t3.large"
use_gpu       = false

# Ollama model to pull during bootstrap
ollama_model = "llama3.2:3b"

# ── Optional ──────────────────────────────────────────────────────────────────

# Leave empty to auto-generate: itsm-agent-docs-<account_id>
s3_bucket_name = ""

# SNS topic ARN for CloudWatch alarm notifications (leave empty to skip)
alarm_sns_arn = ""
```

> **Security note:** `terraform.tfvars` is listed in `.gitignore` and must never be committed to source control — it contains your admin CIDR and key name.

Find your current public IP:

```bash
curl -s https://checkip.amazonaws.com
```

---

## Step 2: Upload Initial Documents to S3

You can upload documents before or after the Terraform deployment. If uploading before, you need to know the bucket name (either the value you set in `s3_bucket_name` or the auto-generated one).

To find the auto-generated bucket name after apply, see [Step 3](#step-3-deploy-with-terraform).

Upload documents to the `knowledge-base/` prefix:

```bash
# Upload individual files
aws s3 cp runbook.pdf       s3://<bucket>/knowledge-base/
aws s3 cp procedures.md     s3://<bucket>/knowledge-base/
aws s3 cp troubleshooting.txt s3://<bucket>/knowledge-base/

# Upload an entire directory
aws s3 sync ./knowledge-base/ s3://<bucket>/knowledge-base/
```

Supported formats: PDF, plain text (`.txt`), Markdown (`.md`).

---

## Step 3: Deploy with Terraform

```bash
cd terraform

# Download required providers (only needed once)
terraform init

# Preview changes before applying
terraform plan

# Apply — this will create ~20 AWS resources
terraform apply
```

Type `yes` when prompted. Terraform will output key values when complete:

```
Outputs:

openwebui_url          = "http://54.123.45.67:8080"
fastapi_url            = "http://54.123.45.67:8000"
s3_bucket_name         = "itsm-agent-docs-123456789012"
ssh_command            = "ssh -i ~/.ssh/itsm-agent-key.pem ec2-user@54.123.45.67"
log_group_name         = "/itsm-agent"
dashboard_url          = "https://us-east-1.console.aws.amazon.com/cloudwatch/..."
```

Save the `openwebui_url` and `fastapi_url` — you will need them in later steps.

---

## Step 4: Wait for EC2 Bootstrap

The EC2 instance runs a bootstrap script (`terraform/scripts/user_data.sh`) on first boot that:

1. Updates system packages
2. Mounts and formats the secondary data EBS volume (`/data`)
3. Installs Docker
4. Installs Ollama and pulls the configured model
5. Starts OpenWebUI in Docker
6. Syncs knowledge-base documents from S3
7. Configures and starts the CloudWatch agent

**Bootstrap typically takes 10–20 minutes** (model download dominates). Monitor progress via CloudWatch Logs:

```bash
# Stream bootstrap log from CloudWatch
aws logs tail /itsm-agent \
  --log-stream-name-prefix "<instance-id>/bootstrap" \
  --follow \
  --region us-east-1
```

Replace `<instance-id>` with the value from `terraform output instance_id`.

Alternatively, SSH into the instance and tail the log directly:

```bash
# From terraform output
ssh -i ~/.ssh/itsm-agent-key.pem ec2-user@<public_ip>

# On the instance
sudo tail -f /var/log/itsm-bootstrap.log
```

The bootstrap is complete when you see:

```
=== ITSM Agent bootstrap completed at <timestamp> ===
```

### Verify Services Are Running

```bash
# Check Ollama
curl http://<public_ip>:11434/api/tags

# Check RAG backend health
curl http://<public_ip>:8000/health | python3 -m json.tool

# Check OpenWebUI is responding
curl -sI http://<public_ip>:8080 | head -5
```

---

## Step 5: Access OpenWebUI

Open `http://<public_ip>:8080` in your browser.

1. **Create an account** — the first account created becomes the administrator
2. **Select a model** — choose the model configured in `ollama_model` (e.g., `llama3.2:3b`)
3. **Start chatting** — the ITSM agent is ready

> **Note:** The RAG backend must be deployed separately to the EC2 instance. The Terraform `user_data.sh` includes a commented-out `docker run` block for the FastAPI backend — uncomment and update it with your container registry image once you have built and pushed the image.

---

## Post-Deployment: Trigger Document Ingestion

After the FastAPI RAG backend is running, trigger document ingestion from S3:

```bash
curl -X POST http://<public_ip>:8000/documents/ingest
```

Response:

```json
{ "message": "Ingestion started in the background." }
```

Monitor ingestion progress in the application logs:

```bash
aws logs tail /itsm-agent --follow
```

Check the number of indexed chunks:

```bash
curl http://<public_ip>:8000/health | python3 -m json.tool
# "chromadb": { "status": "ok", "chunk_count": 284 }
```

List indexed documents:

```bash
curl http://<public_ip>:8000/documents | python3 -m json.tool
```

---

## Updating Models

To pull a different or updated model after deployment, SSH into the instance:

```bash
ssh -i ~/.ssh/itsm-agent-key.pem ec2-user@<public_ip>

# Pull a new model
ollama pull llama3.1:8b

# List available models
ollama list
```

To change the default chat model used by the RAG backend, update the `CHAT_MODEL` environment variable for the backend container and restart it.

---

## Teardown

To destroy all AWS resources created by Terraform:

```bash
cd terraform
terraform destroy
```

> **Warning:** This permanently deletes the S3 bucket contents and all CloudWatch logs. If you want to preserve documents, sync them locally first:
>
> ```bash
> aws s3 sync s3://<bucket>/knowledge-base/ ./knowledge-base-backup/
> ```

Type `yes` when prompted. All resources (EC2, EBS volumes, EIP, VPC, S3 bucket, IAM roles, CloudWatch log groups) will be removed.

### Preserving the Data Volume

The data EBS volume has `delete_on_termination = false` set in Terraform, meaning it survives EC2 termination. However, `terraform destroy` will still delete it because it is a managed resource. To preserve it before destroy:

```bash
# Get the volume ID
terraform output -json | python3 -c "import sys,json; print([v for v in json.load(sys.stdin).values()])"

# In AWS Console or CLI: detach and snapshot the volume before running destroy
aws ec2 create-snapshot \
  --volume-id vol-xxxxxxxxxxxxxxxxx \
  --description "ITSM agent data volume backup"
```
