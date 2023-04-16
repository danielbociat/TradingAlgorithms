from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import yfinance as yf
import configparser
import talib
from flask import Flask, jsonify, request

pd.options.mode.chained_assignment = None  # default='warn'
config = configparser.RawConfigParser()
config.read('config.ini')
api_dict = dict(config.items('historical_data_api_key'))

app = Flask(__name__)

class TradingAlgorithm(ABC):
    def run_algorithm(self):
        self.prepare_data()
        self.generate_signals()
        self.execute_trades()
        self.compute_alpha()

    @abstractmethod
    def prepare_data(self):
        pass

    @abstractmethod
    def generate_signals(self):
        pass

    def generate_benchmark(self, ticker="SPY", period="12mo", interval="1d"):
        self.benchmark_data = yf.download(ticker, period=period, interval=interval)

    def execute_trades(self):
        self.data['Strategy Returns'] = self.data['Position'].shift(1) * self.data['Close'].pct_change()
        cumulative_returns = (self.data['Strategy Returns'] + 1).cumprod()
        plt.plot(cumulative_returns)
        plt.xlabel('Time')
        plt.ylabel('Cumulative Returns')
        plt.show()

    def compute_alpha(self):
        self.generate_benchmark()

        self.benchmark_data['Benchmark Returns'] = self.benchmark_data['Close'].pct_change()
        self.data['Strategy Returns'] = self.data['Position'].shift(1) * self.data['Close'].pct_change()

        self.data['Excess Returns'] = self.data['Strategy Returns'] - self.benchmark_data['Benchmark Returns']

        # Calculate the cumulative excess returns
        self.data['Cumulative Excess Returns'] = (1 + self.data['Excess Returns']).cumprod() - 1

        # Calculate the annualized alpha
        annualized_alpha = (self.data['Cumulative Excess Returns'].iloc[-1] + 1) ** (252 / len(self.data)) - 1

        print(f"Annualized Alpha: {annualized_alpha:.4f}")

        # Plot the cumulative excess returns (alpha) over time
        plt.plot(self.data['Cumulative Excess Returns'])
        plt.xlabel('Time')
        plt.ylabel('Cumulative Excess Returns (Alpha)')
        plt.show()


class MeanReversal(TradingAlgorithm):
    def __init__(self, data, time_window=20):
        self.data = data
        self.time_window = time_window

    def prepare_data(self):
        self.data['Moving Average'] = self.data['Close'].rolling(window=self.time_window).mean()
        self.data['Standard Deviation'] = self.data['Close'].rolling(window=self.time_window).std()
        self.data['Upper Band'] = self.data['Moving Average'] + (self.data['Standard Deviation'] * 2)
        self.data['Lower Band'] = self.data['Moving Average'] - (self.data['Standard Deviation'] * 2)
        self.data['Signal'] = 0
        self.data['Position'] = 0

    def generate_signals(self):
        for i in range(self.time_window, len(self.data)):
            if self.data['Close'][i] < self.data['Lower Band'][i]:
                self.data['Signal'][i] = 1
            elif self.data['Close'][i] > self.data['Upper Band'][i]:
                self.data['Signal'][i] = -1
            else:
                self.data['Signal'][i] = 0

            self.data['Position'][i] = self.data['Signal'][i]


class DoubleRSI(TradingAlgorithm):
    def __init__(self, data, rsi_short_period=14, rsi_long_period=28):
        self.data = data
        self.rsi_short_period = rsi_short_period
        self.rsi_long_period = rsi_long_period

    def prepare_data(self):
        self.data['RSI Short'] = talib.RSI(self.data['Close'], timeperiod=self.rsi_short_period)
        self.data['RSI Long'] = talib.RSI(self.data['Close'], timeperiod=self.rsi_long_period)
        self.data['Signal'] = 0
        self.data['Position'] = 0

    def generate_signals(self):
        for i in range(self.rsi_long_period, len(self.data)):
            if self.data['RSI Short'][i] > self.data['RSI Long'][i]:
                self.data['Signal'][i] = 1
            elif self.data['RSI Short'][i] < self.data['RSI Long'][i]:
                self.data['Signal'][i] = -1
            else:
                self.data['Signal'][i] = 0

            self.data['Position'][i] = self.data['Signal'][i-1]

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

    app.run(host="0.0.0.0", port=8080, debug=True)

    # TEST
    '''
    ticker = "AAPL"
    period = "12mo"
    interval = "1d"

    data = yf.download(ticker, period=period, interval=interval)
    print(data)

    mean_reversion = MeanReversal(data, 20)
    mean_reversion.run_algorithm()

    data = yf.download(ticker, period=period, interval=interval)

    double_rsi = DoubleRSI(data)
    double_rsi.run_algorithm()
    '''