import datetime
import json
import random
import string
from collections import defaultdict
from decimal import Decimal
from io import StringIO
import statistics
from boto3.dynamodb.conditions import Key
from flask import jsonify, request, redirect, Blueprint
from flask_jwt_extended import (
    create_access_token, jwt_required
)

import aws_connections
from trading_algorithms import *

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
        algorithm_parameters = dict()

        data = dict(request.json)

        ticker = data.get("ticker", "AAPL")
        period = data.get("period", "12mo")
        interval = data.get("interval", "1d")

        ticker_data = get_financial_data(ticker, period, interval)

        algorithm = data.get("algorithm", "")

        if algorithm == "double_rsi":
            rsi_short_period = data.get("rsi_short_period", 14)
            rsi_long_period = data.get("rsi_long_period", 28)

            algorithm_parameters["rsi_short_period"] = rsi_short_period
            algorithm_parameters["rsi_long_period"] = rsi_long_period

            alg = DoubleRSI(ticker_data, period, interval, rsi_short_period, rsi_long_period)

        elif algorithm == "mean_reversion":
            time_window = data.get("time_window", 20)

            algorithm_parameters["time_window"] = time_window

            alg = MeanReversion(ticker_data, period, interval, time_window)

        elif algorithm == "arbitrage":
            entry_threshold = data.get("entry_threshold", 2)
            exit_threshold = data.get("exit_threshold", 0)
            ticker2 = data.get("ticker2", "SPY")

            algorithm_parameters["entry_threshold"] = entry_threshold
            algorithm_parameters["exit_threshold"] = exit_threshold
            algorithm_parameters["ticker2"] = ticker2

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

        dynamodb_item = {
                            'timestamp_period': "".join(
                                [datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), '_', period]),
                            'algorithm': algorithm,
                            'ticker': ticker,
                            'period': period,
                            'interval': interval,
                        } | alg.simulation_stats | algorithm_parameters

        dynamodb_item = json.loads(json.dumps(dynamodb_item), parse_float=Decimal)

        aws_connections.DYNAMODB_TABLE.put_item(
            TableName=aws_connections.DYNAMODB_RUNS_TABLE_NAME,
            Item=dynamodb_item
        )

    except Exception as e:
        print(e)
        return "Simulation failed", 400

    print("SIMULATION STATS")
    print(dynamodb_item)

    return "Successful simulation\n See the trading chart at " + aws_connections.get_s3_bucket_item_link(
        chart_name), 200


# endregion


# region statistics

def get_most_used(key, items):
    freq = defaultdict(lambda: 0)

    for item in items:
        if key in item:
            freq[item[key]] += 1

    return max(freq, key=freq.get)


def get_average(key, items):
    getAllElementsWithSameKey = lambda k: [d for d in items if k in d]
    filtered = [d[key] for d in getAllElementsWithSameKey(key)]

    if len(filtered) == 0:
        return 0

    return sum(filtered) / len(filtered)


def get_most_popular_config(algorithm, items):
    most_popular_config = dict()

    if algorithm == "mean_reversion":
        most_popular_config["time_window"] = get_most_used("time_window", items)
    elif algorithm == "double_rsi":
        most_popular_config["rsi_long_period"] = get_most_used("rsi_long_period", items)
        most_popular_config["rsi_short_period"] = get_most_used("rsi_short_period", items)
    elif algorithm == "arbitrage":
        most_popular_config["entry_threshold"] = get_most_used("entry_threshold", items)
        most_popular_config["exit_threshold"] = get_most_used("exit_threshold", items)
        most_popular_config["ticker2"] = get_most_used("ticker2", items)

    return most_popular_config


STATS = Blueprint('stats', __name__, url_prefix='/stats')


# TODO : Add endpoints for statistics => look into dynamodb queries
@STATS.route('/algorithm/<algorithm>', methods=["GET"])
# @jwt_required()
def statistics(algorithm):
    response = aws_connections.DYNAMODB_TABLE.query(
        IndexName='algorithm-index',
        KeyConditionExpression=Key('algorithm').eq(algorithm)
    )

    items = response["Items"]

    if len(items) == 0:
        return "No runs available for algorithm " + algorithm, 400

    stats = dict()
    stats["Most Profitable Run"] = max(items, key=(lambda item: float(item.get('Strategy Result', -9999999))))
    stats["Least Profitable Run"] = min(items, key=(lambda item: float(item.get('Strategy Result', 9999999))))

    stats["Most Popular Configuration"] = get_most_popular_config(algorithm, items)

    stats["Most Used Ticker"] = get_most_used('ticker', items)
    stats["Most Used Period"] = get_most_used('period', items)
    stats["Most Used Interval"] = get_most_used('interval', items)

    stats["Average Strategy Return"] = get_average("Strategy Result", items)

    return jsonify(stats), 200

# endregion
