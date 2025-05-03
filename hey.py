import boto3
from datetime import datetime, timedelta, timezone
import pandas as pd
import json
import botocore
import os

# AWS Clients
cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
ec2 = boto3.client('ec2', region_name='us-east-1')
pricing = boto3.client('pricing', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')

# S3 Bucket Name
S3_BUCKET = 'ansh-cost-reports-2025'

# Fetch CPU Metrics
def get_instance_metrics(instance_id, days=14):
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    response = cloudwatch.get_metric_statistics(
        Namespace='AWS/EC2',
        MetricName='CPUUtilization',
        Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
        StartTime=start_time,
        EndTime=end_time,
        Period=86400,
        Statistics=['Average', 'Maximum'],
        Unit='Percent'
    )

    datapoints = response.get('Datapoints', [])
    if not datapoints:
        return None, None

    avg_util = sum(dp['Average'] for dp in datapoints) / len(datapoints)
    max_util = max(dp['Maximum'] for dp in datapoints)
    return avg_util, max_util

# Get All Running Instances
def get_all_instances():
    response = ec2.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instances.append({
                'InstanceId': instance['InstanceId'],
                'InstanceType': instance['InstanceType'],
                'LaunchTime': instance['LaunchTime'],
                'Tags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
            })
    return instances

# Get On-Demand Price for an Instance Type
def get_instance_type_info(instance_type):
    try:
        response = pricing.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': 'US East (N. Virginia)'},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'}
            ],
            MaxResults=1
        )
        if not response['PriceList']:
            return None

        price_item = json.loads(response['PriceList'][0])
        terms = price_item['terms']['OnDemand']
        term_keys = list(terms.keys())
        price_dimensions = terms[term_keys[0]]['priceDimensions']
        dimension_keys = list(price_dimensions.keys())
        usd_price = price_dimensions[dimension_keys[0]]['pricePerUnit'].get('USD', None)
        return float(usd_price) if usd_price else None

    except Exception as e:
        print(f"Error getting pricing for {instance_type}: {e}")
        return None

# Generate Optimization Recommendations
def get_recommendations(instance, avg_util, max_util):
    recommendations = []
    current_type = instance['InstanceType']

    if max_util < 40:
        recommendations.append(f"Underutilized (Max CPU: {max_util:.1f}%)")
        current_price = get_instance_type_info(current_type)
        family = current_type.split('.')[0]
        potential_types = [f"{family}.large", f"{family}.medium", f"{family}.small"]

        for new_type in potential_types:
            if new_type == current_type:
                continue
            new_price = get_instance_type_info(new_type)
            if new_price and current_price and new_price < current_price:
                savings = current_price - new_price
                savings_percent = (savings / current_price) * 100
                recommendations.append(
                    f"⬇️ Suggest: {new_type} → Save ${savings:.2f}/hr ({savings_percent:.1f}%)"
                )

    if max_util < 10:
        recommendations.append("Consider stopping: appears unused")

    return recommendations

# Upload file to S3
def upload_to_s3(file_name, bucket_name, object_name=None):
    if object_name is None:
        object_name = file_name
    try:
        s3.upload_file(file_name, bucket_name, object_name)
        print(f"✅ Report uploaded to s3://{bucket_name}/{object_name}")
    except botocore.exceptions.ClientError as e:
        print(f"❌ Failed to upload to S3: {e}")

# Shut Down Instances by Name
def shutdown_instances_by_name(names):
    instances_to_stop = []
    all_instances = get_all_instances()
    for instance in all_instances:
        name = instance['Tags'].get('Name', '')
        if name in names:
            instances_to_stop.append(instance['InstanceId'])

    if instances_to_stop:
        print(f" Stopping instances: {instances_to_stop}")
        ec2.stop_instances(InstanceIds=instances_to_stop)
    else:
        print("No matching running instances found.")

# Start Instances by Name
def start_instances_by_name(names):
    instances_to_start = []
    all_instances = ec2.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['stopped']}])['Reservations']
    for reservation in all_instances:
        for instance in reservation['Instances']:
            name = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}.get('Name', '')
            if name in names:
                instances_to_start.append(instance['InstanceId'])

    if instances_to_start:
        print(f" Starting instances: {instances_to_start}")
        ec2.start_instances(InstanceIds=instances_to_start)
    else:
        print("⚠️ No matching stopped instances found.")

# MAIN FUNCTION
def main():
    print("\n AWS EC2 Instance Cost Optimization Tool")
    print("=" * 60)

    instances = get_all_instances()
    print(f"Found {len(instances)} running EC2 instance(s)\n")
    results = []

    for instance in instances:
        instance_id = instance['InstanceId']
        print(f" Analyzing {instance_id}...")

        try:
            avg_util, max_util = get_instance_metrics(instance_id)
            if avg_util is None:
                print(" No metrics found.")
                continue

            recommendations = get_recommendations(instance, avg_util, max_util)

            results.append({
                'Instance ID': instance_id,
                'Name': instance['Tags'].get('Name', ''),
                'Instance Type': instance['InstanceType'],
                'Avg CPU %': round(avg_util, 1),
                'Max CPU %': round(max_util, 1),
                'Recommendations': "\n".join(recommendations) if recommendations else "✅ No recommendations"
            })

        except Exception as e:
            print(f" Error with {instance_id}: {e}")

    df = pd.DataFrame(results)

    if df.empty:
        print("\n No data to export..............")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        file_name = f"aws_cost_optimization_report_{timestamp}.csv"
        full_path = os.path.abspath(file_name)
        df.to_csv(file_name, index=False)

        print("\n📄 Final Report:")
        print(df[['Instance ID', 'Name', 'Instance Type', 'Avg CPU %', 'Max CPU %', 'Recommendations']].to_string(index=False))
        print(f"\n Report saved at: {full_path}")
        upload_to_s3(file_name, S3_BUCKET)

    # Optional Shutdown
    if input("\nDo you want to shut down any instances? (yes/no): ").strip().lower() == 'yes':
        count = int(input("Enter number of instances: "))
        names = [input(f"🔻 Name {i + 1}: ") for i in range(count)]
        shutdown_instances_by_name(names)

    # Optional Start
    if input("\nDo you want to start any stopped instances? (yes/no): ").strip().lower() == 'yes':
        count = int(input("Enter number of instances: "))
        names = [input(f"🔼 Name {i + 1}: ") for i in range(count)]
        start_instances_by_name(names)


if __name__ == "__main__":
    main()
