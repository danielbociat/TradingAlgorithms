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
        self.trades = {
            "time": [],
            "price": [],
            "mode": []
        }

    def run_algorithm(self):
        self.prepare_data()
        self.generate_signals()
        self.execute_trades()
        self.populate_simulation_stats()
        self.add_entry_exit()
        self.remove_gaps_chart()

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

        try:
            for index, row in self.data.iterrows():
                if row["Position"] * current_pos < 0:
                    # Execute trade
                    end_price = row["Close"]
                    current_sum = current_sum * ((end_price / start_price) ** current_pos)

                    # Switch position
                    current_pos = row["Position"]
                    start_price = end_price

                    self.trades["price"].append(end_price)
                    self.trades["time"].append(index)
                    self.trades["mode"].append(current_pos)

                if current_pos == 0 and row["Position"] in [-1, 1]:
                    current_pos = row["Position"]
                    start_price = row["Close"]

                    self.trades["price"].append(start_price)
                    self.trades["time"].append(index)
                    self.trades["mode"].append(current_pos)

                self.cumulative_returns.append(current_sum)
        except Exception as e:
            print(e)

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

    def add_entry_exit(self):
        entry_exit = pd.DataFrame(self.trades)

        self.chart.add_trace(
            go.Scatter(
                x=entry_exit["time"],
                y=entry_exit["price"],
                mode="markers",
                marker_color=["blue" if e > 0 else "orange" for e in entry_exit["mode"]],
                hovertemplate=["LONG" if e > 0 else "SHORT" for e in entry_exit["mode"]],
                name="Position type"
            ),
        )

    def update_chart(self):
        pass

    def remove_gaps_chart(self):
        self.chart.update_yaxes(fixedrange=False)
        self.chart.update_xaxes(rangebreaks=[
            dict(bounds=['sat', 'mon']),  # hide weekends
            dict(values=["2021-12-25", "2022-01-01"])  # hide Xmas and New Year
        ])

    def save_chart_html(self):
        self.chart.write_html(r'.\graph.html')

    @staticmethod
    def sharpe_ratio(cumulative_return, daily_risk_free_rate):
        cumulative_return_df = pd.Series(cumulative_return)
        returns = cumulative_return_df.pct_change().dropna()
        excess_return = returns - daily_risk_free_rate

        sharpe_ratio = excess_return.mean() / excess_return.std()

        return sharpe_ratio

    @staticmethod
    def sortino_ratio(cumulative_return, daily_risk_free_rate):
        cumulative_return_df = pd.Series(cumulative_return)
        returns = cumulative_return_df.pct_change().dropna()
        excess_return = returns - daily_risk_free_rate

        print(daily_risk_free_rate)

        downside_deviation = excess_return[excess_return < 0].std()
        sortino_ratio = excess_return.mean() / downside_deviation

        return sortino_ratio

    # TODO : Review this, maybe add some more things => look TradingView
    def populate_simulation_stats(self):
        self.simulation_stats["Number of trades"] = len(self.trades["time"])
        self.simulation_stats["Profitable trades"] = len(
            [y for x, y in zip([1] + self.cumulative_returns, self.cumulative_returns) if y < x])
        self.simulation_stats["Strategy Result"] = self.cumulative_returns[-1] - 1
        self.simulation_stats["Max Profit"] = np.nanmax(self.cumulative_returns) - 1
        self.simulation_stats["Max Loss"] = np.nanmin(self.cumulative_returns) - 1

        risk_free_rate_annual = 0.03
        risk_free_rate_daily = (1 + risk_free_rate_annual) ** (1 / 252) - 1

        self.simulation_stats["Sharpe ratio"] = TradingAlgorithm.sharpe_ratio(self.cumulative_returns, risk_free_rate_daily)
        self.simulation_stats["Sortino ratio"] = TradingAlgorithm.sortino_ratio(self.cumulative_returns, risk_free_rate_daily)


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
        super().init_chart()
        self.chart.add_trace(
            go.Scatter(x=self.data.index, y=self.data['Upper Band'], marker_color='blue', name='Upper Band'))
        self.chart.add_trace(
            go.Scatter(x=self.data.index, y=self.data['Lower Band'], marker_color='red', name='Lower Band'))

    def populate_simulation_stats(self):
        super().populate_simulation_stats()
        self.simulation_stats["Holding Result"] = self.data.iloc[-1]["Close"] / self.data.iloc[0]["Close"] - 1


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
        self.simulation_stats["Holding Result"] = self.data.iloc[-1]["Close"] / self.data.iloc[0]["Close"] - 1


# TODO - review this, find a way to map tickers and futures
class Arbitrage(TradingAlgorithm):
    def __init__(self, data, arbitrage_data, entry_threshold=2, exit_threshold=0):
        super().__init__()
        self.data1 = data
        self.data2 = arbitrage_data
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def prepare_data(self):
        self.data = pd.concat([self.data1['Close'], self.data2['Close']], axis=1, join='inner')
        self.data.columns = ['Data 1', 'Data 2']
        self.data['Spread'] = self.data['Data 1'] - self.data['Data 2']
        self.data['Z-Score'] = (self.data['Spread'] - self.data['Spread'].mean()) / self.data['Spread'].std()
        self.data['Position'] = 0

        self.update_chart()

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
        current_sum = 1
        self.trades["price2"] = list()
        self.data['Position'] = self.data['Position'].shift(1)

        try:
            for index, row in self.data.iterrows():
                if row["Position"] in [-1, 1]:
                    # Execute trade
                    current_sum = current_sum * ((row["Data 2"] / row["Data 1"]) ** row["Position"])

                    self.trades["price"].append(row["Data 1"])
                    self.trades["price2"].append(row["Data 2"])
                    self.trades["time"].append(index)
                    self.trades["mode"].append(row["Position"])
                    self.cumulative_returns.append(current_sum)

        except Exception as e:
            print(e)

    def populate_simulation_stats(self):
        super().populate_simulation_stats()

    def init_chart(self, data, row):
        self.chart.add_trace(go.Candlestick(x=data.index,
                                            open=data['Open'],
                                            high=data['High'],
                                            low=data['Low'],
                                            close=data['Close'],
                                            ), row=row, col=1)

    def update_chart(self):
        self.chart = make_subplots(rows=2, cols=1,
                                   specs=[[{"secondary_y": True}], [{}]],
                                   shared_xaxes=True,
                                   vertical_spacing=0.05,
                                   row_heights=[0.5, 0.5])
        self.init_chart(self.data1, 1)
        self.init_chart(self.data2, 2)
        self.chart.update_layout(
            xaxis_rangeslider_visible=False,
            xaxis2_rangeslider_visible=True,
            xaxis_type="date"
        )

    def add_entry_exit(self):
        entry_exit = pd.DataFrame(self.trades)

        self.chart.add_trace(
            go.Scatter(
                x=entry_exit["time"],
                y=entry_exit["price"],
                mode="markers",
                marker_color=["blue" if e > 0 else "orange" for e in entry_exit["mode"]],
                hovertemplate=["BUY" if e > 0 else "SELL" for e in entry_exit["mode"]],
                name="Position type"
            ),
            row=1, col=1
        )

        self.chart.add_trace(
            go.Scatter(
                x=entry_exit["time"],
                y=entry_exit["price2"],
                mode="markers",
                marker_color=["blue" if e < 0 else "orange" for e in entry_exit["mode"]],
                hovertemplate=["BUY" if e < 0 else "SELL" for e in entry_exit["mode"]],
                name="Position type"
            ),
            row=2, col=1
        )

    def remove_gaps_chart(self):
        super().remove_gaps_chart()
        self.chart.update_xaxes(rangebreaks=[
            dict(bounds=[16, 9.5], pattern='hour'),
        ])
