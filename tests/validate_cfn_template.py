"""
Comprehensive structural validation of infra/template.yaml.
Task 9 checkpoint: parse YAML, verify all expected resources, policies, and configurations.
"""
import sys
import json
import yaml

TEMPLATE_PATH = "infra/template.yaml"

# Register CloudFormation intrinsic function tags so PyYAML can parse them
CFN_TAGS = [
    "!Ref", "!Sub", "!GetAtt", "!Select", "!GetAZs", "!Join",
    "!If", "!Not", "!Equals", "!And", "!Or", "!FindInMap",
    "!Base64", "!Cidr", "!ImportValue", "!Split", "!Transform",
]

def _cfn_constructor(loader, tag_suffix, node):
    """Generic constructor that preserves the tag as metadata."""
    if isinstance(node, yaml.ScalarNode):
        val = loader.construct_scalar(node)
        return {tag_suffix: val}
    elif isinstance(node, yaml.SequenceNode):
        val = loader.construct_sequence(node)
        return {tag_suffix: val}
    elif isinstance(node, yaml.MappingNode):
        val = loader.construct_mapping(node)
        return {tag_suffix: val}
    return None

class CfnLoader(yaml.SafeLoader):
    pass

# Register all known CloudFormation tags
for tag in CFN_TAGS:
    CfnLoader.add_constructor(tag, lambda loader, node, t=tag: _cfn_constructor(loader, t, node))

# Also handle multi-constructors for any unknown tags
CfnLoader.add_multi_constructor("!", lambda loader, suffix, node: _cfn_constructor(loader, "!" + suffix, node))


def load_template():
    with open(TEMPLATE_PATH, "r") as f:
        return yaml.load(f, Loader=CfnLoader)

def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {label}"
    if detail and not condition:
        msg += f" -- {detail}"
    print(msg)
    return condition


def main():
    print("=" * 70)
    print("CloudFormation Template Validation - Task 9 Checkpoint")
    print("=" * 70)

    # ---- 1. Valid YAML ----
    print("\n1. YAML Validity")
    try:
        tpl = load_template()
        check("Template is valid YAML", True)
    except yaml.YAMLError as e:
        check("Template is valid YAML", False, str(e))
        sys.exit(1)

    resources = tpl.get("Resources", {})
    params = tpl.get("Parameters", {})

    # ---- 2. Resource count and expected types ----
    print("\n2. Resource Count and Types")
    resource_types = {name: res["Type"] for name, res in resources.items()}
    type_set = set(resource_types.values())
    print(f"  Total resources: {len(resources)}")

    expected_types = {
        "AWS::EC2::VPC",
        "AWS::EC2::Subnet",
        "AWS::EC2::InternetGateway",
        "AWS::EC2::VPCGatewayAttachment",
        "AWS::EC2::RouteTable",
        "AWS::EC2::Route",
        "AWS::EC2::SubnetRouteTableAssociation",
        "AWS::EC2::VPCEndpoint",
        "AWS::EC2::SecurityGroup",
        "AWS::IAM::Role",
        "AWS::ElasticLoadBalancingV2::LoadBalancer",
        "AWS::ElasticLoadBalancingV2::TargetGroup",
        "AWS::ElasticLoadBalancingV2::Listener",
        "AWS::CertificateManager::Certificate",
        "AWS::Route53::RecordSet",
        "AWS::ECR::Repository",
        "AWS::Logs::LogGroup",
        "AWS::ECS::Cluster",
        "AWS::ECS::TaskDefinition",
        "AWS::ECS::Service",
        "AWS::S3::BucketPolicy",
    }
    missing_types = expected_types - type_set
    check("All expected resource types present", len(missing_types) == 0,
          f"Missing: {missing_types}")

    # ---- 3. No NAT gateways, no IAM users, no access keys ----
    print("\n3. Forbidden Resources")
    forbidden = {"AWS::EC2::NatGateway", "AWS::IAM::User", "AWS::IAM::AccessKey"}
    found_forbidden = forbidden & type_set
    check("No NAT gateways", "AWS::EC2::NatGateway" not in type_set)
    check("No IAM users", "AWS::IAM::User" not in type_set)
    check("No IAM access keys", "AWS::IAM::AccessKey" not in type_set)

    # ---- 4. TaskRole S3 and DynamoDB actions ----
    print("\n4. TaskRole Permissions")
    task_role = resources.get("TaskRole", {})
    task_policies = task_role.get("Properties", {}).get("Policies", [])
    task_statements = []
    for pol in task_policies:
        stmts = pol.get("PolicyDocument", {}).get("Statement", [])
        task_statements.extend(stmts)

    # Find S3 statement
    s3_actions = set()
    dynamo_actions = set()
    for stmt in task_statements:
        actions = stmt.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        for a in actions:
            if a.startswith("s3:"):
                s3_actions.add(a)
            if a.startswith("dynamodb:"):
                dynamo_actions.add(a)

    expected_s3 = {"s3:GetObject", "s3:ListBucket", "s3:HeadObject"}
    check("TaskRole S3 actions are exactly the read set",
          s3_actions == expected_s3,
          f"Got: {s3_actions}, Expected: {expected_s3}")

    expected_dynamo = {"dynamodb:GetItem"}
    check("TaskRole DynamoDB actions are exactly GetItem",
          dynamo_actions == expected_dynamo,
          f"Got: {dynamo_actions}, Expected: {expected_dynamo}")

    # ---- 5. ExecutionRole actions ----
    print("\n5. ExecutionRole Permissions")
    exec_role = resources.get("ExecutionRole", {})
    exec_policies = exec_role.get("Properties", {}).get("Policies", [])
    exec_statements = []
    for pol in exec_policies:
        stmts = pol.get("PolicyDocument", {}).get("Statement", [])
        exec_statements.extend(stmts)

    ecr_actions = set()
    ssm_actions = set()
    logs_actions = set()
    for stmt in exec_statements:
        actions = stmt.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        for a in actions:
            if a.startswith("ecr:"):
                ecr_actions.add(a)
            if a.startswith("ssm:"):
                ssm_actions.add(a)
            if a.startswith("logs:"):
                logs_actions.add(a)

    expected_ecr = {"ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage", "ecr:GetAuthorizationToken"}
    check("ExecutionRole has ECR pull actions",
          ecr_actions == expected_ecr,
          f"Got: {ecr_actions}")

    expected_ssm = {"ssm:GetParameters"}
    check("ExecutionRole has SSM read action",
          ssm_actions == expected_ssm,
          f"Got: {ssm_actions}")

    expected_logs = {"logs:CreateLogStream", "logs:PutLogEvents"}
    check("ExecutionRole has CloudWatch Logs actions",
          logs_actions == expected_logs,
          f"Got: {logs_actions}")

    # ---- 6. ECS Task Definition ----
    print("\n6. ECS Task Definition")
    task_def = resources.get("TaskDefinition", {}).get("Properties", {})
    check("CPU is 256 (0.25 vCPU)", task_def.get("Cpu") == "256",
          f"Got: {task_def.get('Cpu')}")
    check("Memory is 512 (0.5 GB)", task_def.get("Memory") == "512",
          f"Got: {task_def.get('Memory')}")
    check("Network mode is awsvpc", task_def.get("NetworkMode") == "awsvpc")
    check("Requires FARGATE", "FARGATE" in task_def.get("RequiresCompatibilities", []))

    containers = task_def.get("ContainerDefinitions", [])
    check("Has exactly 1 container definition", len(containers) == 1,
          f"Got {len(containers)}")

    if containers:
        container = containers[0]
        # Port mapping
        ports = container.get("PortMappings", [])
        port_8000 = any(p.get("ContainerPort") == 8000 for p in ports)
        check("Container port 8000 mapped", port_8000)

        # Environment variables
        env_vars = {e["Name"]: e["Value"] for e in container.get("Environment", [])
                    if isinstance(e, dict)}
        expected_env_names = {"S3_BUCKET_NAME", "AWS_REGION", "DYNAMODB_TABLE_NAME", "CORS_ALLOWED_ORIGINS"}
        check("All expected env vars present",
              expected_env_names.issubset(set(env_vars.keys())),
              f"Missing: {expected_env_names - set(env_vars.keys())}")

        # Secrets
        secrets = container.get("Secrets", [])
        secret_names = {s["Name"] for s in secrets if isinstance(s, dict)}
        check("SESSION_SECRET injected as secret", "SESSION_SECRET" in secret_names,
              f"Got secrets: {secret_names}")

        # Log configuration
        log_config = container.get("LogConfiguration", {})
        check("Log driver is awslogs", log_config.get("LogDriver") == "awslogs")
        log_opts = log_config.get("Options", {})
        # awslogs-group may be a Ref, check for it
        awslogs_group = log_opts.get("awslogs-group")
        if isinstance(awslogs_group, dict):
            # YAML parser turns !Ref into {'!Ref': 'LogGroup'}
            refs_loggroup = (
                awslogs_group.get("Ref") == "LogGroup" or
                awslogs_group.get("!Ref") == "LogGroup"
            )
            check("awslogs-group references LogGroup", refs_loggroup,
                  f"Got: {awslogs_group}")
        else:
            check("awslogs-group is /ecs/media-viewer",
                  awslogs_group == "/ecs/media-viewer",
                  f"Got: {awslogs_group}")
        check("awslogs-stream-prefix is ecs",
              log_opts.get("awslogs-stream-prefix") == "ecs")

    # ---- 7. ALB Listeners, Target Group, Security Groups ----
    print("\n7. ALB, Target Group, and Security Groups")

    # Target group health check
    tg = resources.get("TargetGroup", {}).get("Properties", {})
    check("Target group health check path is /health",
          tg.get("HealthCheckPath") == "/health",
          f"Got: {tg.get('HealthCheckPath')}")
    check("Health check interval is 30s",
          tg.get("HealthCheckIntervalSeconds") == 30,
          f"Got: {tg.get('HealthCheckIntervalSeconds')}")
    check("Unhealthy threshold is 3",
          tg.get("UnhealthyThresholdCount") == 3,
          f"Got: {tg.get('UnhealthyThresholdCount')}")
    check("Target group port is 8000",
          tg.get("Port") == 8000,
          f"Got: {tg.get('Port')}")
    check("Target type is ip",
          tg.get("TargetType") == "ip")

    # HTTPS listener (443)
    https_listener = resources.get("HTTPSListener", {}).get("Properties", {})
    check("HTTPS listener on port 443",
          https_listener.get("Port") == 443)
    check("HTTPS listener protocol is HTTPS",
          https_listener.get("Protocol") == "HTTPS")
    https_actions = https_listener.get("DefaultActions", [])
    check("HTTPS listener forwards to target group",
          any(a.get("Type") == "forward" for a in https_actions))

    # HTTP listener (80 redirect)
    http_listener = resources.get("HTTPListener", {}).get("Properties", {})
    check("HTTP listener on port 80",
          http_listener.get("Port") == 80)
    http_actions = http_listener.get("DefaultActions", [])
    has_redirect = any(
        a.get("Type") == "redirect" and
        a.get("RedirectConfig", {}).get("StatusCode") == "HTTP_301" and
        a.get("RedirectConfig", {}).get("Protocol") == "HTTPS"
        for a in http_actions
    )
    check("HTTP listener redirects to HTTPS with 301", has_redirect)

    # ALB Security Group
    alb_sg = resources.get("ALBSecurityGroup", {}).get("Properties", {})
    alb_ingress = alb_sg.get("SecurityGroupIngress", [])
    alb_ingress_ports = {r.get("FromPort") for r in alb_ingress}
    check("ALB SG allows inbound 443", 443 in alb_ingress_ports)
    check("ALB SG allows inbound 80", 80 in alb_ingress_ports)

    alb_egress = alb_sg.get("SecurityGroupEgress", [])
    alb_egress_ports = {r.get("FromPort") for r in alb_egress}
    check("ALB SG egress to port 8000", 8000 in alb_egress_ports)

    # ECS Security Group
    ecs_sg = resources.get("ECSSecurityGroup", {}).get("Properties", {})
    ecs_ingress = ecs_sg.get("SecurityGroupIngress", [])
    ecs_ingress_ports = {r.get("FromPort") for r in ecs_ingress}
    check("ECS SG allows inbound 8000 only", ecs_ingress_ports == {8000})

    ecs_egress = ecs_sg.get("SecurityGroupEgress", [])
    ecs_egress_ports = {r.get("FromPort") for r in ecs_egress}
    check("ECS SG egress to port 443 (VPC endpoints)", 443 in ecs_egress_ports)

    # ---- 8. ECR Lifecycle Policy ----
    print("\n8. ECR Repository")
    ecr = resources.get("ECRRepository", {}).get("Properties", {})
    scan_config = ecr.get("ImageScanningConfiguration", {})
    check("Image scanning on push enabled", scan_config.get("ScanOnPush") is True)

    lifecycle_text = ecr.get("LifecyclePolicy", {}).get("LifecyclePolicyText", "")
    if isinstance(lifecycle_text, str) and lifecycle_text.strip():
        lifecycle = json.loads(lifecycle_text)
        rules = lifecycle.get("rules", [])
        check("Has lifecycle rules", len(rules) > 0)
        if rules:
            rule = rules[0]
            count = rule.get("selection", {}).get("countNumber")
            check("Lifecycle retains 5 images", count == 5,
                  f"Got countNumber: {count}")
    else:
        check("Lifecycle policy text present", False, "No lifecycle policy found")

    # ---- 9. Log Group Retention ----
    print("\n9. CloudWatch Log Group")
    log_group = resources.get("LogGroup", {}).get("Properties", {})
    check("Log group name is /ecs/media-viewer",
          log_group.get("LogGroupName") == "/ecs/media-viewer",
          f"Got: {log_group.get('LogGroupName')}")
    check("Retention is 30 days",
          log_group.get("RetentionInDays") == 30,
          f"Got: {log_group.get('RetentionInDays')}")

    # ---- Summary ----
    print("\n" + "=" * 70)
    print("Validation complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()
