import telebot
import ccxt
import config
import schedule
import pandas as pd
from datetime import datetime


bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN, parse_mode='HTML')


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Howdy, how are you doing?")


@bot.message_handler(func=lambda message: True)
def echo_all(message):
    print(message)
    bot.reply_to(message, message.text)


print(datetime.now().strftime('%Y-%m-%d %H:%M:%S ')+'Bot started')
print()
# bot.infinity_polling()
bot.send_message(config.CHANEL_ID, datetime.now().strftime('%Y-%m-%d %H:%M:%S ')+'Bot restarted')



pd.set_option('display.max_rows', None)

import warnings

warnings.filterwarnings('ignore')

import numpy as np
from datetime import datetime
import time

exchange = ccxt.binance({
    "apiKey": config.BINANCE_API_KEY,
    "secret": config.BINANCE_SECRET_KEY
})
exchange.set_sandbox_mode(True)


def get_balance():
    # print('all balance\n')
    balance = exchange.fetch_balance().get('info')
    asset = balance.get('balances')
    result = {}
    for current in range(0, len(asset)):
        result[asset[current].get('asset')] = asset[current].get('free')
        # print(asset[current].get('asset') + ': ' + asset[current].get('free'))
    return result


balances = get_balance()
print('Balances:' + balances['USDT'] + ' USDT')
print('Balances:' + balances['BTC'] + ' BTC')


def RSI(df, period=14):
    series = df['close']
    delta = series.diff().dropna()
    u = delta * 0
    d = u.copy()
    u[delta > 0] = delta[delta > 0]
    d[delta < 0] = -delta[delta < 0]
    u[u.index[period - 1]] = np.mean(u[:period])  # first value is sum of avg gains
    u = u.drop(u.index[:(period - 1)])
    d[d.index[period - 1]] = np.mean(d[:period])  # first value is sum of avg losses
    d = d.drop(d.index[:(period - 1)])
    rs = pd.DataFrame.ewm(u, com=period - 1, adjust=False).mean() / \
         pd.DataFrame.ewm(d, com=period - 1, adjust=False).mean()
    rsi = 100 - 100 / (1 + rs)
    df['rsi'] = rsi
    return df

def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])

    tr = data[['high-low', 'high-pc', 'low-pc']].max(axis=1)

    return tr


def atr(data, period):
    data['tr'] = tr(data)
    atr = data['tr'].rolling(period).mean()

    return atr


def get_trend(df, period=7, atr_multiplier=3):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = atr(df, period)
    df['upperband'] = hl2 + (atr_multiplier * df['atr'])
    df['lowerband'] = hl2 - (atr_multiplier * df['atr'])
    df['in_uptrend'] = True

    for current in range(1, len(df.index)):
        previous = current - 1

        if df['close'][current] > df['upperband'][previous]:
            df['in_uptrend'][current] = True
        elif df['close'][current] < df['lowerband'][previous]:
            df['in_uptrend'][current] = False
        else:
            df['in_uptrend'][current] = df['in_uptrend'][previous]

            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df['lowerband'][current] = df['lowerband'][previous]

            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]

    return df


in_position = False
position_cap = 0.0
last_buy_price = 0.0
amount = 0.05

def check_buy_sell_signals(df):
    global in_position, position_cap, last_buy_price, amount

    # print("checking for buy and sell signals")
    #print(df.tail(5))
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1

    if in_position:
        stop_lost_percent = 0.01
        stop_lost_price = last_buy_price - (last_buy_price*stop_lost_percent)
        if last_buy_price > 0 and df['close'][previous_row_index] <= stop_lost_price:
            print("STOP LOST: SELL")
            order = exchange.create_market_sell_order('BTC/USDT', amount)
            # print(order)
            in_position = False
            position_cap_late = float(order.get('info').get('cummulativeQuoteQty'))
            profit = position_cap_late - position_cap
            priceAvg = float(order.get('info').get('cummulativeQuoteQty')) / float(order.get('info').get('executedQty'))

            balance = 'Balance: ' + get_balance()['USDT'] + 'USDT'

            rs = 'SELL STOPLOST' + str(amount) + ' BTC with price USDT: ' + order.get('info').get(
                'cummulativeQuoteQty') + ' - take profit: ' + str(profit) + '\n' + balance
            bot.send_message(config.CHANEL_ID, '<del>SELL STOPLOST</del> <b>' + str(amount) + '</b> BTC với số tiền <b><i>' + order.get(
                'info').get('cummulativeQuoteQty') + ' USDT</i></b>\nGiá TB: ' + str(
                priceAvg) + 'USDT\nLợi nhuận: <b>' + str(profit) + ' USDT</b>\n' + balance)
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S ') + rs)
            return

    # if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:
    if df['rsi'][last_row_index] <= 35:
        print("changed to uptrend, buy")
        if not in_position:
            order = exchange.create_market_buy_order('BTC/USDT', amount)
            # print(order)
            in_position = True
            position_cap = float(order.get('info').get('cummulativeQuoteQty'))

            balance = 'Balance: ' + get_balance()['USDT'] + 'USDT'

            priceAvg = float(order.get('info').get('cummulativeQuoteQty')) / float(order.get('info').get('executedQty'))
            last_buy_price = priceAvg

            rs = 'BUY ' + str(amount) + ' BTC with price USDT: ' + order.get('info').get(
                'cummulativeQuoteQty') + ' - Giá tb: ' + str(priceAvg) + ' ' + balance
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S ') + rs)
            bot.send_message(config.CHANEL_ID, 'BUY <b>' + str(
                amount) + ' BTC</b>  với số tiền <b><i>' + order.get('info').get(
                'cummulativeQuoteQty') + ' USDT</i></b>\nGiá TB: ' + str(priceAvg) + 'USDT\n' + balance)

        else:
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S ') + "already in position, nothing to do")

    # if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
    if df['rsi'][last_row_index] >= 67:
        if in_position:
            print("changed to downtrend, sell")
            order = exchange.create_market_sell_order('BTC/USDT', amount)
            # print(order)
            in_position = False
            position_cap_late = float(order.get('info').get('cummulativeQuoteQty'))
            profit = position_cap_late - position_cap
            priceAvg = float(order.get('info').get('cummulativeQuoteQty')) / float(order.get('info').get('executedQty'))

            balance = 'Balance: ' + get_balance()['USDT'] + 'USDT'

            rs = 'SELL ' + str(amount) + ' BTC with price USDT: ' + order.get('info').get(
                'cummulativeQuoteQty') + ' - take profit: ' + str(profit) + '\n' + balance
            bot.send_message(config.CHANEL_ID, '<del>SELL</del> <b>' + str(amount) + '</b> BTC với số tiền <b><i>' + order.get(
                'info').get('cummulativeQuoteQty') + ' USDT</i></b>\nGiá TB: ' + str(
                priceAvg) + 'USDT\nLợi nhuận: <b>' + str(profit) + ' USDT</b>\n' + balance)
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S ') + rs)
        else:
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S ') + "You aren't in position, nothing to sell")


def run_bot():
    # print(f"Fetching new bars for {datetime.now().isoformat()}")
    bars = exchange.fetch_ohlcv('BTC/USDT', timeframe='1m', limit=100)
    df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    trend_data = get_trend(df)
    trend_data = RSI(trend_data)
    check_buy_sell_signals(trend_data)


# print('BUY')
# order = exchange.create_market_buy_order('BTC/USDT', 0.027)
# print(order)
# price = float(order.get('info').get('cummulativeQuoteQty'))/float(order.get('info').get('executedQty'))
# print('Giá tb: '+str(price))
#
# print('SELL')
# order = exchange.create_market_sell_order('BTC/USDT', 0.0181)
# print(order)
# price = float(order.get('info').get('cummulativeQuoteQty'))/float(order.get('info').get('executedQty'))
# print('Giá tb: '+str(price))
# #
# balances = get_balance()
# print('Balances:' + balances['USDT'] + ' USDT')
# print('Balances:' + balances['BTC'] + ' BTC')

schedule.every(10).seconds.do(run_bot)
while True:
    schedule.run_pending()
    time.sleep(1)
