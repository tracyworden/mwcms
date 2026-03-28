# Implementation Plan: AWS Infrastructure Security Hardening

## Overview

Application code changes first (testable locally), then Dockerfile fix, then CloudFormation template (bulk of work), then wiring/validation. Property tests and unit tests sit alongside the code they verify.

## Tasks

- [x] 1. Application code changes (local-testable)
  - [x] 1.1 Add `CORS_ALLOWED_ORIGINS` to Settings and cache `get_settings()` with `@lru_cache`
    - Add `CORS_ALLOWED_ORIGINS: str = "http://localhost:5173"` field to `Settings` in `app/api/config/settings.py`
    - Decorate `get_settings()` with `@lru_cache(maxsize=1)` so it returns the same instance on repeated calls
    - _Requirements: 5.3, 11.3_

  - [x] 1.2 Lock down CORS in `app/main.py` using the new settings field
    - Replace `allow_origins=["*"]` with origins parsed from `settings.CORS_ALLOWED_ORIGINS` (comma-split)
    - Move `get_settings()` call above middleware registration
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 1.3 Add HSTS middleware in `app/main.py`
    - Add `HSTSMiddleware` class (subclass of `BaseHTTPMiddleware`) that sets `Strict-Transport-Security: max-age=31536000; includeSubDomains` on every response
    - Add it after CORS middleware
    - _Requirements: 2.5_

  - [x] 1.4 Cache boto3 S3 client as singleton in `app/api/s3/client.py`
    - Decorate `_get_s3_client()` with `@lru_cache(maxsize=1)`
    - _Requirements: 11.1_

  - [x] 1.5 Cache DynamoDB Table resource as singleton in `app/api/auth/models.py`
    - Decorate `_get_table()` with `@lru_cache(maxsize=1)`
    - _Requirements: 11.2_

  - [x] 1.6 Rewrite health endpoint to use shared cached clients in `app/api/health/router.py`
    - Replace standalone `boto3.client("s3")` with `_get_s3_client()` from `app.api.s3.client`
    - Replace standalone `boto3.client("dynamodb")` with `_get_table().meta.client` from `app.api.auth.models`
    - Remove direct `boto3` import
    - _Requirements: 11.4, 11.5, 11.6_

  - [ ]* 1.7 Write property test: HSTS header present on all responses (Property 1)
    - **Property 1: HSTS header present on all responses**
    - Use Hypothesis to generate random valid URL paths, assert `Strict-Transport-Security` header with `max-age >= 31536000` on every response via FastAPI `TestClient`
    - File: `tests/property/test_hsts.py`
    - **Validates: Requirements 2.5**

  - [ ]* 1.8 Write property test: CORS rejects non-allowed origins (Property 5)
    - **Property 5: CORS rejects non-allowed origins**
    - Use Hypothesis to generate random `Origin` header values not matching the configured allowed origin, assert no `Access-Control-Allow-Origin` in response
    - File: `tests/property/test_cors.py`
    - **Validates: Requirements 5.1, 5.2, 5.4**

  - [ ]* 1.9 Write property test: Singleton caching for all factory functions (Property 11)
    - **Property 11: Singleton caching for all factory functions**
    - Use Hypothesis to generate N (2..50), call each factory function N times, assert `is`-identity on all return values
    - File: `tests/property/test_caching.py`
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.7**

  - [ ]* 1.10 Write unit tests for CORS, HSTS, settings caching, client caching, and health endpoint
    - Verify allowed origin gets `Access-Control-Allow-Origin`, wildcard origin is rejected
    - Verify exact HSTS header value on a known endpoint
    - Verify `get_settings()`, `_get_s3_client()`, `_get_table()` return same instance on second call
    - Verify health endpoint uses shared clients (mock boto3, assert no new client creation), returns 200/503 correctly
    - File: `tests/unit/test_app_changes.py`
    - _Requirements: 2.5, 5.1, 5.4, 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 2. Checkpoint - Verify application code changes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Dockerfile fix for bcrypt build
  - [x] 3.1 Update `Dockerfile` to install `build-essential` before `pip install` and remove it after
    - Chain `apt-get update && apt-get install -y --no-install-recommends build-essential`, then `pip install`, then `apt-get purge -y build-essential && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*` in a single `RUN` layer
    - Verify `.env` is NOT copied into the image (it isn't currently — confirm no `COPY .env` line exists)
    - _Requirements: 7.4, 6.5_

- [x] 4. CloudFormation template — network and security groups
  - [x] 4.1 Create `infra/template.yaml` with Parameters section and VPC resources
    - Define parameters: `DomainName`, `HostedZoneId`, `ImageUri`, `SessionSecretArn`, `AdminPrincipalArn`, `S3BucketName` (default `mw-family-videos-1`), `DynamoDBTableName` (default `User_Table`), `CorsAllowedOrigins`
    - Define VPC (10.0.0.0/16), 2 public subnets, 2 private subnets, Internet Gateway, public route table with 0.0.0.0/0 → IGW, private route table
    - _Requirements: 1.2_

  - [x] 4.2 Add VPC endpoints to the template
    - Gateway endpoints for S3 and DynamoDB (associated with private route table)
    - Interface endpoints for `ecr.api`, `ecr.dkr`, and `logs` (placed in private subnets, attached to VPC Endpoint SG)
    - Define VPC Endpoint security group: inbound TCP 443 from ECS SG
    - _Requirements: 1.3, 10.4, 10.5_

  - [x] 4.3 Add ALB and ECS security groups to the template
    - ALB SG: inbound TCP 443 and TCP 80 from 0.0.0.0/0, outbound TCP 8000 to ECS SG
    - ECS SG: inbound TCP 8000 from ALB SG, outbound TCP 443 to VPC Endpoint SG
    - _Requirements: 1.7, 1.8_

  - [ ]* 4.4 Write property test: No NAT gateways in CloudFormation template (Property 10)
    - **Property 10: No NAT gateways in CloudFormation template**
    - Parse the YAML template, scan all resource types, assert none is `AWS::EC2::NatGateway`
    - File: `tests/property/test_cfn_no_nat.py`
    - **Validates: Requirements 10.4**

- [x] 5. CloudFormation template — IAM roles and policies
  - [x] 5.1 Add Task_Role with inline policy for S3 read and DynamoDB GetItem
    - S3 actions: `s3:GetObject`, `s3:ListBucket`, `s3:HeadObject` scoped to `mw-family-videos-1` bucket and objects
    - DynamoDB action: `dynamodb:GetItem` scoped to exact `User_Table` ARN
    - Trust policy: `ecs-tasks.amazonaws.com`
    - _Requirements: 3.3, 3.4, 4.1, 4.2, 4.3_

  - [x] 5.2 Add Execution_Role with inline policy for ECR pull, SSM read, and CloudWatch Logs
    - ECR actions: `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `ecr:GetAuthorizationToken`
    - SSM action: `ssm:GetParameters` scoped to exact `SessionSecretArn` parameter
    - Logs actions: `logs:CreateLogStream`, `logs:PutLogEvents` scoped to the log group
    - Trust policy: `ecs-tasks.amazonaws.com`
    - _Requirements: 6.3, 7.2, 8.4, 9.3_

  - [ ]* 5.3 Write property test: Task_Role S3 permissions are exactly the read set (Property 2)
    - **Property 2: Task_Role S3 permissions are exactly the read set**
    - Parse the template, extract Task_Role S3 actions, assert set equality with `{s3:GetObject, s3:ListBucket, s3:HeadObject}`
    - File: `tests/property/test_iam_s3.py`
    - **Validates: Requirements 3.3, 3.4**

  - [ ]* 5.4 Write property test: Task_Role DynamoDB permissions are exactly GetItem (Property 3)
    - **Property 3: Task_Role DynamoDB permissions are exactly GetItem**
    - Parse the template, extract Task_Role DynamoDB actions, assert set is exactly `{dynamodb:GetItem}`
    - File: `tests/property/test_iam_dynamodb.py`
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 5.5 Write property test: DynamoDB resource ARN is not a wildcard (Property 4)
    - **Property 4: DynamoDB resource ARN is not a wildcard**
    - Parse the template, extract DynamoDB statement resources, assert none are `*` and all resolve to a specific table ARN
    - File: `tests/property/test_iam_dynamodb_arn.py`
    - **Validates: Requirements 4.3**

  - [ ]* 5.6 Write property test: Execution_Role SSM access scoped to exact parameter ARN (Property 6)
    - **Property 6: Execution_Role SSM access scoped to exact parameter ARN**
    - Parse the template, extract SSM resource from Execution_Role, assert it references the exact parameter ARN (not wildcard)
    - File: `tests/property/test_iam_ssm.py`
    - **Validates: Requirements 6.3**

  - [ ]* 5.7 Write property test: Task_Role has no secrets access (Property 7)
    - **Property 7: Task_Role has no secrets access**
    - Parse the template, scan all Task_Role actions, assert none match `ssm:*`, `secretsmanager:*`, or any secrets-related permission
    - File: `tests/property/test_iam_no_secrets.py`
    - **Validates: Requirements 6.4**

  - [ ]* 5.8 Write property test: No IAM users or access keys in template (Property 8)
    - **Property 8: No IAM users or access keys in CloudFormation template**
    - Parse the template, scan all resource types, assert none is `AWS::IAM::User` or `AWS::IAM::AccessKey`
    - File: `tests/property/test_cfn_no_iam_users.py`
    - **Validates: Requirements 7.3**

- [x] 6. Checkpoint - Validate IAM and network resources
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. CloudFormation template — ALB, DNS/TLS, and ECS
  - [x] 7.1 Add ALB, target group, HTTPS listener (443), and HTTP→HTTPS redirect listener (80)
    - Target group: health check `GET /health`, interval 30s, unhealthy threshold 3, port 8000
    - HTTPS listener uses ACM certificate
    - HTTP listener returns 301 redirect to HTTPS
    - _Requirements: 1.4, 1.5, 1.6, 2.3, 2.4_

  - [x] 7.2 Add ACM certificate with DNS validation and Route 53 A-record alias
    - ACM certificate for `DomainName` parameter, DNS validation via `HostedZoneId`
    - Route 53 A-record alias pointing `DomainName` to ALB
    - _Requirements: 2.1, 2.2_

  - [x] 7.3 Add ECR repository with image scanning and lifecycle policy
    - Private repository, `imageScanningConfiguration.scanOnPush: true`
    - Lifecycle policy: retain only 5 most recent images
    - _Requirements: 8.1, 8.2, 8.3, 8.5_

  - [x] 7.4 Add CloudWatch log group with 30-day retention
    - Log group name: `/ecs/media-viewer`
    - Retention: 30 days
    - _Requirements: 9.2_

  - [x] 7.5 Add ECS cluster, task definition, and service
    - Fargate task definition: 0.25 vCPU, 0.5 GB memory, `awsvpc` network mode
    - Container definition: port 8000, environment variables (`S3_BUCKET_NAME`, `AWS_REGION`, `DYNAMODB_TABLE_NAME`, `CORS_ALLOWED_ORIGINS`), secret (`SESSION_SECRET` from SSM `SessionSecretArn`)
    - Log configuration: `awslogs` driver pointing to the log group
    - Task role: `Task_Role`, execution role: `Execution_Role`
    - ECS service: desired count 1, launch type FARGATE, private subnets, ECS SG, target group attachment
    - _Requirements: 1.1, 1.6, 6.2, 7.1, 7.2, 9.1, 10.1, 10.2_

- [x] 8. CloudFormation template — existing resource configuration (S3 and DynamoDB)
  - [x] 8.1 Add S3 bucket policy, Block Public Access, and default encryption for `mw-family-videos-1`
    - Bucket policy: deny all except Task_Role and Admin_Principal (using `StringNotEquals` on `aws:PrincipalArn`)
    - Block Public Access: all four settings true
    - Default encryption: SSE-S3 (AES-256)
    - _Requirements: 3.1, 3.2, 3.5, 3.6_

  - [x] 8.2 Add DynamoDB table configuration for `User_Table`
    - Enable point-in-time recovery
    - Confirm default encryption (AWS-owned key)
    - Billing mode: PAY_PER_REQUEST
    - _Requirements: 4.4, 4.5, 10.3_

- [x] 9. Checkpoint - Validate full CloudFormation template
  - Run `aws cloudformation validate-template --template-body file://infra/template.yaml` to check syntax
  - Ensure all property and unit tests pass, ask the user if questions arise.

- [x] 10. Final wiring and verification
  - [x] 10.1 Add SSM Parameter Store SecureString resource to the template for SESSION_SECRET
    - Resource type `AWS::SSM::Parameter`, type `SecureString`
    - The `SessionSecretArn` parameter is used by the Execution_Role and task definition `secrets` block
    - _Requirements: 6.1, 6.6_

  - [ ]* 10.2 Write property test: No explicit AWS credentials in boto3 calls (Property 9)
    - **Property 9: No explicit AWS credentials in boto3 client creation**
    - AST-parse all Python files under `app/`, find `boto3.client()` and `boto3.resource()` calls, assert none pass `aws_access_key_id` or `aws_secret_access_key` as arguments
    - File: `tests/property/test_no_credentials.py`
    - **Validates: Requirements 7.5**

  - [ ]* 10.3 Write unit tests for CloudFormation template structure
    - Parse `infra/template.yaml`, verify Task_Role has exactly the expected statements
    - Verify ECS task definition has correct CPU/memory, port mapping, environment variables, and secrets
    - Verify ALB listeners, target group health check config, security group rules
    - Verify ECR lifecycle policy retains 5 images
    - Verify log group retention is 30 days
    - File: `tests/unit/test_cfn_template.py`
    - _Requirements: 1.1, 1.4, 1.5, 1.7, 1.8, 3.1, 3.2, 8.2, 8.3, 9.2, 10.1, 10.2_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Application code changes (tasks 1.1–1.6) can be tested locally before any AWS resources exist
- The CloudFormation template is a single file `infra/template.yaml` — validate with `aws cloudformation validate-template` at checkpoint 9
- Property tests validate universal correctness properties from the design document
- Existing resources (S3 bucket, DynamoDB table, Route 53 hosted zone) are referenced, not created, by the template
