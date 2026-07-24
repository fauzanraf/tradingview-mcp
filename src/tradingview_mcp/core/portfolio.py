import sqlite3
import os
from typing import Dict, List, Optional, Any

# Store the DB in the user's home directory or current directory
DB_DIR = os.path.expanduser("~/.tradingview_mcp_data")
DB_PATH = os.path.join(DB_DIR, "portfolio.db")

# Starting virtual capital per currency for a new user.
# See docs/adr/0002-per-currency-cash-balances.md for why balances are
# tracked per currency instead of a single balance converted at trade time.
DEFAULT_BALANCES = {"USD": 1000.0, "IDR": 15_000_000.0}


def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # One row per (user, currency) cash balance
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS balances (
        user_id TEXT NOT NULL,
        currency TEXT NOT NULL,
        amount REAL NOT NULL,
        PRIMARY KEY (user_id, currency)
    )
    ''')

    # Table for active positions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        quantity REAL NOT NULL,
        average_price REAL NOT NULL,
        currency TEXT NOT NULL,
        side TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Table for trade history/logs
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trade_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        quantity REAL NOT NULL,
        price REAL NOT NULL,
        currency TEXT NOT NULL,
        side TEXT NOT NULL,  -- 'BUY' or 'SELL'
        realized_pnl REAL DEFAULT 0,
        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()


def get_or_create_balances(user_id: str) -> Dict[str, float]:
    """Return {currency: amount} for the user, seeding defaults on first use."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT currency, amount FROM balances WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()

    if not rows:
        for currency, amount in DEFAULT_BALANCES.items():
            cursor.execute(
                "INSERT INTO balances (user_id, currency, amount) VALUES (?, ?, ?)",
                (user_id, currency, amount),
            )
        conn.commit()
        balances = dict(DEFAULT_BALANCES)
    else:
        balances = {currency: amount for currency, amount in rows}

    conn.close()
    return balances


def _get_balance(cursor, user_id: str, currency: str) -> float:
    cursor.execute(
        "SELECT amount FROM balances WHERE user_id = ? AND currency = ?", (user_id, currency)
    )
    row = cursor.fetchone()
    if row is not None:
        return row[0]
    default = DEFAULT_BALANCES.get(currency, 0.0)
    cursor.execute(
        "INSERT INTO balances (user_id, currency, amount) VALUES (?, ?, ?)",
        (user_id, currency, default),
    )
    return default


def _set_balance(cursor, user_id: str, currency: str, amount: float) -> None:
    cursor.execute(
        "UPDATE balances SET amount = ? WHERE user_id = ? AND currency = ?",
        (amount, user_id, currency),
    )


def execute_trade(
    user_id: str,
    symbol: str,
    quantity: float,
    current_price: float,
    side: str,
    currency: str = "USD",
) -> Dict[str, Any]:
    """Execute a simulated trade (BUY or SELL) for a user, settled in `currency`."""
    symbol = symbol.upper()
    side = side.upper()
    currency = currency.upper()

    if side not in ['BUY', 'SELL']:
        return {"error": "Side must be 'BUY' or 'SELL'"}

    if quantity <= 0:
        return {"error": "Quantity must be greater than 0"}

    # Ensure the user's balances exist (seeds defaults on first use)
    get_or_create_balances(user_id)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        if side == 'BUY':
            balance = _get_balance(cursor, user_id, currency)
            cost = quantity * current_price
            if balance < cost:
                return {
                    "error": f"Insufficient {currency} balance. Required: {cost:.2f}, Available: {balance:.2f}"
                }

            new_balance = balance - cost
            _set_balance(cursor, user_id, currency, new_balance)

            # Check if position exists to average down, else create new
            cursor.execute(
                "SELECT id, quantity, average_price FROM positions WHERE user_id = ? AND symbol = ?",
                (user_id, symbol),
            )
            pos = cursor.fetchone()

            if pos:
                pos_id, existing_qty, existing_avg_price = pos
                new_qty = existing_qty + quantity
                new_avg_price = ((existing_qty * existing_avg_price) + (quantity * current_price)) / new_qty
                cursor.execute(
                    "UPDATE positions SET quantity = ?, average_price = ? WHERE id = ?",
                    (new_qty, new_avg_price, pos_id),
                )
            else:
                cursor.execute(
                    "INSERT INTO positions (user_id, symbol, quantity, average_price, currency, side) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, symbol, quantity, current_price, currency, "LONG"),
                )

            cursor.execute(
                "INSERT INTO trade_history (user_id, symbol, quantity, price, currency, side) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, symbol, quantity, current_price, currency, 'BUY'),
            )

            conn.commit()
            return {
                "status": "success",
                "action": "BUY",
                "symbol": symbol,
                "quantity": quantity,
                "price": current_price,
                "currency": currency,
                "total_cost": cost,
                "remaining_balance": new_balance,
            }

        elif side == 'SELL':
            cursor.execute(
                "SELECT id, quantity, average_price FROM positions WHERE user_id = ? AND symbol = ?",
                (user_id, symbol),
            )
            pos = cursor.fetchone()

            if not pos:
                return {"error": f"You do not own any {symbol}"}

            pos_id, existing_qty, existing_avg_price = pos

            if quantity > existing_qty:
                return {"error": f"Cannot sell {quantity} of {symbol}. You only own {existing_qty}."}

            revenue = quantity * current_price
            realized_pnl = (current_price - existing_avg_price) * quantity

            balance = _get_balance(cursor, user_id, currency)
            new_balance = balance + revenue
            _set_balance(cursor, user_id, currency, new_balance)

            new_qty = existing_qty - quantity
            if new_qty <= 0.00001:  # Floating point safety
                cursor.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
            else:
                cursor.execute("UPDATE positions SET quantity = ? WHERE id = ?", (new_qty, pos_id))

            cursor.execute(
                "INSERT INTO trade_history (user_id, symbol, quantity, price, currency, side, realized_pnl) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, symbol, quantity, current_price, currency, 'SELL', realized_pnl),
            )

            conn.commit()
            return {
                "status": "success",
                "action": "SELL",
                "symbol": symbol,
                "quantity": quantity,
                "price": current_price,
                "currency": currency,
                "revenue": revenue,
                "realized_pnl": realized_pnl,
                "new_balance": new_balance,
            }

    except Exception as e:
        conn.rollback()
        return {"error": f"Database error during trade: {str(e)}"}
    finally:
        conn.close()


def get_portfolio(user_id: str) -> Dict[str, Any]:
    """Retrieve the user's current portfolio (per-currency balances and open positions)."""
    balances = get_or_create_balances(user_id)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT symbol, quantity, average_price, currency FROM positions WHERE user_id = ?",
        (user_id,),
    )
    rows = cursor.fetchall()

    positions = []
    for row in rows:
        positions.append({
            "symbol": row["symbol"],
            "quantity": row["quantity"],
            "average_price": row["average_price"],
            "currency": row["currency"],
        })

    conn.close()

    return {
        "user_id": user_id,
        "balances": balances,
        "positions": positions,
    }


def get_trade_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve the user's most recent trades, newest first."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT symbol, quantity, price, currency, side, realized_pnl, executed_at "
        "FROM trade_history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# Initialize DB when module is imported
init_db()
