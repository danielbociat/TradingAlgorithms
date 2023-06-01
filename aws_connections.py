import configparser
import json

import boto3
from botocore.exceptions import ClientError
from elasticache_pyclient import MemcacheClient

config = configparser.RawConfigParser()
config.read('config.ini')
aws_connections_config = dict(config.items('aws_connections'))


session = boto3.session.Session()

REGION_NAME = aws_connections_config.get("region_name")
BUCKET_NAME = aws_connections_config.get("bucket_name")
DYNAMODB_RUNS_TABLE_NAME = aws_connections_config.get("dynamodb_runs_table_name")
MEMCACHED_URL = aws_connections_config.get("memcached_url")


def get_memcached_connection(url):
    connection = None
    try:
        connection = MemcacheClient(url)
    except Exception:
        pass
    return connection


def get_secrets_manager_connection():
    secrets_manager = session.client(
        service_name='secretsmanager',
        region_name=REGION_NAME
    )
    return secrets_manager


def get_secret_from_secrets_manager(secrets_manager, key):
    try:
        get_secret_value_response = secrets_manager.get_secret_value(
            SecretId=key
        )
    except ClientError as e:
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response['SecretString']
    secrets = json.loads(secret)
    return secrets[key]


def get_dynamodb_connection():
    dynamodb = boto3.resource(
        service_name='dynamodb',
        region_name=REGION_NAME
    )
    return dynamodb


def get_dynamodb_table(dynamodb, table_name):
    table = dynamodb.Table(table_name)
    return table


def get_s3_connection():
    s3 = boto3.client('s3')
    return s3


def put_s3_item(s3, name, item, content_type):
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f'{name}',
        Body=item,
        ContentType=content_type
    )


def get_s3_bucket_item_link(name):
    return "https://" + BUCKET_NAME + ".s3." + REGION_NAME + ".amazonaws.com/" + name
