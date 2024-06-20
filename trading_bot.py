import ccxt.async_support as ccxt
import asyncio
import logging
import pandas as pd
from datetime import datetime
import json

# Configure logging
logging.basicConfig(filename='trading_bot.log', level=logging.INFO, format='%(asctime)s - %(message)s')

# Initialize Binance API
binance = ccxt.binance({
    'apiKey': 'AppzE59Z1cF5pGUTmGcE2hxlI0oWa00TYhpD6PBj5EAW9cH2WpFflmXOH6EuWo5y',
    'secret': '11sfe1D2H9lYKrkQuHZC9n72kJErJNAZqL0oxwmPvsbAdcF6kNUBB47YYXqQQsjH',
    'enableRateLimit': True,
    'options': {
        'defaultType': 'spot',
        'adjustForTimeDifference': True,
    }
})

# Parameters
pair = 'USDC/USDT'
profit_margin = 0.0001
initial_trade_amount = 10
fee_rate = 0.0
max_trades_per_day = 1000
log_data = []
balance_file = 'balance.json'

def load_balance():
    try:
        with open(balance_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'USDT': initial_trade_amount, 'USDC': 0}

def save_balance(balance):
    with open(balance_file, 'w') as f:
        json.dump(balance, f)

async def get_order_book():
    for attempt in range(5):
        try:
            return await binance.fetch_order_book(pair)
        except ccxt.BaseError as e:
            print(f"API Error while fetching order book: {e}")
            logging.error(f"API Error while fetching order book: {e}")
            await asyncio.sleep(2 ** attempt)
    raise Exception("Failed to fetch order book after 5 attempts")

async def place_order(side, amount, price):
    for attempt in range(5):
        try:
            if side == 'buy':
                return await binance.create_limit_buy_order(pair, amount, price)
            elif side == 'sell':
                return await binance.create_limit_sell_order(pair, amount, price)
        except ccxt.BaseError as e:
            print(f"API Error while placing order: {e}")
            logging.error(f"API Error while placing order: {e}")
            await asyncio.sleep(2 ** attempt)
    raise Exception("Failed to place order after 5 attempts")

def calculate_profit(buy_price, sell_price, amount):
    cost = buy_price * amount * (1 + fee_rate)
    revenue = sell_price * amount * (1 - fee_rate)
    return revenue - cost

async def check_balance():
    for attempt in range(5):
        try:
            balance = await binance.fetch_balance()
            logging.info(f"Fetched balance: {balance}")
            return {
                'USDT': balance['total']['USDT'],
                'USDC': balance['total']['USDC']
            }
        except ccxt.BaseError as e:
            print(f"API Error while fetching balance: {e}")
            logging.error(f"API Error while fetching balance: {e}")
            await asyncio.sleep(2 ** attempt)
    raise Exception("Failed to fetch balance after 5 attempts")

def log_trade(trade_data):
    log_data.append(trade_data)
    logging.info(trade_data)

def export_to_excel():
    df = pd.DataFrame(log_data)
    df.to_excel('trades_log.xlsx', index=False)

async def main():
    global initial_trade_amount  # Use the global initial_trade_amount variable
    trades_executed = 0
    total_profit = 0
    
    # Load initial balance
    balance = load_balance()
    print(f"Initial Balance: USDT: {balance['USDT']}, USDC: {balance['USDC']}")
    
    while trades_executed < max_trades_per_day:
        try:
            # Check current balance
            balance = await check_balance()
            print(f"Current Balance: USDT: {balance['USDT']}, USDC: {balance['USDC']}")
            
            if balance['USDT'] < initial_trade_amount:
                print("Insufficient USDT balance for trading. Exiting.")
                break
            
            # Get real-time order book
            order_book = await get_order_book()
            buy_price = order_book['bids'][0][0]
            sell_price = order_book['asks'][0][0]
            
            # Determine if the current prices offer a profitable trade
            if buy_price + profit_margin <= sell_price:
                profit = calculate_profit(buy_price, sell_price, initial_trade_amount)
                if profit > 0:
                    print(f"Executing trade: Buy at {buy_price}, Sell at {sell_price}, Profit: {profit}")
                    
                    # Execute buy order: USDT -> USDC
                    buy_order = await place_order('buy', initial_trade_amount, buy_price)
                    await asyncio.sleep(1)
                    while buy_order['filled'] < buy_order['amount']:
                        await asyncio.sleep(1)
                        buy_order = await binance.fetch_order(buy_order['id'], pair)
                    
                    usdc_amount = buy_order['filled']
                    
                    # Execute sell order: USDC -> USDT
                    sell_order = await place_order('sell', usdc_amount, sell_price)
                    await asyncio.sleep(1)
                    while sell_order['filled'] < sell_order['amount']:
                        await asyncio.sleep(1)
                        sell_order = await binance.fetch_order(sell_order['id'], pair)
                    
                    profit = calculate_profit(buy_price, sell_price, usdc_amount)
                    balance['USDT'] += profit
                    total_profit += profit
                    trades_executed += 1
                    trade_data = {
                        'time': datetime.now(),
                        'buy_price': buy_price,
                        'sell_price': sell_price,
                        'amount_before': initial_trade_amount,
                        'amount_after': initial_trade_amount + profit,
                        'profit': profit,
                        'profit_percent': (profit / initial_trade_amount) * 100,
                    }
                    log_trade(trade_data)
                    
                    # Save updated balance
                    save_balance(balance)
                else:
                    print("No profitable trade found")
            else:
                print("No arbitrage opportunity detected")
                
            await asyncio.sleep(1)  # Reduced sleep time for quicker re-evaluation
            
        except ccxt.BaseError as e:
            print(f"API Error: {e}")
            logging.error(f"API Error: {e}")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Unexpected Error: {e}")
            logging.error(f"Unexpected Error: {e}")
            await asyncio.sleep(10)

    export_to_excel()
    print(f"Total profit: {total_profit}")

if __name__ == '__main__':
    asyncio.run(main())
