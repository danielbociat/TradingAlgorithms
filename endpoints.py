import datetime
import json
import random
import string
from collections import defaultdict
from decimal import Decimal
from io import StringIO
from boto3.dynamodb.conditions import Key
from flask import jsonify, request, redirect, Blueprint
from flask_jwt_extended import (
    create_access_token, jwt_required
)
from flask_swagger_ui import get_swaggerui_blueprint

import aws_connections
from trading_algorithms import *

# region Constants

PERIODS = ['1d', '5d', '1mo', '3mo', '6mo', '12mo', '1y', '2y', '5y', '10y', 'ytd', 'max']
INTERVALS = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo']
ALGORITHMS = ['double_rsi', 'mean_reversion', 'arbitrage']
CHECK_CONFIG = "\nCheck the /configuration endpoint to see the available configurations"
CONFIG_NOTES = "1m data is only for available for last 7 days, and data interval <1d for the last 60 days"
# endregion

# region Swagger

SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.yaml'
SWAGGER_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Trading Algorithms"
    }
)

# endregion

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


@MISC.route('/configuration', methods=["GET"])
@jwt_required()
def get_algorithms():
    return jsonify(
        algorithm=ALGORITHMS,
        period=PERIODS,
        interval=INTERVALS,
        notes=CONFIG_NOTES
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


def gen_random_string():
    return ''.join(random.sample(string.ascii_letters + string.digits, 16))


ALGO = Blueprint('algo', __name__)


@ALGO.route('/simulate', methods=["POST"])
@jwt_required()
def simulate():
    try:
        algorithm_parameters = dict()
        data = dict(request.json)
        ticker = data.get("ticker", "AAPL")
        period = data.get("period", "12mo")

        if period not in PERIODS:
            return "The selected period is incorrect" + CHECK_CONFIG, 400

        interval = data.get("interval", "1d")

        if interval not in interval:
            return "The selected interval is incorrect" + CHECK_CONFIG, 400

        ticker_data = get_financial_data(ticker, period, interval)

        if ticker_data.empty:
            return "The ticker {ticker} does not exist or has been removed or the period/interval is invalid".format(ticker=ticker) + CHECK_CONFIG, 400

        algorithm = data.get("algorithm", "")

        if algorithm not in ALGORITHMS:
            return "The selected algorithm does not exist" + CHECK_CONFIG, 400

        benchmark_data = get_financial_data("SPY", period, interval)

        alg = None

        if algorithm == "double_rsi":
            rsi_short_period = data.get("rsi_short_period", 14)
            rsi_long_period = data.get("rsi_long_period", 28)

            if not (type(rsi_long_period) is int and type(rsi_long_period) is int):
                return "The RSI periods must be positive integers", 400

            if not (rsi_long_period > 0 and rsi_long_period > 0):
                return "The RSI periods must be positive integers", 400

            algorithm_parameters["rsi_short_period"] = rsi_short_period
            algorithm_parameters["rsi_long_period"] = rsi_long_period

            alg = DoubleRSI(ticker_data, ticker, period, interval, benchmark_data, rsi_short_period, rsi_long_period)

        elif algorithm == "mean_reversion":
            time_window = data.get("time_window", 20)

            if not (type(time_window) is int):
                return "The time window must be strictly positive integer", 400

            if time_window <= 0:
                return "The time window must be strictly positive integer", 400

            algorithm_parameters["time_window"] = time_window

            alg = MeanReversion(ticker_data, ticker, period, interval, benchmark_data, time_window)

        elif algorithm == "arbitrage":
            entry_threshold = data.get("entry_threshold", 2)
            exit_threshold = data.get("exit_threshold", 0)

            if not ((type(entry_threshold) is int or type(entry_threshold) is float) and (type(exit_threshold) is int or type(exit_threshold) is float)):
                return "The entry_threshold and exit_threshold must be non-negative numbers", 400

            if entry_threshold < 0 or exit_threshold < 0:
                return "The entry_threshold and exit_threshold must be non-negative numbers", 400

            ticker2 = data.get("ticker2", "SPY")

            algorithm_parameters["entry_threshold"] = entry_threshold
            algorithm_parameters["exit_threshold"] = exit_threshold
            algorithm_parameters["ticker2"] = ticker2

            arbitrage_data = get_financial_data(ticker2, period, interval)

            if arbitrage_data.empty:
                return "The ticker {ticker} does not exist or has been removed".format(ticker=ticker2), 400

            alg = Arbitrage(ticker_data, ticker, period, interval, benchmark_data, arbitrage_data, ticker2, entry_threshold,
                            exit_threshold)

        if alg is None:
            return "The has been an error, check the configuration", 400

        alg.run_algorithm()

        chart_name = gen_random_string()
        str_obj = StringIO()
        alg.trading_chart.write_html(str_obj, 'html')
        buf = str_obj.getvalue().encode()
        aws_connections.put_s3_item(aws_connections.S3, chart_name, buf, 'text/html')

        portfolio_chart_name = gen_random_string()
        str_obj = StringIO()
        alg.progress_chart.write_html(str_obj, 'html')
        buf = str_obj.getvalue().encode()
        aws_connections.put_s3_item(aws_connections.S3, portfolio_chart_name, buf, 'text/html')

        dynamodb_item = dict()
        dynamodb_item.update({
            'algorithm': algorithm,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'ticker': ticker,
            'period': period,
            'interval': interval,
        })
        dynamodb_item.update(alg.simulation_stats)
        dynamodb_item.update(algorithm_parameters)

        dynamodb_item = json.loads(json.dumps(dynamodb_item), parse_float=Decimal)

        aws_connections.DYNAMODB_TABLE.put_item(
            TableName=aws_connections.DYNAMODB_RUNS_TABLE_NAME,
            Item=dynamodb_item
        )

    except Exception as e:
        print(e)
        return jsonify(e), 400

    response = dict()
    response.update(alg.simulation_stats)
    response['trading_chart'] = aws_connections.get_s3_bucket_item_link(chart_name)
    response['portfolio_evolution'] = aws_connections.get_s3_bucket_item_link(portfolio_chart_name)
    return jsonify(response), 200


# endregion


# region statistics

def get_most_used(key, items):
    freq = defaultdict(lambda: 0)

    for item in items:
        if key in item:
            freq[item[key]] += 1

    return max(freq, key=freq.get)


def get_average(key, items):
    def get_all_elements_with_same_key(k): return [d for d in items if k in d]

    filtered = [d[key] for d in get_all_elements_with_same_key(key)]

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


@STATS.route('/algorithm/<algorithm>', methods=["GET"])
@jwt_required()
def statistics(algorithm):
    response = aws_connections.DYNAMODB_TABLE.query(
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

    stats["Total Runs"] = len(items)
    stats["Profitable Runs"] = len(
        [item["Strategy Result"] for item in items if "Strategy Result" in item and item["Strategy Result"] > 0])

    return jsonify(stats), 200

# endregion
