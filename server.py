"""
server.py – Household Ops MCP Server (spec 2025-11-25, Streamable HTTP transport).

Tools exposed:
  1. add_pantry_item     – add or update a pantry entry
  2. check_pantry        – list items, optionally filter by name or expiry
  3. suggest_meals       – rank recipes by how many ingredients are in-pantry
  4. build_shopping_list – create the shopping list for chosen recipes
  5. add_bill            – store a bill reminder
  6. upcoming_bills      – list bills due within N days

Resource:
  pantry://shopping-list  – read-only live view of the current shopping list

Prompt:
  weekly-review – reusable weekly household review template

Run:
    python server.py
    # or:
    uv run mcp run server.py --transport streamable-http

Inspector test:
    npx @modelcontextprotocol/inspector http://localhost:8000/mcp
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from database import get_conn, init_db

# --------------------------------------------------------------------------- #
#  Initialise                                                                   #
# --------------------------------------------------------------------------- #
RECIPES_PATH = Path(__file__).parent / "recipes.json"
EXPIRY_WARN_DAYS = int(os.getenv("EXPIRY_WARN_DAYS", "5"))  # flag items within N days

with open(RECIPES_PATH, encoding="utf-8") as fh:
    RECIPES: list[dict] = json.load(fh)

init_db()  # create tables on cold start

mcp = FastMCP("household-ops")


# =========================================================================== #
#  TOOLS                                                                        #
# =========================================================================== #

@mcp.tool()
def add_pantry_item(
    name: str,
    quantity: float,
    unit: str = "pcs",
    expires: str = "",
) -> dict:
    """
    Add a new pantry item or update an existing one.

    Args:
        name:     Item name, e.g. 'eggs', 'milk', 'garlic'. Case-insensitive.
        quantity: How much you have, e.g. 12 (eggs) or 500 (grams of flour).
        unit:     Unit of measurement, e.g. 'pcs', 'g', 'ml', 'kg', 'L'.
                  Defaults to 'pcs'.
        expires:  Optional expiry date in YYYY-MM-DD format.
                  Leave empty if the item has no expiry (e.g. salt, oil).

    Returns:
        {"status": "added"|"updated", "item": name, "qty": quantity,
         "unit": unit, "expires": expires_or_null}
    """
    name = name.strip().lower()
    if not name:
        return {"error": "Item name cannot be empty."}
    if quantity <= 0:
        return {"error": "Quantity must be greater than zero."}

    expires_val: Optional[str] = expires.strip() if expires.strip() else None
    if expires_val:
        try:
            date.fromisoformat(expires_val)
        except ValueError:
            return {"error": f"Invalid date '{expires_val}'. Use YYYY-MM-DD format."}

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM pantry WHERE name = ?", (name,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE pantry SET qty = ?, unit = ?, expires = ? WHERE name = ?",
                (quantity, unit, expires_val, name),
            )
            status = "updated"
        else:
            conn.execute(
                "INSERT INTO pantry (name, qty, unit, expires) VALUES (?, ?, ?, ?)",
                (name, quantity, unit, expires_val),
            )
            status = "added"

    return {
        "status": status,
        "item": name,
        "qty": quantity,
        "unit": unit,
        "expires": expires_val,
    }


@mcp.tool()
def check_pantry(filter: str = "") -> dict:
    """
    List current pantry contents.

    Args:
        filter: Optional. 'expiring' to show only items expiring within the
                next 5 days. A word like 'egg' to search by name. Leave empty
                to list everything.

    Returns:
        {"items": [...], "expiring_soon": [...], "total": int}
        Each item: {"name", "qty", "unit", "expires", "days_left": int|null,
                    "expiring_soon": bool}
    """
    today = date.today()
    warn_cutoff = today + timedelta(days=EXPIRY_WARN_DAYS)
    filter_lower = filter.strip().lower()

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name, qty, unit, expires FROM pantry ORDER BY expires ASC, name ASC"
        ).fetchall()

    items: list[dict] = []
    for row in rows:
        days_left: Optional[int] = None
        expiring = False
        if row["expires"]:
            exp_date = date.fromisoformat(row["expires"])
            days_left = (exp_date - today).days
            expiring = exp_date <= warn_cutoff

        entry = {
            "name": row["name"],
            "qty": row["qty"],
            "unit": row["unit"],
            "expires": row["expires"],
            "days_left": days_left,
            "expiring_soon": expiring,
        }
        items.append(entry)

    # Apply filter
    if filter_lower == "expiring":
        items = [i for i in items if i["expiring_soon"]]
    elif filter_lower:
        items = [i for i in items if filter_lower in i["name"]]

    expiring_soon = [i for i in items if i["expiring_soon"]]

    return {
        "items": items,
        "expiring_soon": expiring_soon,
        "total": len(items),
    }


@mcp.tool()
def suggest_meals(dietary_preference: str = "") -> dict:
    """
    Suggest recipes ranked by how many ingredients you already have.
    Heavily favours recipes that use up items expiring soon.

    Args:
        dietary_preference: Optional tag to filter by, e.g. 'vegetarian',
                            'vegan', 'non-veg', 'Indian', 'quick', 'breakfast'.
                            Leave empty for all recipes.

    Returns:
        {"suggestions": [...], "preference_applied": str}
        Each suggestion: {"recipe", "can_make": bool, "have": [...],
                          "missing": [...], "score": int,
                          "uses_expiring": [...]}
    """
    today = date.today()
    warn_cutoff = today + timedelta(days=EXPIRY_WARN_DAYS)
    pref = dietary_preference.strip().lower()

    with get_conn() as conn:
        rows = conn.execute("SELECT name, qty, expires FROM pantry").fetchall()

    pantry_qty:    dict[str, float] = {r["name"]: r["qty"] for r in rows}
    pantry_expiry: dict[str, Optional[str]] = {r["name"]: r["expires"] for r in rows}

    results = []
    for recipe in RECIPES:
        # Filter by dietary preference tag
        if pref and pref not in [t.lower() for t in recipe.get("tags", [])]:
            continue

        have:          list[str] = []
        missing:       list[str] = []
        uses_expiring: list[str] = []

        for ing in recipe["ingredients"]:
            item_name = ing["item"].lower()
            if item_name in pantry_qty and pantry_qty[item_name] > 0:
                have.append(item_name)
                exp = pantry_expiry.get(item_name)
                if exp and date.fromisoformat(exp) <= warn_cutoff:
                    uses_expiring.append(item_name)
            else:
                missing.append(item_name)

        can_make = len(missing) == 0
        # Score: base points for ingredients in pantry + bonus for using expiring items
        score = (len(have) * 2) + (len(uses_expiring) * 5)

        results.append({
            "recipe":        recipe["name"],
            "can_make":      can_make,
            "have":          have,
            "missing":       missing,
            "uses_expiring": uses_expiring,
            "score":         score,
            "tags":          recipe.get("tags", []),
        })

    # Sort: can_make first, then by score descending
    results.sort(key=lambda r: (not r["can_make"], -r["score"]))

    return {
        "suggestions":          results[:8],  # top 8
        "preference_applied":   dietary_preference or "none",
    }


@mcp.tool()
def build_shopping_list(recipe_names: list[str]) -> dict:
    """
    Build or extend the shopping list with missing ingredients for the given recipes.
    Compares each ingredient against the pantry and stores only what is missing.

    Args:
        recipe_names: One or more recipe names exactly as returned by suggest_meals,
                      e.g. ["Dal Tadka", "Egg Fried Rice"].

    Returns:
        {"added": [...], "already_in_pantry": [...], "shopping_list": [...],
         "recipes_not_found": [...]}
    """
    recipe_names_lower = [r.strip().lower() for r in recipe_names]
    recipe_map = {r["name"].lower(): r for r in RECIPES}

    found_recipes = []
    not_found = []
    for rn in recipe_names_lower:
        if rn in recipe_map:
            found_recipes.append(recipe_map[rn])
        else:
            not_found.append(rn)

    with get_conn() as conn:
        pantry_rows = conn.execute("SELECT name, qty FROM pantry").fetchall()
        pantry_qty = {r["name"]: r["qty"] for r in pantry_rows}

        added:             list[str] = []
        already_in_pantry: list[str] = []

        for recipe in found_recipes:
            for ing in recipe["ingredients"]:
                item_name = ing["item"].lower()
                if item_name in pantry_qty and pantry_qty[item_name] > 0:
                    already_in_pantry.append(item_name)
                else:
                    # Upsert into shopping list
                    conn.execute(
                        """
                        INSERT INTO shopping (item, qty, unit)
                        VALUES (?, ?, ?)
                        ON CONFLICT(item) DO UPDATE SET qty = MAX(shopping.qty, excluded.qty)
                        """,
                        (item_name, ing["qty"], ing["unit"]),
                    )
                    if item_name not in added:
                        added.append(item_name)

        shopping_list = [
            {"item": r["item"], "qty": r["qty"], "unit": r["unit"]}
            for r in conn.execute("SELECT item, qty, unit FROM shopping ORDER BY item").fetchall()
        ]

    return {
        "added":               added,
        "already_in_pantry":   list(set(already_in_pantry)),
        "shopping_list":       shopping_list,
        "recipes_not_found":   not_found,
    }


@mcp.tool()
def add_bill(name: str, amount: float, due_date: str) -> dict:
    """
    Store a bill reminder.

    Args:
        name:     Name of the bill, e.g. 'Electricity Bill', 'Internet'.
        amount:   Amount due, e.g. 1800.00 (currency-agnostic).
        due_date: Due date in YYYY-MM-DD format, e.g. '2026-10-28'.

    Returns:
        {"status": "saved", "bill": name, "amount": amount, "due": due_date}
    """
    name = name.strip()
    if not name:
        return {"error": "Bill name cannot be empty."}
    if amount <= 0:
        return {"error": "Amount must be greater than zero."}
    try:
        date.fromisoformat(due_date.strip())
    except ValueError:
        return {"error": f"Invalid due_date '{due_date}'. Use YYYY-MM-DD format."}

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO bills (name, amount, due) VALUES (?, ?, ?)",
            (name, amount, due_date.strip()),
        )

    return {
        "status": "saved",
        "bill":   name,
        "amount": amount,
        "due":    due_date.strip(),
    }


@mcp.tool()
def upcoming_bills(days_ahead: int = 30) -> dict:
    """
    List bills due within the next N days, sorted by due date.

    Args:
        days_ahead: How many days to look ahead. Defaults to 30.
                    Use 7 for 'this week', 3 for 'very soon'.

    Returns:
        {"bills": [...], "total": int, "days_checked": days_ahead}
        Each bill: {"name", "amount", "due", "days_left": int}
    """
    if days_ahead < 0:
        return {"error": "days_ahead must be a non-negative integer."}

    today    = date.today()
    cutoff   = today + timedelta(days=days_ahead)
    today_s  = today.isoformat()
    cutoff_s = cutoff.isoformat()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT name, amount, due
            FROM   bills
            WHERE  due BETWEEN ? AND ?
            ORDER  BY due ASC
            """,
            (today_s, cutoff_s),
        ).fetchall()

    bills = [
        {
            "name":      r["name"],
            "amount":    r["amount"],
            "due":       r["due"],
            "days_left": (date.fromisoformat(r["due"]) - today).days,
        }
        for r in rows
    ]

    return {
        "bills":        bills,
        "total":        len(bills),
        "days_checked": days_ahead,
    }


# =========================================================================== #
#  RESOURCE – read-only shopping list                                           #
# =========================================================================== #

@mcp.resource("pantry://shopping-list")
def get_shopping_list() -> str:
    """
    Current shopping list as plain text.
    Read-only resource – updated automatically as build_shopping_list adds items.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT item, qty, unit FROM shopping ORDER BY item"
        ).fetchall()

    if not rows:
        return "Shopping list is empty."

    lines = ["# Shopping List", ""]
    for row in rows:
        lines.append(f"- {row['qty']} {row['unit']} of {row['item']}")
    return "\n".join(lines)


# =========================================================================== #
#  PROMPT – weekly household review template                                    #
# =========================================================================== #

@mcp.prompt()
def weekly_review() -> str:
    """
    Reusable weekly household review prompt.
    Guides the assistant to check expiry, suggest a weekly meal plan,
    update the shopping list, and review upcoming bills.
    """
    return (
        "You are a helpful household assistant. Please do the following for me:\n"
        "1. Check my pantry for items expiring within the next 5 days and list them.\n"
        "2. Suggest 3 meals I can make this week that use up expiring ingredients first.\n"
        "3. Build a consolidated shopping list for those 3 meals.\n"
        "4. Show me any bills due in the next 14 days.\n"
        "Provide a friendly, concise summary at the end."
    )


# =========================================================================== #
#  Entry point                                                                  #
# =========================================================================== #

if __name__ == "__main__":
    import uvicorn

    # FastMCP creates a Starlette/ASGI app for streamable-http transport.
    # Default endpoint: http://localhost:8000/mcp
    mcp.run(transport="streamable-http")
