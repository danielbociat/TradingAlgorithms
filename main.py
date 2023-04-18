import yfinance as yf
from flask import Flask, jsonify, request
import configparser
from trading_algorithms import *
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
    # TEST
    '''
    app.run(host="0.0.0.0", port=8081, debug=True)
    
    
    '''
    ticker = "AAPL"
    period = "12mo"
    interval = "1d"

    data = yf.download("AAPL", period=period, interval=interval)
    print(data)

    mr = MeanReversal(data)
    mr.run_algorithm()
    mr.save_chart_html()
