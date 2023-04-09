from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
import nasdaqdatalink as ndl
import configparser
pd.options.mode.chained_assignment = None  # default='warn'

config = configparser.RawConfigParser()
config.read('config.ini')
api_dict = dict(config.items('historical_data_api_key'))


class TradingAlgorithm(ABC):
    def run_algorithm(self):
        self.prepare_data()
        self.generate_signals()
        self.execute_trades()

    @abstractmethod
    def prepare_data(self):
        pass

    @abstractmethod
    def generate_signals(self):
        pass

    def execute_trades(self):
        print("Executing trades based on generated signals")


class DoubleRSI(TradingAlgorithm):
    def prepare_data(self):
        print("TODO: Preparing data")

    def generate_signals(self):
        print("TODO: Generate signals")


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

            self.data['Position'][i] = self.data['Signal'][i - 1]

    def execute_trades(self):
        self.data['Strategy Returns'] = self.data['Position'].shift(1) * self.data['Close'].pct_change()
        cumulative_returns = (self.data['Strategy Returns'] + 1).cumprod()
        plt.plot(cumulative_returns)
        plt.xlabel('Time')
        plt.ylabel('Cumulative Returns')
        plt.show()


if __name__ == "__main__":
    # TEST
    ticker = "AAPL"
    data = yf.download(ticker, interval="1d")
    print(data)

    mean_reversion = MeanReversal(data, 10)
    mean_reversion.run_algorithm()
