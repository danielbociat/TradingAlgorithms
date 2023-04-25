import yfinance as yf
from flask import Flask, jsonify, request
import configparser
from trading_algorithms import *
import pandas as pd

pd.options.mode.chained_assignment = None  # default='warn'

'''
config = configparser.RawConfigParser()
config.read('config.ini')
api_dict = dict(config.items('historical_data_api_key'))
'''

application = Flask(__name__)

'''

@app.before_request
def before():
    print(request.json)
'''


@application.route('/', methods=['GET', 'POST'])
def run_algorithm():
    return "Hello World!"


@application.route('/algorithms', methods=["GET"])
def get_algorithms():
    return "The existing algorithms are: 'double_rsi', 'mean_reversal', 'arbitrage'", 200


if __name__ == "__main__":
    # TEST
    application.run()

    '''
    ticker = "AAPL"
    period = "12mo"
    interval = "1d"

    data = yf.download("AAPL", period=period, interval=interval)
    print(data)

    data.to_csv("data.csv")

    mr = DoubleRSI(data)
    mr.run_algorithm()
    mr.save_chart_html()
    '''
