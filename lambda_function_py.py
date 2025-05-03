import boto3
from datetime import datetime, timedelta, timezone

ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    print("🔍 Checking running EC2 instances...")
    reservations = ec2.describe_instances(Filters=[
        {'Name': 'instance-state-name', 'Values': ['running']}
    ])['Reservations']

    for res in reservations:
        for inst in res['Instances']:
            instance_id = inst['InstanceId']
            print(f"⏳ Checking {instance_id}...")

            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=20)

            metrics = cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average']
            )

            datapoints = metrics.get('Datapoints', [])
            if datapoints:
                avg_cpu = sum(dp['Average'] for dp in datapoints) / len(datapoints)
                print(f"→ {instance_id} Avg CPU: {avg_cpu:.2f}%")
                if avg_cpu < 1:
                    print(f"🛑 Stopping {instance_id} due to inactivity...")
                    ec2.stop_instances(InstanceIds=[instance_id])
