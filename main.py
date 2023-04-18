import yfinance as yf
from flask import Flask, jsonify, request
import configparser
from trading_algorithms import *

pd.options.mode.chained_assignment = None  # default='warn'
config = configparser.RawConfigParser()
config.read('config.ini')
api_dict = dict(config.items('historical_data_api_key'))

app = Flask(__name__)


@app.before_request
def before():
    print(request.json)


@app.route('/run/', methods=['GET', 'POST'])
def run_algorithm():
    return "Hello World!"


@app.route('/algorithms', methods=["GET"])
def get_algorithms():
    return "The existing algorithms are: 'double_rsi', 'mean_reversal', 'arbitrage'", 200


if __name__ == "__main__":

    app.run(host="0.0.0.0", port=8081, debug=True)

    # TEST
    '''
    
    ticker = "PL"
    period = "7d"
    interval = "5m"

    data = yf.download("^GSPC", period=period, interval=interval)
    print(data)

    futures_data = yf.download("ES=F", period=period, interval=interval)
    print(futures_data)

    arbitrage = Arbitrage(data, futures_data)
    arbitrage.run_algorithm()
    '''
