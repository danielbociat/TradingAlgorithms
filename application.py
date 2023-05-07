import yfinance as yf
from flask import Flask, jsonify, request
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token, get_jwt_identity
)
import uuid
from flask_swagger_ui import get_swaggerui_blueprint
import configparser
from trading_algorithms import *
import pandas as pd
from datetime import timedelta
import boto3
from botocore.exceptions import ClientError
import json
import amazondax

pd.options.mode.chained_assignment = None  # default='warn'

'''
config = configparser.RawConfigParser()
config.read('config.ini')
api_dict = dict(config.items('historical_data_api_key'))
'''

region_name = "eu-central-1"
session = boto3.session.Session()

secrets_manager = session.client(
    service_name='secretsmanager',
    region_name=region_name
)

dynamodb = boto3.client(
    service_name='dynamodb',
    region_name=region_name
)

dax = amazondax.AmazonDaxClient.resource(
    endpoint_url='daxs://tradingalgorithmsdax.lwtvyq.dax-clusters.eu-central-1.amazonaws.com',
    region_name=region_name
)


def get_secret(key):
    secret_name = "jwt_secret_key"

    try:
        get_secret_value_response = secrets_manager.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response['SecretString']
    secrets = json.loads(secret)
    return secrets[key]


application = Flask(__name__)
application.config["JWT_SECRET_KEY"] = get_secret("jwt_secret_key")
application.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(application)

'''
SWAGGER_URL = '/api/docs'
API_URL = 'trading-algorithms.eu-central-1.elasticbeanstalk.com'

swagger_ui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
    API_URL,
    config={  # Swagger UI config overrides
        'app_name': "Test application"
    },
    # oauth_config={  # OAuth config. See https://github.com/swagger-api/swagger-ui#oauth2-configuration .
    #    'clientId': "your-client-id",
    #    'clientSecret': "your-client-secret-if-required",
    #    'realm': "your-realms",
    #    'appName': "your-app-name",
    #    'scopeSeparator': " ",
    #    'additionalQueryStringParams': {'test': "hello"}
    # }
)

application.register_blueprint(swagger_ui_blueprint)
'''


@application.before_request
def before():
    if request.headers.get("content_type") == "application/json":
        print(request.json)


@application.route('/auth', methods=['POST'])
def auth():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    # TODO - Add auth logic
    if not (username == "test" and password == "test"):
        return jsonify({"msg": "Invalid username or password"}), 401

    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token)


@application.route('/home', methods=['GET', 'POST'])
def home():
    try:
        dax.put_item(
            TableName="DataCache",
            Item={
                'ticker_period_interval': {'S': "SHOULD DISSAPEAR"},
                'algorithm': {'S': "AAAAAAAAAAAAA"},
            }
        )

        rsp = dax.get_item(
            TableName="DataCache",
            Key={
                'ticker_period_interval': {'S': "SHOULD DISSAPEAR"}
            }
        )

    except Exception as e:
        print(e)
        raise e

    return 'Hello'


# TODO - add all the configuration details: algorithms, tickers, periods and intervals
@application.route('/configuration', methods=["GET"])
@jwt_required()
def get_algorithms():
    return jsonify(
        algorithm=['double_rsi', 'mean_reversion', 'arbitrage'],
        period=['12mo'],
        interval=['1d']
    ), 200


# TODO - complete simulation endpoint
@application.route('/simulate', methods=["POST"])
@jwt_required()
def simulate():
    try:
        data = dict(request.json)

        ticker = data.get("ticker", "AAPL")
        period = data.get("period", "12mo")
        interval = data.get("interval", "1d")

        ticker_data = yf.download(ticker, period=period, interval=interval)

        algorithm = data.get("algorithm", "")

        if algorithm == "double_rsi":
            alg = DoubleRSI(ticker_data)
        elif algorithm == "mean_reversion":
            alg = MeanReversion(ticker_data)
        elif algorithm == "arbitrage":
            alg = Arbitrage(ticker_data)
        else:
            return "The algorithm selected does not exist", 400

        alg.run_algorithm()

        dynamodb.put_item(
            TableName="TradingAlgorithmsRun",
            Item={
                'run_id': {'S': str(uuid.uuid1())},
                'algorithm': {'S': algorithm},
                'ticker': {'S': ticker},
                'period': {'S': period},
                'interval': {'S': interval},
            }
        )

    except Exception as e:
        raise e
        return "FAIL", 400

    return "Successful simulation", 200


# TODO - complete benchmark endpoint
@application.route('/benchmark', methods=["POST"])
@jwt_required()
def benchmark():
    return "", 404


if __name__ == "__main__":
    application.run(debug=True)