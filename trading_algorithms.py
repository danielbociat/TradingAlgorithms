from abc import ABC, abstractmethod
import matplotlib.pyplot as plt
import pandas_ta as ta
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np


# TODO : Remove/Clear financial data from the class, add it as parameter
class TradingAlgorithm(ABC):
    def __init__(self):
        self.data = None
        self.chart = None
        self.benchmark_data = None
        self.cumulative_returns = list()
        self.simulation_stats = dict()

    def run_algorithm(self):
        self.prepare_data()
        self.generate_signals()
        self.execute_trades()
        self.populate_simulation_stats()

    @abstractmethod
    def prepare_data(self):
        pass

    @abstractmethod
    def generate_signals(self):
        pass

    def generate_benchmark(self, ticker="SPY", period="12mo", interval="1d"):
        self.benchmark_data = yf.download(ticker, period=period, interval=interval)

    def execute_trades(self):
        current_pos = 0
        start_price = 0
        current_sum = 1
        self.data['Position'] = self.data['Position'].shift(1)

        for index, row in self.data.iterrows():
            if row["Position"] * current_pos < 0:
                # Execute trade
                end_price = row["Close"]
                current_sum = current_sum * ((end_price/start_price) ** current_pos)

                # print(start_price, end_price, current_pos, current_sum)

                # Switch position
                current_pos = row["Position"]
                start_price = end_price

                self.cumulative_returns.append(current_sum)

            if current_pos == 0 and row["Position"] in [-1, 1]:
                current_pos = row["Position"]
                start_price = row["Close"]

    # TODO: Refactor to allow for a general situation, not only yearly; Remove completely??
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
        # plt.show()

    def init_chart(self):
        self.chart.add_trace(go.Candlestick(x=self.data.index,
                                            open=self.data['Open'],
                                            high=self.data['High'],
                                            low=self.data['Low'],
                                            close=self.data['Close'],
                                            ))

    # TODO : Update charts to allow for multiple subcharts (RSI), charts (Arbitrage) and display buying and selling points
    def update_chart(self):
        pass

    def save_chart_html(self):
        self.chart.write_html(r'.\graph.html')

    # TODO : Review this, maybe add some more things => look TradingView
    def populate_simulation_stats(self):
        self.simulation_stats["Number of trades"] = len(self.cumulative_returns)
        self.simulation_stats["Profitable trades"] = len([y for x, y in zip([1]+self.cumulative_returns, self.cumulative_returns) if y > x])
        self.simulation_stats["Holding Result"] = self.data.iloc[-1]["Close"] / self.data.iloc[0]["Close"] - 1
        self.simulation_stats["Strategy Result"] = self.cumulative_returns[-1] - 1
        self.simulation_stats["Max Profit"] = np.nanmax(self.cumulative_returns) - 1
        self.simulation_stats["Max Loss"] = np.nanmin(self.cumulative_returns) - 1


class MeanReversion(TradingAlgorithm):
    def __init__(self, data, time_window=20):
        super().__init__()
        self.data = data
        self.time_window = time_window

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
        self.chart = make_subplots(
            specs=[[{"secondary_y": True}]],
            shared_xaxes=True
        )
        self.init_chart()
        self.chart.add_trace(
            go.Scatter(x=self.data.index, y=self.data['Upper Band'], marker_color='blue', name='Upper Band'))
        self.chart.add_trace(
            go.Scatter(x=self.data.index, y=self.data['Lower Band'], marker_color='red', name='Lower Band'))


class DoubleRSI(TradingAlgorithm):
    def __init__(self, data, rsi_short_period=14, rsi_long_period=28):
        super().__init__()
        self.data = data
        self.rsi_short_period = rsi_short_period
        self.rsi_long_period = rsi_long_period

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
        self.chart = make_subplots(rows=2, cols=1,
                                   specs=[[{"secondary_y": True}], [{}]],
                                   shared_xaxes=True,
                                   vertical_spacing=0.05,
                                   row_heights=[0.75, 0.25])
        self.init_chart()
        self.chart.add_trace(
            go.Scatter(x=self.data.index, y=self.data['RSI Short'], marker_color='blue', name='RSI Short'),
            row=2, col=1)
        self.chart.add_trace(
            go.Scatter(x=self.data.index, y=self.data['RSI Long'], marker_color='red', name='RSI Long'),
            row=2, col=1)
        self.chart.update_layout(
            xaxis_rangeslider_visible=False,
            xaxis2_rangeslider_visible=True,
            xaxis_type="date"
        )

    def populate_simulation_stats(self):
        super().populate_simulation_stats()


# TODO - review this, find a way to map tickers and futures
class Arbitrage(TradingAlgorithm):
    def __init__(self, data, futures_data, entry_threshold=2, exit_threshold=0):
        super().__init__()
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
        self.data['Strategy Returns'] = self.data['Position'].shift(1) * (
                self.data['SPY Returns'] - self.data['ES Returns'])
        self.cumulative_returns = (1 + self.data['Strategy Returns']).cumprod()
        plt.plot(self.cumulative_returns)
        plt.xlabel('Time')
        plt.ylabel('Cumulative Returns')
        # plt.show()
