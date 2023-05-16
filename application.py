import string
from io import StringIO
import yfinance as yf
from flask import Flask, jsonify, request
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token
)
import random
import datetime
from flask_swagger_ui import get_swaggerui_blueprint
import configparser
from trading_algorithms import *
import pandas as pd
from datetime import timedelta
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import json
from elasticache_pyclient import MemcacheClient

pd.options.mode.chained_assignment = None  # default='warn'

'''
config = configparser.RawConfigParser()
config.read('config.ini')
api_dict = dict(config.items('historical_data_api_key'))
'''


def connect_to_memcache(url):
    connection = None
    try:
        connection = MemcacheClient(url)
    except Exception:
        pass
    return connection


region_name = "eu-central-1"
session = boto3.session.Session()

secrets_manager = session.client(
    service_name='secretsmanager',
    region_name=region_name
)

dynamodb = boto3.resource(
    service_name='dynamodb',
    region_name=region_name
)
table = dynamodb.Table("TradingAlgorithmsRuns")

memcache = connect_to_memcache('tradingalgortihmsmemcache.lwtvyq.0001.euc1.cache.amazonaws.com:11211')

s3 = boto3.client('s3')
BUCKET_NAME = "tradingalgorithmscharts"


def get_chart_link(chart_name):
    return "https://" + BUCKET_NAME + ".s3.eu-central-1.amazonaws.com/" + chart_name


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


# Application
application = Flask(__name__)
application.config["JWT_SECRET_KEY"] = get_secret("jwt_secret_key")
application.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(application)

SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.yaml'
SWAGGER_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Trading Algorithms"
    }
)

application.register_blueprint(SWAGGER_BLUEPRINT, url_prefix=SWAGGER_URL)


def get_financial_data(ticker, period, interval):
    key = ticker + period + interval
    ticker_data = None

    if memcache is not None:
        memcache.set(key, ticker_data, 1)
        ticker_data = memcache.get(key)

    if ticker_data is None:
        ticker_data = yf.download(ticker, period=period, interval=interval)

        if memcache is not None:
            memcache.set(key, ticker_data, 3*60*60)

    return ticker_data


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


@application.route('/', methods=['GET', 'POST'])
def home():
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

        ticker_data = get_financial_data(ticker, period, interval)

        algorithm = data.get("algorithm", "")

        if algorithm == "double_rsi":
            alg = DoubleRSI(ticker_data)
        elif algorithm == "mean_reversion":
            alg = MeanReversion(ticker_data)
        elif algorithm == "arbitrage":
            alg = Arbitrage(ticker_data, ticker_data)
        else:
            return "The algorithm selected does not exist", 400

        alg.run_algorithm()

        chart_name = ''.join(random.sample(string.ascii_letters + string.digits, 16))

        str_obj = StringIO()  # instantiate in-memory string object
        alg.chart.write_html(str_obj, 'html')  # saving to memory string object
        buf = str_obj.getvalue().encode()  # convert in-memory string to bytes
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f'{chart_name}',
            Body=buf,
            ContentType='text/html'
        )

        table.put_item(
            TableName="TradingAlgorithmsRuns",
            Item={
                'timestamp_period': "".join([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), '_', period]),
                'algorithm': algorithm,
                'ticker': ticker,
                'period': period,
                'interval': interval,
            }
        )

    except Exception:
        return "Simulation failed", 400

    return "Successful simulation\n See the trading chart at " + get_chart_link(chart_name), 200


@application.route('/statistics', methods=["GET"])
@jwt_required()
def statistics():
    return "", 404


# TODO - complete benchmark endpoint
@application.route('/benchmark', methods=["POST"])
@jwt_required()
def benchmark():
    return "", 404


if __name__ == "__main__":
    application.run(debug=True)
