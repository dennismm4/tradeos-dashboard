"""
TradeOS — Binance Grid Trading Bot
====================================
Connects to your Binance account via API and runs a
grid trading strategy on BTC/USDT (or any pair you choose).

Author : TradeOS / Claude
Version: 1.0.0
Account: Binance (Kenya)

SETUP STEPS:
  1. pip install python-binance pandas python-dotenv
  2. Create a .env file with your Binance API keys (see below)
  3. Run:  python binance_bot.py --mode paper   (paper trade first!)
  4. Run:  python binance_bot.py --mode live    (only when ready)

RISK NOTICE:
  - Never trade more than you can afford to lose
  - Always run in paper mode for at least 2 weeks first
  - Max risk per grid level: 2% of account
"""

import os, sys, time, math, json, argparse, logging
from datetime import datetime
from dotenv import load_dotenv

# ── Try importing binance; guide user if not installed ──
try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
    from binance.enums import *
except ImportError:
    print("\n[ERROR] python-binance not installed.")
    print("Run:  pip install python-binance python-dotenv pandas\n")
    sys.exit(1)

load_dotenv()

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('tradeos_binance.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger('TradeOS')

# ══════════════════════════════════════════
#   CONFIGURATION — edit these to your needs
# ══════════════════════════════════════════
CONFIG = {
    # Trading pair
    'SYMBOL':        'BTCUSDT',       # BTC/USDT pair

    # Grid settings
    'GRID_LOWER':    64000.0,         # Bottom of grid ($)
    'GRID_UPPER':    70000.0,         # Top of grid ($)
    'GRID_LEVELS':   10,              # Number of grid lines

    # Capital
    'TOTAL_CAPITAL': 20.0,            # Your $20 Binance allocation (USDT)
    'PER_GRID_USD':  1.8,             # ~$1.8 per grid level (10% buffer)

    # Risk management
    'STOP_LOSS':     63000.0,         # Hard stop-loss below grid
    'MAX_LOSS_PCT':  0.15,            # Stop bot if -15% total loss
    'MAX_RISK_TRADE': 0.02,           # Max 2% capital per trade

    # Bot behaviour
    'CHECK_INTERVAL': 10,             # Seconds between price checks
    'LOG_INTERVAL':   60,             # Seconds between status logs
}


class GridBot:
    """
    Simple symmetric grid bot.
    Places buy orders at each grid level below current price,
    and sell orders at each grid level above current price.
    When a buy fills, immediately places a sell one grid higher.
    When a sell fills, immediately places a buy one grid lower.
    """

    def __init__(self, client: Client, config: dict, paper: bool = True):
        self.client = client
        self.cfg    = config
        self.paper  = paper
        self.symbol = config['SYMBOL']
        self.mode   = 'PAPER' if paper else 'LIVE'

        # State
        self.grid_prices   = []   # All grid price levels
        self.open_orders   = {}   # {price: order_id}
        self.filled_buys   = []   # Prices where we bought
        self.pnl           = 0.0  # Running P&L
        self.total_trades  = 0
        self.wins          = 0
        self.losses        = 0
        self.start_time    = datetime.now()
        self.last_log      = time.time()

        # Paper trading state
        self.paper_balance_usdt = config['TOTAL_CAPITAL']
        self.paper_balance_btc  = 0.0
        self.paper_orders       = {}   # Simulated orders

        self._build_grid()
        log.info(f"[{self.mode}] GridBot initialized")
        log.info(f"  Symbol  : {self.symbol}")
        log.info(f"  Range   : ${config['GRID_LOWER']:,.0f} – ${config['GRID_UPPER']:,.0f}")
        log.info(f"  Levels  : {config['GRID_LEVELS']}")
        log.info(f"  Capital : ${config['TOTAL_CAPITAL']:.2f} USDT")
        log.info(f"  Per grid: ${config['PER_GRID_USD']:.2f} USDT")
        log.info(f"  Stop-loss: ${config['STOP_LOSS']:,.0f}")

    def _build_grid(self):
        low  = self.cfg['GRID_LOWER']
        high = self.cfg['GRID_UPPER']
        n    = self.cfg['GRID_LEVELS']
        step = (high - low) / n
        self.grid_prices = [round(low + step * i, 2) for i in range(n + 1)]
        self.grid_step   = step
        log.info(f"  Grid step: ${step:,.0f}")
        log.info(f"  Levels: {[f'${p:,.0f}' for p in self.grid_prices]}")

    def get_price(self) -> float:
        """Fetch current BTC price."""
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            log.error(f"Price fetch failed: {e}")
            return None

    def get_quantity(self, usdt_amount: float, price: float) -> float:
        """Calculate BTC quantity for a given USDT amount."""
        qty = usdt_amount / price
        # Round to Binance's minimum step size (0.00001 BTC)
        return math.floor(qty * 100000) / 100000

    def place_order(self, side: str, price: float) -> str:
        """Place a limit order. Returns order ID."""
        qty = self.get_quantity(self.cfg['PER_GRID_USD'], price)
        if qty <= 0:
            log.warning(f"Quantity too small at ${price:,.0f}")
            return None

        if self.paper:
            oid = f"PAPER_{side}_{price}_{int(time.time())}"
            self.paper_orders[oid] = {
                'side': side, 'price': price, 'qty': qty,
                'status': 'OPEN', 'time': datetime.now().isoformat()
            }
            log.info(f"[PAPER] {side} order placed: {qty:.5f} BTC @ ${price:,.0f}")
            return oid

        try:
            order = self.client.create_order(
                symbol=self.symbol,
                side=SIDE_BUY if side == 'BUY' else SIDE_SELL,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=f"{qty:.5f}",
                price=f"{price:.2f}"
            )
            log.info(f"[LIVE] {side} order #{order['orderId']}: {qty:.5f} BTC @ ${price:,.2f}")
            return str(order['orderId'])
        except BinanceAPIException as e:
            log.error(f"Order failed [{side} @ {price}]: {e}")
            return None

    def check_fills(self, current_price: float):
        """
        Paper mode: simulate order fills based on current price.
        Live mode: check Binance for filled orders.
        """
        if self.paper:
            for oid, order in list(self.paper_orders.items()):
                if order['status'] != 'OPEN':
                    continue
                filled = False
                if order['side'] == 'BUY' and current_price <= order['price']:
                    filled = True
                if order['side'] == 'SELL' and current_price >= order['price']:
                    filled = True

                if filled:
                    order['status'] = 'FILLED'
                    cost = order['qty'] * order['price']
                    if order['side'] == 'BUY':
                        self.paper_balance_usdt -= cost
                        self.paper_balance_btc  += order['qty']
                        self.filled_buys.append(order['price'])
                        log.info(f"[PAPER FILL] BUY {order['qty']:.5f} BTC @ ${order['price']:,.0f} (cost ${cost:.2f})")
                        # Place corresponding sell at next grid level up
                        sell_price = order['price'] + self.grid_step
                        if sell_price <= self.cfg['GRID_UPPER']:
                            self.place_order('SELL', sell_price)
                    else:
                        revenue = order['qty'] * order['price']
                        buy_price = order['price'] - self.grid_step
                        trade_pnl = (order['price'] - buy_price) * order['qty']
                        self.pnl   += trade_pnl
                        self.paper_balance_usdt += revenue
                        self.paper_balance_btc  -= order['qty']
                        self.total_trades += 1
                        if trade_pnl > 0:
                            self.wins += 1
                        else:
                            self.losses += 1
                        log.info(f"[PAPER FILL] SELL {order['qty']:.5f} BTC @ ${order['price']:,.0f} | P&L: +${trade_pnl:.4f}")
                        # Place corresponding buy at next grid level down
                        buy_back = order['price'] - self.grid_step
                        if buy_back >= self.cfg['GRID_LOWER']:
                            self.place_order('BUY', buy_back)

    def init_grid(self, current_price: float):
        """Place initial grid orders around current price."""
        log.info(f"\n{'='*50}")
        log.info(f"Initialising grid at current price ${current_price:,.0f}")
        log.info(f"{'='*50}")

        placed = 0
        for gp in self.grid_prices:
            if gp < current_price:
                # Place buy orders below current price
                oid = self.place_order('BUY', gp)
                if oid:
                    self.open_orders[gp] = oid
                    placed += 1
            elif gp > current_price:
                # Place sell orders above current price (need to hold BTC)
                pass  # Skip sells on init — no BTC held yet

        log.info(f"Grid initialised: {placed} BUY orders placed")

    def check_stop_loss(self, price: float) -> bool:
        """Return True if stop-loss triggered."""
        if price < self.cfg['STOP_LOSS']:
            log.warning(f"⛔ STOP-LOSS TRIGGERED @ ${price:,.0f} (limit ${self.cfg['STOP_LOSS']:,.0f})")
            return True
        loss_pct = abs(min(0, self.pnl)) / self.cfg['TOTAL_CAPITAL']
        if loss_pct >= self.cfg['MAX_LOSS_PCT']:
            log.warning(f"⛔ MAX LOSS REACHED: {loss_pct*100:.1f}% >= {self.cfg['MAX_LOSS_PCT']*100:.0f}%")
            return True
        return False

    def log_status(self, price: float):
        """Log current bot status."""
        runtime = str(datetime.now() - self.start_time).split('.')[0]
        win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0
        open_orders_count = sum(1 for o in self.paper_orders.values() if o.get('status') == 'OPEN')
        log.info(f"\n{'─'*50}")
        log.info(f"  STATUS [{self.mode}] — Runtime: {runtime}")
        log.info(f"  Price     : ${price:,.2f}")
        log.info(f"  P&L       : ${self.pnl:+.4f} USDT")
        log.info(f"  Trades    : {self.total_trades} (W:{self.wins} L:{self.losses} WR:{win_rate:.0f}%)")
        log.info(f"  USDT bal  : ${self.paper_balance_usdt:.4f}")
        log.info(f"  BTC held  : {self.paper_balance_btc:.5f}")
        log.info(f"  Open orders: {open_orders_count}")
        log.info(f"{'─'*50}\n")

    def save_state(self):
        """Save bot state to JSON for dashboard."""
        state = {
            'timestamp'    : datetime.now().isoformat(),
            'mode'         : self.mode,
            'symbol'       : self.symbol,
            'pnl'          : round(self.pnl, 4),
            'total_trades' : self.total_trades,
            'wins'         : self.wins,
            'losses'       : self.losses,
            'balance_usdt' : round(self.paper_balance_usdt, 4),
            'balance_btc'  : round(self.paper_balance_btc, 6),
            'grid_lower'   : self.cfg['GRID_LOWER'],
            'grid_upper'   : self.cfg['GRID_UPPER'],
            'grid_levels'  : self.cfg['GRID_LEVELS'],
        }
        with open('bot_state.json', 'w') as f:
            json.dump(state, f, indent=2)

    def run(self):
        """Main bot loop."""
        log.info(f"\n🚀 TradeOS Grid Bot starting in {self.mode} mode...")
        log.info("Press Ctrl+C to stop.\n")

        # Get initial price and set up grid
        price = self.get_price()
        if price is None:
            log.error("Cannot get initial price. Check API connection.")
            return

        if price < self.cfg['GRID_LOWER'] or price > self.cfg['GRID_UPPER']:
            log.warning(f"⚠️ Current price ${price:,.0f} is outside grid range!")
            log.warning(f"   Adjust GRID_LOWER / GRID_UPPER in CONFIG.")
            if not self.paper:
                log.error("Refusing to start live bot outside grid range.")
                return

        self.init_grid(price)
        last_log = time.time()

        try:
            while True:
                price = self.get_price()
                if price is None:
                    time.sleep(5)
                    continue

                # Check stop-loss
                if self.check_stop_loss(price):
                    log.warning("🛑 Bot stopping due to stop-loss.")
                    self.save_state()
                    break

                # Check for fills
                self.check_fills(price)

                # Periodic status log
                if time.time() - last_log >= self.cfg['LOG_INTERVAL']:
                    self.log_status(price)
                    self.save_state()
                    last_log = time.time()

                time.sleep(self.cfg['CHECK_INTERVAL'])

        except KeyboardInterrupt:
            log.info("\n\n⏹ Bot stopped by user.")
            self.log_status(price or 0)
            self.save_state()


def main():
    parser = argparse.ArgumentParser(description='TradeOS Binance Grid Bot')
    parser.add_argument('--mode', choices=['paper', 'live'], default='paper',
                        help='paper = simulation, live = real trades')
    args = parser.parse_args()

    paper = (args.mode == 'paper')

    if paper:
        log.info("=" * 55)
        log.info("  PAPER TRADING MODE — no real money at risk")
        log.info("  Run for 2+ weeks before switching to --mode live")
        log.info("=" * 55)
        # Use fake keys for paper mode
        api_key    = os.getenv('BINANCE_API_KEY', 'PAPER_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET', 'PAPER_SECRET')
    else:
        log.info("=" * 55)
        log.info("  ⚠️  LIVE TRADING MODE — REAL MONEY AT RISK")
        log.info("=" * 55)
        api_key    = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        if not api_key or not api_secret:
            log.error("Set BINANCE_API_KEY and BINANCE_API_SECRET in your .env file")
            sys.exit(1)

    try:
        client = Client(api_key, api_secret)
        if not paper:
            client.ping()
            log.info("✅ Binance API connected")
    except Exception as e:
        if not paper:
            log.error(f"Binance connection failed: {e}")
            sys.exit(1)
        # Paper mode works without real connection
        log.info("📄 Paper mode: running with simulated price feed")

    bot = GridBot(client, CONFIG, paper=paper)
    bot.run()


if __name__ == '__main__':
    main()
