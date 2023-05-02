import yfinance as yf
from flask import Flask, jsonify, request
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token, get_jwt_identity
)
import configparser
from trading_algorithms import *
import pandas as pd
from datetime import timedelta
import boto3
from botocore.exceptions import ClientError
import json
pd.options.mode.chained_assignment = None  # default='warn'

'''
config = configparser.RawConfigParser()
config.read('config.ini')
api_dict = dict(config.items('historical_data_api_key'))
'''


def get_secret(key):
    secret_name = "jwt_secret_key"
    region_name = "eu-central-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response['SecretString']
    secrets = json.loads(secret)
    return secrets[key]


application = Flask(__name__)
application.config["JWT_SECRET_KEY"] = get_secret("jwt_secret_key")
application.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(application)


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
@jwt_required()
def home():
    return "Hello World!"


# TODO - add all the configuration details: algorithms, tickers, periods and intervals
@application.route('/configuration', methods=["GET"])
@jwt_required()
def get_algorithms():
    return jsonify(
        algorithm=['double_rsi', 'mean_reversal', 'arbitrage'],
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

        algorithm = data["algorithm"]

        if algorithm == "double_rsi":
            alg = DoubleRSI(ticker_data)
            alg.run_algorithm()
#           alg.save_chart_html()
        elif algorithm == "mean_reversal":
            alg = MeanReversal(ticker_data)
            alg.run_algorithm()
#           alg.save_chart_html()
        elif algorithm == "arbitrage":
            alg = Arbitrage(ticker_data)
        else:
            return "Wrong data sent in body", 400

    except Exception as e:
        print(e)
        return "Wrong data sent in body", 400

    return "Successful simulation", 200


# TODO - complete benchmark endpoint
@application.route('/benchmark', methods=["POST"])
@jwt_required()
def benchmark():
    return "", 404


if __name__ == "__main__":
    application.run(debug=True)