from flask import Flask, jsonify, request, redirect, Blueprint
from flask_jwt_extended import (
    create_access_token, JWTManager, jwt_required
)
from trading_algorithms import *
import aws_connections
import datetime
import random
import string
from datetime import timedelta
from io import StringIO

# region Auth

AUTH = Blueprint('auth', __name__)


@AUTH.route('/auth', methods=['POST'])
def auth():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    credentials = aws_connections.get_secret_from_secrets_manager(aws_connections.SECRETS_MANAGER, "credentials")

    if not (username == credentials["username"] and password == credentials["password"]):
        return jsonify({"msg": "Invalid username or password"}), 401

    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token)


# endregion

# region Home and Config


MISC = Blueprint('misc', __name__)


@MISC.route('/', methods=['GET', 'POST'])
def home():
    return redirect('/swagger')


# TODO - add all the configuration details: algorithms, tickers, periods and intervals
@MISC.route('/configuration', methods=["GET"])
@jwt_required()
def get_algorithms():
    return jsonify(
        algorithm=['double_rsi', 'mean_reversion', 'arbitrage'],
        period=['12mo'],
        interval=['1d']
    ), 200


# endregion

# region Algorithms

def get_financial_data(ticker, period, interval):
    key = ticker + period + interval
    ticker_data = None

    if aws_connections.MEMCACHE is not None:
        ticker_data = aws_connections.MEMCACHE.get(key)

    if ticker_data is None:
        ticker_data = yf.download(ticker, period=period, interval=interval)

        if aws_connections.MEMCACHE is not None:
            aws_connections.MEMCACHE.set(key, ticker_data, 12 * 60 * 60)

    return ticker_data


ALGO = Blueprint('algo', __name__)


# TODO - Add simulation stats to dynamo db
# TODO - Add custom messages for failing situations
@ALGO.route('/simulate', methods=["POST"])
# @jwt_required()
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

            alg = DoubleRSI(ticker_data, period, interval, rsi_short_period, rsi_long_period)

        elif algorithm == "mean_reversion":
            time_window = data.get("time_window", 20)

            alg = MeanReversion(ticker_data, period, interval, time_window)

        elif algorithm == "arbitrage":
            entry_threshold = data.get("entry_threshold", 2)
            exit_threshold = data.get("exit_threshold", 0)

            ticker2 = data.get("ticker2", "SPY")
            arbitrage_data = get_financial_data(ticker2, period, interval)
            alg = Arbitrage(ticker_data, period, interval, arbitrage_data, entry_threshold, exit_threshold)

        else:
            return "The selected algorithm does not exist", 400

        alg.run_algorithm()

        chart_name = ''.join(random.sample(string.ascii_letters + string.digits, 16))
        str_obj = StringIO()
        alg.chart.write_html(str_obj, 'html')
        buf = str_obj.getvalue().encode()
        aws_connections.put_s3_item(aws_connections.S3, chart_name, buf, 'text/html')

        # TODO : Add alg.statistics to the Item
        aws_connections.DYNAMODB_TABLE.put_item(
            TableName=aws_connections.DYNAMODB_RUNS_TABLE_NAME,
            Item={
                'timestamp_period': "".join([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), '_', period]),
                'algorithm': algorithm,
                'ticker': ticker,
                'period': period,
                'interval': interval,
            }
        )
    except Exception as e:
        print(e)
        return "Simulation failed", 400

    print("SIMULATION STATS")
    print(alg.simulation_stats)

    return "Successful simulation\n See the trading chart at " + aws_connections.get_s3_bucket_item_link(
        chart_name), 200


# endregion


# region statistics

STATS = Blueprint('stats', __name__)


# TODO : Add endpoints for statistics => look into dynamodb queries
@STATS.route('/statistics', methods=["GET"])
@jwt_required()
def statistics():
    return "", 404

# endregion
