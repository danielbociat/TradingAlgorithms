from abc import ABC, abstractmethod
import matplotlib.pyplot as plt
import pandas_ta as ta
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class TradingAlgorithm(ABC):
    def __init__(self):
        self.data = None
        self.chart = None
        self.benchmark_data = None
        self.cumulative_returns = None
        self.simulation_stats = dict()

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

    def generate_benchmark(self, ticker="SPY", period="12mo", interval="1d"):
        self.benchmark_data = yf.download(ticker, period=period, interval=interval)

    def execute_trades(self):
        self.data['Strategy Returns'] = self.data['Position'].shift(1) * self.data['Close'].pct_change()
        self.cumulative_returns = (self.data['Strategy Returns'] + 1).cumprod()
        plt.plot(self.cumulative_returns)
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

    def init_chart(self):
        self.chart = make_subplots(specs=[[{"secondary_y": True}]])
        self.chart.add_trace(go.Candlestick(x=self.data.index,
                                            open=self.data['Open'],
                                            high=self.data['High'],
                                            low=self.data['Low'],
                                            close=self.data['Close'],
                                            ))

    def update_chart(self):
        pass

    def save_chart_html(self):
        self.chart.write_html(r'.\graph.html')


class MeanReversion(TradingAlgorithm):
    def __init__(self, data, time_window=20):
        self.data = data
        self.time_window = time_window
        self.init_chart()

    def prepare_data(self):
        self.data['Moving Average'] = self.data['Close'].rolling(window=self.time_window).mean()
        self.data['Standard Deviation'] = self.data['Close'].rolling(window=self.time_window).std()
        self.data['Upper Band'] = self.data['Moving Average'] + (self.data['Standard Deviation'] * 2)
        self.data['Lower Band'] = self.data['Moving Average'] - (self.data['Standard Deviation'] * 2)
        self.data['Signal'] = 0
        self.data['Position'] = 0

        self.update_chart()

    def generate_signals(self):
        for i in range(self.time_window, len(self.data)):
            if self.data['Close'][i] < self.data['Lower Band'][i]:
                self.data['Signal'][i] = 1
            elif self.data['Close'][i] > self.data['Upper Band'][i]:
                self.data['Signal'][i] = -1
            else:
                self.data['Signal'][i] = 0

            self.data['Position'][i] = self.data['Signal'][i]

    def update_chart(self):
        self.chart.add_trace(
            go.Scatter(x=self.data.index, y=self.data['Upper Band'], marker_color='blue', name='Upper Band'))
        self.chart.add_trace(
            go.Scatter(x=self.data.index, y=self.data['Lower Band'], marker_color='red', name='Lower Band'))


class DoubleRSI(TradingAlgorithm):
    def __init__(self, data, rsi_short_period=14, rsi_long_period=28):
        self.data = data
        self.rsi_short_period = rsi_short_period
        self.rsi_long_period = rsi_long_period
        self.init_chart()

    def prepare_data(self):
        self.data['RSI Short'] = ta.rsi(self.data['Close'], length=self.rsi_short_period, append=True)
        self.data['RSI Long'] = ta.rsi(self.data['Close'], length=self.rsi_long_period, append=True)
        self.data['Signal'] = 0
        self.data['Position'] = 0

        self.update_chart()

    def generate_signals(self):
        for i in range(self.rsi_long_period, len(self.data)):
            if self.data['RSI Short'][i] > self.data['RSI Long'][i]:
                self.data['Signal'][i] = 1
            elif self.data['RSI Short'][i] < self.data['RSI Long'][i]:
                self.data['Signal'][i] = -1
            else:
                self.data['Signal'][i] = 0

            self.data['Position'][i] = self.data['Signal'][i - 1]

    def update_chart(self):
        self.chart.add_trace(
            go.Scatter(x=self.data.index, y=self.data['RSI Short'], marker_color='blue', name='RSI Short'))
        self.chart.add_trace(
            go.Scatter(x=self.data.index, y=self.data['RSI Long'], marker_color='red', name='RSI Long'))


# TODO - review this
class Arbitrage(TradingAlgorithm):
    def __init__(self, data, futures_data, entry_threshold=2, exit_threshold=0):
        self.spy_data = data
        self.es_data = futures_data
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def prepare_data(self):
        self.data = pd.concat([self.spy_data['Close'], self.es_data['Close']], axis=1, join='inner')
        self.data.columns = ['SPY', 'ES']
        self.data['Spread'] = self.data['SPY'] - self.data['ES']
        self.data['Z-Score'] = (self.data['Spread'] - self.data['Spread'].mean()) / self.data['Spread'].std()
        self.data['Position'] = 0

    def generate_signals(self):
        for i in range(1, len(self.data)):
            if self.data['Z-Score'][i] > self.entry_threshold:
                self.data['Position'][i] = -1
            elif self.data['Z-Score'][i] < -self.entry_threshold:
                self.data['Position'][i] = 1
            elif -self.exit_threshold < self.data['Z-Score'][i] < self.exit_threshold:
                self.data['Position'][i] = 0
            else:
                self.data['Position'][i] = self.data['Position'][i - 1]

    def execute_trades(self):
        self.data['SPY Returns'] = self.data['SPY'].pct_change()
        self.data['ES Returns'] = self.data['ES'].pct_change()
        self.data['Strategy Returns'] = self.data['Position'].shift(1) * (self.data['SPY Returns'] - self.data['ES Returns'])
        self.cumulative_returns = (1 + self.data['Strategy Returns']).cumprod()
        plt.plot(self.cumulative_returns)
        plt.xlabel('Time')
        plt.ylabel('Cumulative Returns')
        plt.show()
