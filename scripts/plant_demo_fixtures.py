"""
FinOps Cost Guardian — Demo Fixture Planting Script
Plants safe test fixtures in the personal AWS account to demonstrate:
  1. EC2 Instance tagged 'eligible-for-remediation=true' (Demonstrates auto-stop)
  2. EBS Volume tagged 'DoNotStop=true' (Demonstrates exclusion guard preservation)
  3. Elastic IP tagged 'eligible-for-remediation=true' (Demonstrates unassociated EIP release)

All resources are tagged 'DemoFixture=true' and 'Project=FinOpsCostGuardian'
for immediate bulk removal via cleanup_demo_fixtures.py.
"""

import sys
import os
import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))


def get_default_ami(ec2_client) -> str:
    """Find the latest Amazon Linux 2023 minimal AMI or standard SSM parameter."""
    try:
        ssm = boto3.client("ssm", region_name=REGION)
        param = ssm.get_parameter(Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64")
        return param["Parameter"]["Value"]
    except Exception:
        # Fallback to describing public Amazon Linux images
        try:
            images = ec2_client.describe_images(
                Owners=["amazon"],
                Filters=[
                    {"Name": "name", "Values": ["al2023-ami-2023.*-x86_64"]},
                    {"Name": "state", "Values": ["available"]}
                ]
            ).get("Images", [])
            if images:
                images.sort(key=lambda x: x["CreationDate"], reverse=True)
                return images[0]["ImageId"]
        except Exception:
            pass
    # Common us-east-1 AL2023 fallback AMI
    return "ami-0c101f26f147fa7fd"


def plant_fixtures():
    print(f"\n=======================================================")
    print(f"  FinOps Cost Guardian — Planting Live Demo Fixtures")
    print(f"  Target Region: {REGION}")
    print(f"=======================================================\n")

    ec2 = boto3.client("ec2", region_name=REGION)
    planted = {"ec2": [], "ebs": [], "eip": []}

    # 1. Plant EC2 Instance (eligible-for-remediation=true)
    try:
        ami_id = get_default_ami(ec2)
        print(f"[1/3] Launching t2.micro EC2 Instance using AMI: {ami_id}...")
        res = ec2.run_instances(
            ImageId=ami_id,
            InstanceType="t2.micro",
            MinCount=1,
            MaxCount=1,
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name", "Value": "finops-demo-eligible-ec2"},
                        {"Key": "Project", "Value": "FinOpsCostGuardian"},
                        {"Key": "eligible-for-remediation", "Value": "true"},
                        {"Key": "DemoFixture", "Value": "true"},
                        {"Key": "Env", "Value": "demo"}
                    ]
                }
            ]
        )
        instance_id = res["Instances"][0]["InstanceId"]
        planted["ec2"].append(instance_id)
        print(f"      -> SUCCESS: Launched {instance_id}")
        print(f"         Tags: eligible-for-remediation=true, DemoFixture=true")
    except Exception as e:
        print(f"      -> ERROR launching EC2: {e}")

    # 2. Plant Unattached EBS Volume (DoNotStop=true)
    try:
        print(f"\n[2/3] Creating 1 GB Unattached EBS Volume (DoNotStop=true)...")
        # Get AZ from EC2 instance or first available AZ
        az = f"{REGION}a"
        try:
            azs = ec2.describe_availability_zones()["AvailabilityZones"]
            if azs:
                az = azs[0]["ZoneName"]
        except Exception:
            pass

        vol_res = ec2.create_volume(
            AvailabilityZone=az,
            Size=1,
            VolumeType="gp3",
            TagSpecifications=[
                {
                    "ResourceType": "volume",
                    "Tags": [
                        {"Key": "Name", "Value": "finops-demo-donotstop-ebs"},
                        {"Key": "Project", "Value": "FinOpsCostGuardian"},
                        {"Key": "DoNotStop", "Value": "true"},
                        {"Key": "DemoFixture", "Value": "true"},
                        {"Key": "Env", "Value": "demo"}
                    ]
                }
            ]
        )
        vol_id = vol_res["VolumeId"]
        planted["ebs"].append(vol_id)
        print(f"      -> SUCCESS: Created volume {vol_id} in {az}")
        print(f"         Tags: DoNotStop=true (Strict Exclusion Guard), DemoFixture=true")
    except Exception as e:
        print(f"      -> ERROR creating EBS volume: {e}")

    # 3. Plant Unassociated Elastic IP (eligible-for-remediation=true)
    try:
        print(f"\n[3/3] Allocating Unassociated Elastic IP...")
        eip_res = ec2.allocate_address(
            Domain="vpc",
            TagSpecifications=[
                {
                    "ResourceType": "elastic-ip",
                    "Tags": [
                        {"Key": "Name", "Value": "finops-demo-eligible-eip"},
                        {"Key": "Project", "Value": "FinOpsCostGuardian"},
                        {"Key": "eligible-for-remediation", "Value": "true"},
                        {"Key": "DemoFixture", "Value": "true"},
                        {"Key": "Env", "Value": "demo"}
                    ]
                }
            ]
        )
        alloc_id = eip_res.get("AllocationId")
        pub_ip = eip_res.get("PublicIp")
        planted["eip"].append(alloc_id)
        print(f"      -> SUCCESS: Allocated {alloc_id} ({pub_ip})")
        print(f"         Tags: eligible-for-remediation=true, DemoFixture=true")
    except Exception as e:
        print(f"      -> ERROR allocating Elastic IP: {e}")

    print("\n=======================================================")
    print("  DEMO FIXTURES READY FOR TESTING")
    print("=======================================================")
    print(f"EC2 Instance:    {planted['ec2']}")
    print(f"EBS Volume:      {planted['ebs']}")
    print(f"Elastic IP:      {planted['eip']}")
    print("\nNext step: Run 'ResourceScanner' via dashboard or CLI.")
    print("When done, run 'python scripts/cleanup_demo_fixtures.py' to remove all fixtures immediately.")
    print("=======================================================\n")


if __name__ == "__main__":
    plant_fixtures()
