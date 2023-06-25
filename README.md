# TradingAlgorithms

## Bachelor Thesis ## 
Deployed version: http://trading-algorithms.eu-central-1.elasticbeanstalk.com/

GitHub Link: https://github.com/danielbociat/TradingAlgorithms

GitLab Link: https://gitlab.upt.ro/daniel.bociat/TradingAlgorithms

For local development:

- Firstly an AWS account has to be set up, follow the next steps to correctly configure an account:

1. Create an AWS account and set up the following services: Secrets Manager, DynamoDB, S3
    Note: to run the system locally Elastic Beanstalk and CodePipeline are not used
        and ElastiCache is not working locally as it requires the user to be part of the AWS VPC
2. Configure the user by running 'aws configure' in the AWS CLI
3. Add the permissions for the services mentioned above to the user by using AWS IAM
4. Add the account region in the 'config.ini' file
5. For Secrets Manager create a secret called 'jwt_secret_key' where the JWT secret key is added
6. For Secrets Manager create a second secret called 'credential' using plaintext in the format:
    {"credentials" : {"username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}}, 'YOUR_USERNAME' and 'YOUR_PASSWORD' may
    be replaced with credentials of your choosing.
7. For DynamoDB create a Table with the partition key: 'algorithm' and sort key: 'timestamp'
8. Add the DynamoDB Table name in the 'config.ini' file
9. Create a public S3 bucket with the following policy and replace 'BUCKET_NAME' with your bucket value:
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::BUCKET_NAME/*"
            ]
        }
    ]
}
```

10. Add the S3 Bucket name in the 'config.ini' file


- To start the application locally:

1. Install the Python packages found in requirements.txt by using "pip install -r requirements.txt"
    Note: Use Python 3.8 or newer

2. Run the application.py file, either using a command "py application.py", either directly from the IDE (PyCharm was used for development)

3. To access the Swagger UI open the browser to "http://localhost:5000/", or by clicking the link received in the terminal
