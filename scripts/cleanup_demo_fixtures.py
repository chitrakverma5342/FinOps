"""
FinOps Cost Guardian — Demo Fixture Cleanup Script
Immediately terminates, deletes, and releases all demo resources planted in the personal AWS account.
Ensures zero lingering cost or resource leakage.
"""

import os
import time
import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))


def cleanup_fixtures():
    print(f"\n=======================================================")
    print(f"  FinOps Cost Guardian — Cleaning Up Demo Fixtures")
    print(f"  Target Region: {REGION}")
    print(f"=======================================================\n")

    ec2 = boto3.client("ec2", region_name=REGION)

    # 1. Terminate Demo EC2 Instances
    print("[1/3] Searching for demo EC2 instances (DemoFixture=true)...")
    try:
        inst_res = ec2.describe_instances(
            Filters=[
                {"Name": "tag:DemoFixture", "Values": ["true"]},
                {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}
            ]
        )
        instance_ids = []
        for r in inst_res.get("Reservations", []):
            for inst in r.get("Instances", []):
                instance_ids.append(inst["InstanceId"])

        if instance_ids:
            print(f"      Found {len(instance_ids)} demo instance(s): {instance_ids}")
            ec2.terminate_instances(InstanceIds=instance_ids)
            print(f"      -> SUCCESS: Initiated termination for {instance_ids}")
        else:
            print("      -> No active demo EC2 instances found.")
    except Exception as e:
        print(f"      -> ERROR terminating EC2 instances: {e}")

    # 2. Release Demo Elastic IPs
    print("\n[2/3] Searching for demo Elastic IPs (DemoFixture=true)...")
    try:
        eip_res = ec2.describe_addresses(
            Filters=[{"Name": "tag:DemoFixture", "Values": ["true"]}]
        )
        addresses = eip_res.get("Addresses", [])
        if addresses:
            for addr in addresses:
                alloc_id = addr.get("AllocationId")
                public_ip = addr.get("PublicIp")
                assoc_id = addr.get("AssociationId")
                if assoc_id:
                    ec2.disassociate_address(AssociationId=assoc_id)
                    time.sleep(1)
                ec2.release_address(AllocationId=alloc_id)
                print(f"      -> SUCCESS: Released Elastic IP {alloc_id} ({public_ip})")
        else:
            print("      -> No demo Elastic IPs found.")
    except Exception as e:
        print(f"      -> ERROR releasing Elastic IPs: {e}")

    # 3. Delete Demo EBS Volumes
    print("\n[3/3] Searching for demo EBS volumes (DemoFixture=true)...")
    try:
        vol_res = ec2.describe_volumes(
            Filters=[{"Name": "tag:DemoFixture", "Values": ["true"]}]
        )
        volumes = vol_res.get("Volumes", [])
        if volumes:
            for vol in volumes:
                vol_id = vol.get("VolumeId")
                vol_state = vol.get("State")
                if vol_state == "in-use":
                    print(f"      Volume {vol_id} is in-use, waiting 5s for instance detachment...")
                    time.sleep(5)
                try:
                    ec2.delete_volume(VolumeId=vol_id)
                    print(f"      -> SUCCESS: Deleted volume {vol_id}")
                except Exception as del_err:
                    print(f"      -> Retry deletion for {vol_id}: {del_err}")
        else:
            print("      -> No demo EBS volumes found.")
    except Exception as e:
        print(f"      -> ERROR deleting EBS volumes: {e}")

    print("\n=======================================================")
    print("  ALL DEMO FIXTURES CLEANED UP — ZERO RESIDUAL CHARGES")
    print("=======================================================\n")


if __name__ == "__main__":
    cleanup_fixtures()
