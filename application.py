import aws_connections
from trading_algorithms import *

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
import pandas as pd
from datetime import timedelta
from boto3.dynamodb.conditions import Key, Attr
import json

pd.options.mode.chained_assignment = None  # default='warn'


dynamodb = aws_connections.get_dynamodb_connection()
table = aws_connections.get_dynamodb_table(dynamodb, aws_connections.DYNAMODB_RUNS_TABLE_NAME)
memcache = aws_connections.get_memcached_connection(aws_connections.MEMCACHED_URL)
secrets_manager = aws_connections.get_secrets_manager_connection()
s3 = aws_connections.get_s3_connection()


# Application
application = Flask(__name__)
application.config["JWT_SECRET_KEY"] = aws_connections.get_secret_from_secrets_manager(secrets_manager, "jwt_secret_key")
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
        ticker_data = memcache.get(key)

    if ticker_data is None:
        ticker_data = yf.download(ticker, period=period, interval=interval)

        if memcache is not None:
            memcache.set(key, ticker_data, 3 * 60 * 60)

    return ticker_data


@application.before_request
def before():
    if request.headers.get("content_type") == "application/json":
        print(request.json)


@application.route('/auth', methods=['POST'])
def auth():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    # TODO - Add auth logic / maybe aws user account
    if not (username == "test" and password == "test"):
        return jsonify({"msg": "Invalid username or password"}), 401

    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token)


# TODO: Remove this
@application.route('/', methods=['GET', 'POST'])
def home():
    try:
        ticker = "AAPL"
        period = "12mo"
        interval = "1d"

        ticker_data = get_financial_data(ticker, period, interval)

        arbitrage_data = get_financial_data("IVV", period, interval)

        alg = DoubleRSI(ticker_data)

        alg.run_algorithm()

        alg.save_chart_html()

        print("SIMULATION STATS")
        print(alg.simulation_stats)
    except Exception as e:
        print(e)

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


# TODO - Add simulation stats to dynamo db
# TODO - Add custom messages for failing situations
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
            rsi_short_period = data.get("rsi_short_period", 14)
            rsi_long_period = data.get("rsi_long_period", 28)

            alg = DoubleRSI(ticker_data, rsi_short_period, rsi_long_period)

        elif algorithm == "mean_reversion":
            time_window = data.get("time_window", 20)

            alg = MeanReversion(ticker_data, time_window)

        elif algorithm == "arbitrage":
            entry_threshold = data.get("entry_threshold", 2)
            exit_threshold = data.get("exit_threshold", 0)

            ticker2 = data.get("ticker2", "SPY")
            arbitrage_data = get_financial_data(ticker2, period, interval)
            alg = Arbitrage(ticker_data, arbitrage_data, entry_threshold, exit_threshold)

        else:
            return "The selected algorithm does not exist", 400

        alg.run_algorithm()

        chart_name = ''.join(random.sample(string.ascii_letters + string.digits, 16))
        str_obj = StringIO()
        alg.chart.write_html(str_obj, 'html')
        buf = str_obj.getvalue().encode()
        aws_connections.put_s3_item(s3, chart_name, buf, 'text/html')

        # TODO : Add alg.statistics to the Item
        table.put_item(
            TableName=aws_connections.DYNAMODB_RUNS_TABLE_NAME,
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

    print(alg.simulation_stats)

    return "Successful simulation\n See the trading chart at " + aws_connections.get_s3_bucket_item_link(chart_name), 200


# TODO : Add endpoints for statistics => look into dynamodb queries
@application.route('/statistics', methods=["GET"])
@jwt_required()
def statistics():
    return "", 404


# TODO - add benchmark endpoint
@application.route('/benchmark', methods=["POST"])
@jwt_required()
def benchmark():
    return "", 404


if __name__ == "__main__":
    application.run(debug=True)
