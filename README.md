# EC2 Cost Optimization and Auto Shutdown

This project automates the cost optimization of EC2 instances by analyzing CPU utilization and shutting down instances that remain idle. It uses AWS Lambda to run Python logic serverlessly, triggered manually or on a daily schedule using Amazon CloudWatch.

## Project Overview

This serverless solution leverages the following AWS services:

- *Amazon S3* – Storage for Python script and optional input data
- *AWS Lambda* – Executes the EC2 monitoring and shutdown logic
- *AWS IAM* – Manages permissions for Lambda
- *Amazon CloudWatch* – Schedules the Lambda function and stores logs
- *Amazon Ec2* -For the instances.

---

## Setup Instructions

### 1. Create an S3 Bucket

1. Go to the *AWS S3 Console* → *Create bucket*
2. Name your bucket (e.g., my-data-analysis-bucket)
3. Click *Create bucket*
4. Upload the following files:
   - lambda_function_py.py (Python script)
   - aws_cost_optimization_report.csv (if needed)

---

### 2. Set Up IAM Role

1. Go to the *IAM Console* → *Roles* → *Create Role*
2. Choose *Lambda* as the use case
3. Attach the following policies:
   - AWSLambdaBasicExecutionRole
   - AmazonEC2ReadOnlyAccess
   - AmazonS3ReadOnlyAccess (if your script reads from S3)
4. Name the role: LambdaExecutionRole
5. Create the role

---

### 3. Deploy Lambda Function

1. Go to the *Lambda Console* → *Create function*
2. Name your function: EC2Optimizer
3. Choose *Python 3.9* as the runtime
4. Assign the IAM role LambdaExecutionRole
5. Paste the code from lambda_function_py.py into the editor
6. Click *Deploy*

---

### 4. Test the Function

1. In the Lambda function console, click *Test*
2. Configure a test event (use the default settings)
3. Run the test

---

### 5. Schedule Daily Execution (Optional)

1. In the Lambda console, go to *Add trigger*
2. Choose *EventBridge (CloudWatch Events)*
3. Create a new rule:
   - Rule Type: *Schedule*
   - Cron expression: cron(0 18 * * ? *) (runs daily at 6 PM UTC)

---

## Monitoring & Logs

- View logs via *Amazon CloudWatch*
  - Navigate to: /aws/lambda/EC2Optimizer
- Confirm whether idle EC2 instances were stopped successfully

---

## Cleanup

To avoid unexpected charges:
- Delete the Lambda function if unused
- Delete the S3 bucket and contents

---

## Troubleshooting

- *Permission Denied*: Check IAM role policies
- *No Data Returned: Ensure EC2 instances have **detailed monitoring* enabled

---

## License

This project is released for educational and personal AWS optimization use. Use responsibly and monitor billing.

---

## Author

*Ansh Negi*
