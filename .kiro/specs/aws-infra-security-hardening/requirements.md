# Requirements Document

## Introduction

Deploy the existing FastAPI/React media viewer application to AWS with production-grade security hardening. The application is a family video browser backed by S3 and DynamoDB, currently running locally. This spec covers ECS Fargate deployment, HTTPS via ACM/Route 53, IAM least-privilege, secrets management, S3 bucket lockdown, and CORS restriction. The target audience is a small family group (zero customers today), so infrastructure is right-sized for minimal cost and operational simplicity — not enterprise scale.

### What's out of scope

- Auto-scaling, multi-AZ redundancy, or high-availability patterns (no customers yet)
- CI/CD pipeline (deploy manually or via CLI for now)
- WAF, CloudFront CDN, or DDoS protection (overkill at this stage)
- Application code changes beyond CORS origin configuration, HSTS middleware addition, secrets retrieval, and backend performance fixes (boto3 client caching, settings caching, health endpoint client reuse)
- React Native TV app infrastructure (future concern)
- Monitoring/alerting beyond basic CloudWatch container logs

### Honest callouts

- Presigned URL expiration is capped at 3600s (1 hour). Fine for now, but the TV app may need longer sessions for buffering large videos.
- The `list_media_by_year` endpoint makes N individual S3 GetObject calls (one per item) to fetch metadata on the first page load. The existing TTL cache prevents repeat hits, but the cold-load N+1 pattern remains. Batch-fetching metadata is not straightforward with S3's API, so this is accepted as a known tradeoff for now.

## Glossary

- **ECS_Task**: An AWS ECS Fargate task running the Docker container that serves both the FastAPI backend and React frontend static files.
- **Task_Role**: The IAM role assumed by the ECS_Task at runtime, granting access to S3 and DynamoDB.
- **Execution_Role**: The IAM role used by ECS to pull the container image from ECR and inject secrets at task startup.
- **ALB**: Application Load Balancer that terminates HTTPS and forwards traffic to the ECS_Task.
- **Media_Bucket**: The S3 bucket `mw-family-videos-1` storing videos, thumbnails, metadata JSON, and transcripts.
- **User_Table**: The DynamoDB table `User_Table` storing usernames and bcrypt password hashes.
- **ACM_Certificate**: An AWS Certificate Manager TLS certificate for the application domain.
- **Secrets_Store**: AWS Systems Manager Parameter Store (SecureString) or AWS Secrets Manager, used to store the SESSION_SECRET value.
- **VPC**: The Virtual Private Cloud network containing the ECS_Task, ALB, and associated security groups.
- **IaC_Templates**: Infrastructure-as-Code definitions (CloudFormation or Terraform) that provision all AWS resources.
- **Admin_Principal**: The IAM role or user belonging to the application owner, used for console/CLI access to the Media_Bucket.
- **S3_Client_Module**: The `app/api/s3/client.py` module that provides all S3 operations (list, get, presign, head) to the rest of the application.
- **Auth_Models_Module**: The `app/api/auth/models.py` module that provides DynamoDB User_Table access to the rest of the application.
- **Settings_Factory**: The `get_settings()` function in `app/api/config/settings.py` that returns a `Settings` pydantic object populated from environment variables.
- **Health_Endpoint**: The `/health` endpoint in `app/api/health/router.py` that checks S3 and DynamoDB connectivity.

## Requirements

### Requirement 1: ECS Fargate Deployment

**User Story:** As the application owner, I want to run the Docker container on ECS Fargate, so that the app is accessible on the internet without managing EC2 instances.

#### Acceptance Criteria

1. THE IaC_Templates SHALL define an ECS Fargate service that runs exactly one ECS_Task using the application Docker image from ECR.
2. THE IaC_Templates SHALL define a VPC with public subnets for the ALB and private subnets for the ECS_Task.
3. THE ECS_Task SHALL run in a private subnet with outbound access provided exclusively by VPC endpoints: gateway endpoints for S3 and DynamoDB (free), and interface endpoints for ECR (ecr.api and ecr.dkr), Secrets Manager, and CloudWatch Logs.
4. THE IaC_Templates SHALL define an ALB in public subnets that forwards HTTPS traffic to the ECS_Task on port 8000.
5. THE ALB SHALL perform health checks against the `/health` endpoint and route traffic only to healthy ECS_Tasks.
6. WHEN the ECS_Task fails the ALB health check three consecutive times, THE ECS service SHALL replace the ECS_Task with a new instance.
7. THE IaC_Templates SHALL define a security group for the ECS_Task that allows inbound traffic only from the ALB security group on port 8000.
8. THE IaC_Templates SHALL define a security group for the ALB that allows inbound traffic only on ports 443 (HTTPS) and 80 (HTTP redirect).

### Requirement 2: Domain and HTTPS

**User Story:** As the application owner, I want the app served over HTTPS on a custom domain, so that users access it via a memorable URL with encrypted connections.

#### Acceptance Criteria

1. THE IaC_Templates SHALL provision an ACM_Certificate for the application domain with DNS validation via Route 53.
2. THE IaC_Templates SHALL create a Route 53 A-record (alias) pointing the application domain to the ALB.
3. THE ALB SHALL terminate TLS using the ACM_Certificate.
4. WHEN a request arrives on port 80, THE ALB SHALL redirect the request to HTTPS (port 443) with a 301 status code.
5. THE FastAPI application SHALL set the `Strict-Transport-Security` header with a max-age of at least 31536000 seconds on all responses via a middleware.

### Requirement 3: S3 Bucket Security

**User Story:** As the application owner, I want the Media_Bucket locked down so that only the ECS_Task can read objects, so that video files are not publicly accessible.

#### Acceptance Criteria

1. THE IaC_Templates SHALL enable S3 Block Public Access on the Media_Bucket with all four block settings set to true (BlockPublicAcls, IgnorePublicAcls, BlockPublicPolicy, RestrictPublicBuckets).
2. THE IaC_Templates SHALL define a bucket policy on the Media_Bucket that denies all access except from the Task_Role principal and the designated Admin_Principal (admin IAM role or user).
3. THE Task_Role SHALL have an IAM policy that grants `s3:GetObject`, `s3:ListBucket`, and `s3:HeadObject` on the Media_Bucket and its objects, and no other S3 permissions.
4. THE Task_Role SHALL NOT have `s3:PutObject`, `s3:DeleteObject`, or any write permissions on the Media_Bucket.
5. IF a request to the Media_Bucket originates from a principal other than the Task_Role or the Admin_Principal, THEN THE Media_Bucket bucket policy SHALL deny the request.
6. THE IaC_Templates SHALL enable default server-side encryption (SSE-S3 or SSE-KMS) on the Media_Bucket.

### Requirement 4: DynamoDB Security

**User Story:** As the application owner, I want DynamoDB access scoped to the minimum operations needed, so that a compromised task cannot scan or delete user data.

#### Acceptance Criteria

1. THE Task_Role SHALL have an IAM policy that grants `dynamodb:GetItem` on the User_Table resource ARN only.
2. THE Task_Role SHALL NOT have `dynamodb:Scan`, `dynamodb:Query`, `dynamodb:PutItem`, `dynamodb:DeleteItem`, `dynamodb:UpdateItem`, or `dynamodb:BatchWriteItem` on the User_Table.
3. THE IAM policy for DynamoDB access SHALL scope the Resource to the exact User_Table ARN, not a wildcard.
4. THE IaC_Templates SHALL enable DynamoDB point-in-time recovery on the User_Table.
5. THE IaC_Templates SHALL enable server-side encryption on the User_Table using the AWS-owned key (default encryption).

### Requirement 5: CORS Lockdown

**User Story:** As the application owner, I want CORS restricted to the actual application domain, so that browsers reject cross-origin requests from unauthorized sites.

#### Acceptance Criteria

1. THE FastAPI application SHALL configure `allow_origins` in the CORSMiddleware to contain only the production domain URL (`https://mw.mzwcms.com`).
2. THE FastAPI application SHALL NOT use the wildcard `*` for `allow_origins` in production.
3. THE FastAPI application SHALL read the allowed CORS origin from an environment variable so it can differ between local development and production.
4. WHEN a request arrives with an `Origin` header that does not match the configured allowed origin, THE FastAPI application SHALL omit the `Access-Control-Allow-Origin` header from the response.

### Requirement 6: Secrets Management

**User Story:** As the application owner, I want the SESSION_SECRET stored in a managed secrets service instead of a .env file, so that the secret is not committed to source control or stored in plaintext on disk.

#### Acceptance Criteria

1. THE IaC_Templates SHALL create a Secrets_Store entry (SSM Parameter Store SecureString or Secrets Manager secret) containing the SESSION_SECRET value.
2. THE ECS task definition SHALL inject the SESSION_SECRET into the container as an environment variable sourced from the Secrets_Store at task startup.
3. THE Execution_Role SHALL have an IAM policy granting read access to the specific Secrets_Store entry ARN, and no other secrets.
4. THE Task_Role SHALL NOT have read access to the Secrets_Store entry (only the Execution_Role needs it for injection).
5. THE .env file SHALL NOT be included in the Docker image or deployed to production.
6. IF the Secrets_Store entry is unavailable at task startup, THEN THE ECS_Task SHALL fail to start and the ECS service SHALL log the failure to CloudWatch.

### Requirement 7: IAM Role-Based Access (No Access Keys)

**User Story:** As the application owner, I want the ECS task to use IAM task roles for all AWS API calls, so that no long-lived access keys exist in the environment.

#### Acceptance Criteria

1. THE ECS task definition SHALL assign the Task_Role as the task IAM role, enabling boto3 to use the container credential provider automatically.
2. THE ECS task definition SHALL assign the Execution_Role as the task execution role for ECR image pull and secret injection.
3. THE IaC_Templates SHALL NOT create IAM users or access keys for the application.
4. THE Docker container SHALL NOT contain AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY environment variables.
5. WHEN boto3 initializes inside the ECS_Task, THE boto3 client SHALL resolve credentials from the ECS container credential provider (169.254.170.2) without explicit credential configuration.

### Requirement 8: Container Image and ECR

**User Story:** As the application owner, I want the Docker image stored in a private ECR repository, so that the image is not publicly accessible and is scanned for vulnerabilities.

#### Acceptance Criteria

1. THE IaC_Templates SHALL create a private ECR repository for the application image.
2. THE ECR repository SHALL have image scanning enabled on push.
3. THE ECR repository SHALL have a lifecycle policy that retains only the 5 most recent images to limit storage costs.
4. THE Execution_Role SHALL have permissions to pull images from the ECR repository.
5. THE ECR repository SHALL NOT allow public access.

### Requirement 9: Logging and Observability

**User Story:** As the application owner, I want container logs shipped to CloudWatch, so that I can debug issues without SSH access to a container.

#### Acceptance Criteria

1. THE ECS task definition SHALL configure the `awslogs` log driver to send container stdout and stderr to a CloudWatch log group.
2. THE IaC_Templates SHALL create the CloudWatch log group with a retention period of 30 days to limit costs.
3. THE Execution_Role SHALL have permissions to create log streams and put log events in the designated log group.

### Requirement 10: Cost Controls

**User Story:** As the application owner, I want infrastructure right-sized for zero-to-low traffic, so that monthly AWS costs stay minimal while the app has no external customers.

#### Acceptance Criteria

1. THE ECS Fargate task SHALL use the smallest available resource allocation (0.25 vCPU, 0.5 GB memory) unless the application fails health checks at that size.
2. THE ECS service SHALL run exactly one task (desired count = 1) with no auto-scaling configured.
3. THE DynamoDB User_Table SHALL use on-demand (PAY_PER_REQUEST) billing mode.
4. THE IaC_Templates SHALL NOT provision any NAT gateways; all outbound AWS API access from the ECS_Task SHALL use VPC endpoints exclusively.
5. THE IaC_Templates SHALL provision gateway endpoints for S3 and DynamoDB (free) and interface endpoints for ECR, Secrets Manager, and CloudWatch Logs.

### Requirement 11: Backend Performance Fixes (boto3 Client and Settings Caching)

**User Story:** As the application owner, I want boto3 clients and application settings cached as singletons, so that the backend does not waste time re-creating connections and re-parsing configuration on every request.

#### Acceptance Criteria

1. THE S3_Client_Module SHALL create the boto3 S3 client once at module level and reuse the same client instance for all subsequent calls to `_get_s3_client()`.
2. THE Auth_Models_Module SHALL create the boto3 DynamoDB Table resource once at module level and reuse the same Table instance for all subsequent calls to `_get_table()`.
3. THE Settings_Factory SHALL cache the Settings object so that `get_settings()` returns the same instance on repeated calls without re-reading environment variables (e.g., via `@lru_cache` or a module-level singleton).
4. THE Health_Endpoint SHALL use the shared boto3 S3 client from the S3_Client_Module instead of creating an independent `boto3.client("s3")` on each health check.
5. THE Health_Endpoint SHALL use the shared boto3 DynamoDB resource from the Auth_Models_Module (or an equivalent shared client) instead of creating an independent `boto3.client("dynamodb")` on each health check.
6. WHEN the application starts, THE cached boto3 clients SHALL be initialized using the AWS_REGION value from the cached Settings object.
7. THE cached clients and settings SHALL remain valid for the lifetime of the application process (no per-request expiration needed, since the ECS_Task is replaced on redeploy).
