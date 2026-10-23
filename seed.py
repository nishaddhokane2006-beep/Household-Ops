"""
seed.py – Populate the database with realistic demo data.
Run this before every recording to get a clean, reproducible state.

Usage:
    python seed.py
"""
import sqlite3
from datetime import date, timedelta
from database import get_conn, init_db, DB_PATH

# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #
def today_plus(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def run_seed() -> None:
    # Wipe existing data
    init_db()
    with get_conn() as conn:
        conn.execute("DELETE FROM pantry")
        conn.execute("DELETE FROM bills")
        conn.execute("DELETE FROM shopping")

        # ------------------------------------------------------------------- #
        #  Pantry – mix of fresh, about-to-expire and long-shelf items         #
        # ------------------------------------------------------------------- #
        pantry_rows = [
            # name,                qty,   unit,    expires
            ("eggs",               24,    "pcs",   today_plus(3)),   # ← expiring soon
            ("milk",               1000,  "ml",    today_plus(2)),   # ← expiring soon
            ("banana",             4,     "pcs",   today_plus(1)),   # ← very soon!
            ("bread",              1,     "loaf",  today_plus(4)),   # ← expiring soon
            ("tomato",             6,     "pcs",   today_plus(5)),
            ("onion",              3,     "pcs",   None),
            ("garlic",             8,     "cloves",None),
            ("ginger",             1,     "tsp",   None),
            ("rice",               1000,  "g",     None),
            ("red lentils",        500,   "g",     None),
            ("cumin seeds",        50,    "g",     None),
            ("turmeric",           30,    "g",     None),
            ("oil",                500,   "ml",    None),
            ("salt",               200,   "g",     None),
            ("soy sauce",          150,   "ml",    today_plus(90)),
            ("butter",             100,   "g",     today_plus(14)),
            ("oats",               400,   "g",     None),
            ("honey",              250,   "g",     None),
            ("feta cheese",        100,   "g",     today_plus(6)),
            ("cucumber",           1,     "pcs",   today_plus(5)),
            ("bell pepper",        2,     "pcs",   today_plus(5)),
            ("lemon",              3,     "pcs",   today_plus(10)),
            ("chilli flakes",      20,    "g",     None),
        ]
        conn.executemany(
            "INSERT INTO pantry (name, qty, unit, expires) VALUES (?, ?, ?, ?)",
            pantry_rows,
        )

        # ------------------------------------------------------------------- #
        #  Bills                                                               #
        # ------------------------------------------------------------------- #
        bills_rows = [
            # name,              amount,   due
            ("Electricity Bill", 1800.00,  today_plus(5)),
            ("Internet Bill",    999.00,   today_plus(12)),
            ("Water Bill",       650.00,   today_plus(20)),
        ]
        conn.executemany(
            "INSERT INTO bills (name, amount, due) VALUES (?, ?, ?)",
            bills_rows,
        )

        # Shopping list starts empty – tools will populate it
        pantry_count = conn.execute("SELECT COUNT(*) FROM pantry").fetchone()[0]
        bills_count  = conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0]

    print(f"[OK] Database seeded: {pantry_count} pantry items, {bills_count} bills.")
    print(f"     DB path: {DB_PATH}")


if __name__ == "__main__":
    run_seed()
