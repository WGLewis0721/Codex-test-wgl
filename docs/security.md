# Security Guide

This document describes the security architecture of the ITSM Tier 1 Agent and best practices for secure deployment and operation.

---

## Table of Contents

- [IAM Least Privilege](#iam-least-privilege)
- [Security Group Configuration](#security-group-configuration)
- [VPC Isolation](#vpc-isolation)
- [Encryption at Rest and in Transit](#encryption-at-rest-and-in-transit)
- [Secrets Management](#secrets-management)
- [Audit Logging with CloudWatch](#audit-logging-with-cloudwatch)
- [EC2 Instance Hardening](#ec2-instance-hardening)
- [Compliance Notes](#compliance-notes)

---

## IAM Least Privilege

The EC2 instance uses an IAM instance role — no long-lived AWS credentials are stored on the instance. The role is granted only the minimum permissions required for the application to function.

### Permissions Granted and Rationale

#### S3 Access (scoped to the single documentation bucket)

| Permission | Resource | Reason |
|-----------|----------|--------|
| `s3:ListBucket` | `arn:aws:s3:::itsm-agent-docs-<account>` | Enumerate documents for ingestion |
| `s3:GetBucketLocation` | Bucket ARN | Required by AWS SDK for path-style requests |
| `s3:GetObject` | `arn:aws:s3:::itsm-agent-docs-<account>/*` | Download documents for ingestion |
| `s3:PutObject` | Bucket objects | Allow uploading processed artifacts (future use) |
| `s3:DeleteObject` | Bucket objects | Allow removing documents via API |
| `s3:GetObjectVersion` | Bucket objects | Retrieve specific document versions |

> **Not granted:** `s3:ListAllMyBuckets`, `s3:CreateBucket`, `s3:DeleteBucket`, or access to any other bucket.

#### CloudWatch Logs (scoped to `/itsm-agent*` log groups)

| Permission | Resource | Reason |
|-----------|----------|--------|
| `logs:CreateLogGroup` | `/itsm-agent*` | Create log groups on first use |
| `logs:CreateLogStream` | `/itsm-agent*` | Create per-instance log streams |
| `logs:PutLogEvents` | `/itsm-agent*` | Write application and system logs |
| `logs:DescribeLogGroups` | `/itsm-agent*` | CloudWatch agent health checks |
| `logs:DescribeLogStreams` | `/itsm-agent*` | CloudWatch agent health checks |

> **Not granted:** Access to log groups outside the `/itsm-agent` prefix, or `logs:DeleteLogGroup`.

#### CloudWatch Metrics

| Permission | Resource | Reason |
|-----------|----------|--------|
| `cloudwatch:PutMetricData` | `*` | Required by service design — CloudWatch does not support resource-level restrictions for PutMetricData |
| `cloudwatch:GetMetricStatistics` | `*` | CloudWatch agent health checks |
| `cloudwatch:ListMetrics` | `*` | CloudWatch agent health checks |
| `ec2:DescribeVolumes` | `*` | CloudWatch agent collects disk metrics |
| `ec2:DescribeTags` | `*` | CloudWatch agent populates instance dimensions |

#### AWS Systems Manager (managed policy)

The `AmazonSSMManagedInstanceCore` AWS-managed policy is attached to enable Session Manager access. This provides a secure, audit-logged alternative to SSH that does not require an open port 22.

### Reviewing the IAM Policies

```bash
# View the applied policies after deployment
terraform show | grep -A 20 "aws_iam_policy"

# Or via AWS CLI
aws iam get-role-policy \
  --role-name itsm-agent-ec2-role \
  --policy-name itsm-agent-s3-access
```

---

## Security Group Configuration

The Terraform configuration creates a security group with the following rules:

### Inbound Rules

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 8080 | TCP | `0.0.0.0/0` | OpenWebUI — restrict to internal CIDR in production |
| 8000 | TCP | `0.0.0.0/0` | RAG Backend API — restrict to internal CIDR in production |
| 22 | TCP | `admin_cidr` | SSH access — set to your IP/VPN CIDR in `terraform.tfvars` |

### Outbound Rules

| Port | Protocol | Destination | Purpose |
|------|----------|------------|---------|
| All | All | `0.0.0.0/0` | Allow outbound for package updates, Ollama model downloads, S3 access |

### Hardening for Production

Restrict the OpenWebUI and RAG API ports to trusted CIDR ranges:

```hcl
# In terraform.tfvars or as a variable
admin_cidr = "10.0.0.0/8"   # Corporate network CIDR
```

For a production deployment, consider:

1. **Place OpenWebUI behind an ALB** with HTTPS and an AWS WAF web ACL
2. **Keep the RAG API internal-only** — expose it only within the VPC or via an internal ALB
3. **Disable port 22** and use Session Manager exclusively for administrative access
4. **Enable AWS Shield Standard** (included at no cost) for DDoS protection on the EIP

---

## VPC Isolation

The deployment creates a dedicated VPC with the following isolation properties:

- **Separate VPC:** All resources run in an isolated VPC (`10.0.0.0/16` by default), separate from your default VPC and other workloads.
- **Public subnets:** The EC2 instance sits in a public subnet with a direct internet route via an Internet Gateway. This is required for Ollama model downloads and S3 access.
- **Private subnets:** Two private subnets are created for future use (e.g., adding a managed database or ElastiCache). These subnets have no internet gateway route.
- **No NAT Gateway:** Not included by default (cost saving). Add one if private-subnet resources need outbound internet access.

### Future: Moving the Application to a Private Subnet

For higher security, the EC2 instance can be moved to a private subnet with:
- A NAT Gateway for outbound traffic
- An internal ALB for inbound traffic from the public subnet
- VPC Endpoints for S3 and CloudWatch Logs to avoid traffic traversing the internet

---

## Encryption at Rest and in Transit

### At Rest

| Storage | Encryption | Details |
|---------|-----------|---------|
| Root EBS volume (50 GiB) | ✅ AES-256 | `encrypted = true` in `ec2.tf` |
| Data EBS volume (100 GiB) | ✅ AES-256 | `encrypted = true` in `ec2.tf` |
| S3 bucket | ✅ SSE-S3 | Server-side encryption enabled on all objects |
| S3 bucket versioning | ✅ Enabled | Allows recovery of accidentally deleted/overwritten documents |

### In Transit

| Connection | Encryption | Notes |
|-----------|-----------|-------|
| Browser → OpenWebUI | ❌ HTTP only | Add an ALB with ACM certificate for HTTPS in production |
| OpenWebUI → Ollama | ❌ HTTP (internal Docker network) | Acceptable for internal-only traffic |
| RAG Backend → Ollama | ❌ HTTP (internal Docker network) | Acceptable for internal-only traffic |
| RAG Backend → S3 | ✅ HTTPS | AWS SDK enforces HTTPS by default |
| EC2 → CloudWatch | ✅ HTTPS | CloudWatch agent uses HTTPS |
| SSH (admin) | ✅ SSH/TLS | Consider using Session Manager to eliminate port 22 |

### Enabling HTTPS for OpenWebUI

To add TLS termination for the OpenWebUI and RAG API in AWS:

1. Create an ACM certificate for your domain
2. Add an Application Load Balancer in front of the EC2 instance
3. Configure HTTPS listener (443) on the ALB forwarding to port 8080/8000
4. Update the security group to remove direct port 8080/8000 access and allow only the ALB

---

## Secrets Management

### What Is a Secret in This System?

| Secret | Local | AWS |
|--------|-------|-----|
| AWS credentials | `.env` (git-ignored) | IAM instance role — no credentials stored |
| S3 bucket name | `.env` | Terraform output / environment variable |
| EC2 key pair private key | `~/.ssh/*.pem` (local only) | Never stored on the instance |

### Rules

1. **Never commit `.env` or `terraform.tfvars` to source control.** Both are listed in `.gitignore`.

2. **Never hardcode credentials in Terraform files.** Use `terraform.tfvars` (git-ignored) or environment variables (`TF_VAR_*`).

3. **Rotate credentials if leaked.** If AWS credentials are accidentally committed, immediately:
   - Revoke the access key in IAM
   - Scan git history and rewrite it: `git filter-repo --path .env --invert-paths`
   - Notify your security team

4. **Use the EC2 instance role in production.** Never copy AWS credentials to the EC2 instance. The IAM role provides temporary credentials automatically via the instance metadata service.

5. **Restrict `.env` file permissions locally:**

```bash
chmod 600 .env
```

### Checking for Accidentally Committed Secrets

```bash
# Scan for common patterns in tracked files
git log --all --full-history --diff-filter=A -p -- "*.env" "*.tfvars" | grep -i "key\|secret\|password\|token"

# Use a tool like truffleHog or git-secrets for automated scanning
```

---

## Audit Logging with CloudWatch

### What Is Logged

| Log Stream | Content |
|-----------|---------|
| `{instance_id}/bootstrap` | EC2 initialisation script output |
| `{instance_id}/system` | OS-level messages (`/var/log/messages`) |
| Application stdout | FastAPI request/response logs (when backend is containerised with log driver) |

### Log Retention

Logs are retained for **90 days** by default (`log_retention_days` variable). Adjust in `terraform.tfvars`:

```hcl
log_retention_days = 365   # 1 year for compliance
```

### CloudWatch Alarms

The following alarms are configured automatically:

| Alarm | Threshold | Action |
|-------|-----------|--------|
| High CPU | > 80% for 5 consecutive minutes | SNS notification (if `alarm_sns_arn` set) |
| High memory | > 85% | SNS notification |
| High disk | > 85% | SNS notification |

### Viewing Logs

```bash
# Bootstrap log
aws logs tail /itsm-agent \
  --log-stream-name-prefix "<instance_id>/bootstrap" \
  --follow

# System log
aws logs tail /itsm-agent \
  --log-stream-name-prefix "<instance_id>/system" \
  --since 1h

# All recent logs
aws logs tail /itsm-agent --follow --since 30m
```

### Enabling SNS Alarm Notifications

```hcl
# terraform.tfvars
alarm_sns_arn = "arn:aws:sns:us-east-1:123456789012:itsm-ops-alerts"
```

Create the SNS topic and subscribe your email before deploying, then add the ARN to `terraform.tfvars`.

---

## EC2 Instance Hardening

The following hardening measures are applied by the Terraform configuration:

| Control | Implementation |
|---------|--------------|
| IMDSv2 required | `http_tokens = "required"` — mitigates SSRF credential theft |
| Hop limit = 1 | `http_put_response_hop_limit = 1` — prevents metadata access from containers |
| EBS encrypted | `encrypted = true` on all block devices |
| Detailed monitoring | `monitoring = true` — 1-minute CloudWatch metric resolution |
| SSM Session Manager | `AmazonSSMManagedInstanceCore` policy — enables audited shell access without SSH |
| IMDSv1 disabled | Enforced by `http_tokens = required` |

### Recommended Additional Hardening

- **Disable SSH (port 22)** after configuring Session Manager:
  - Remove the port 22 ingress rule from the security group in `vpc.tf`
  - Set `admin_cidr = ""` or remove the SSH rule entirely

- **Enable AWS Config** to detect configuration drift

- **Enable Amazon GuardDuty** for threat detection (EC2, S3, IAM anomalies)

- **Enable AWS Security Hub** to aggregate findings across services

---

## Compliance Notes

This system uses AI-generated responses. Consider the following before deploying in regulated environments:

| Area | Consideration |
|------|--------------|
| **Data residency** | All processing happens within the AWS region you configure. No data is sent to external AI providers (Ollama runs locally). |
| **PII in documents** | Documents uploaded to S3 are indexed and their contents may appear in chat responses. Do not upload documents containing unredacted PII if GDPR/CCPA applies. |
| **Audit trail** | Chat conversations are not logged to CloudWatch by default (session history is in-memory only). Add request logging middleware to the FastAPI backend if an audit trail of queries is required. |
| **Model hallucinations** | The RAG pipeline grounds responses in your documents, but the LLM may still produce incorrect information. Include a disclaimer in the OpenWebUI system prompt for production use. |
| **SOC 2 / ISO 27001** | AWS infrastructure components (EC2, S3, VPC, IAM, CloudWatch) are SOC 2 Type II and ISO 27001 certified. The application-level controls described in this document are the customer's responsibility. |
