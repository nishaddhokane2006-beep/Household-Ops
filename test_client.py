"""
test_client.py – Quick smoke-test for every MCP tool.

Usage (with MCP server already running on localhost:8000):
    python test_client.py

Pass to confirm before recording your demo video.
All assertions print ✅ on success or ❌ with details on failure.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, timedelta

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = "http://localhost:8000/mcp"


async def call(session: ClientSession, tool: str, **kwargs):
    result = await session.call_tool(tool, kwargs)
    if result.content and hasattr(result.content[0], "text"):
        try:
            return json.loads(result.content[0].text)
        except Exception:
            return result.content[0].text
    return result


def ok(label: str, condition: bool, detail: str = "") -> None:
    icon = "✅" if condition else "❌"
    suffix = f" – {detail}" if detail else ""
    print(f"  {icon}  {label}{suffix}")
    if not condition:
        # Don't exit – show all failures
        pass


async def run_tests():
    print(f"\n🔗  Connecting to {MCP_URL} …\n")

    async with streamable_http_client(MCP_URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()

            # --- list tools ---
            tools_result = await s.list_tools()
            tool_names   = [t.name for t in tools_result.tools]
            print("📦  Available tools:", ", ".join(tool_names))
            ok("6 tools registered", len(tool_names) >= 6, str(len(tool_names)))

            # --- add_pantry_item ---
            print("\n── add_pantry_item ──")
            r1 = await call(s, "add_pantry_item", name="test_apple", quantity=5, unit="pcs",
                            expires=(date.today() + timedelta(days=2)).isoformat())
            ok("status is added/updated", r1.get("status") in ("added", "updated"))
            ok("item name returned",      r1.get("item") == "test_apple")

            # Update same item
            r2 = await call(s, "add_pantry_item", name="test_apple", quantity=10, unit="pcs")
            ok("upsert: status=updated", r2.get("status") == "updated")

            # Bad quantity
            r3 = await call(s, "add_pantry_item", name="bad", quantity=-1)
            ok("rejects qty < 0",        "error" in r3)

            # Bad date
            r4 = await call(s, "add_pantry_item", name="bad", quantity=1, expires="not-a-date")
            ok("rejects bad date",       "error" in r4)

            # --- check_pantry ---
            print("\n── check_pantry ──")
            r5 = await call(s, "check_pantry")
            ok("returns items list",     isinstance(r5.get("items"), list))
            ok("total > 0",              r5.get("total", 0) > 0)

            r6 = await call(s, "check_pantry", filter="expiring")
            ok("expiring filter works",  isinstance(r6.get("expiring_soon"), list))

            r7 = await call(s, "check_pantry", filter="egg")
            ok("name filter works",      all("egg" in i["name"] for i in r7["items"]))

            # --- suggest_meals ---
            print("\n── suggest_meals ──")
            r8 = await call(s, "suggest_meals")
            ok("returns suggestions",    isinstance(r8.get("suggestions"), list))
            ok("at least 1 suggestion",  len(r8.get("suggestions", [])) > 0)
            first = r8["suggestions"][0]
            ok("suggestion has recipe",  "recipe" in first)
            ok("suggestion has can_make","can_make" in first)
            ok("suggestion has missing", "missing" in first)

            r9 = await call(s, "suggest_meals", dietary_preference="vegetarian")
            ok("veg filter applied",     r9.get("preference_applied") == "vegetarian")

            # --- build_shopping_list ---
            print("\n── build_shopping_list ──")
            r10 = await call(s, "build_shopping_list", recipe_names=["Pasta Aglio e Olio"])
            ok("returns shopping_list",  isinstance(r10.get("shopping_list"), list))
            ok("added items list",       isinstance(r10.get("added"), list))

            r11 = await call(s, "build_shopping_list", recipe_names=["NONEXISTENT RECIPE"])
            ok("reports unknown recipe", "NONEXISTENT RECIPE".lower() in
               [x.lower() for x in r11.get("recipes_not_found", [])])

            # --- add_bill ---
            print("\n── add_bill ──")
            due = (date.today() + timedelta(days=7)).isoformat()
            r12 = await call(s, "add_bill", name="Test Bill", amount=999.0, due_date=due)
            ok("bill saved",             r12.get("status") == "saved")
            ok("amount echoed",          r12.get("amount") == 999.0)

            r13 = await call(s, "add_bill", name="Bad Bill", amount=0, due_date=due)
            ok("rejects amount=0",       "error" in r13)

            r14 = await call(s, "add_bill", name="Bad Bill", amount=100, due_date="bad-date")
            ok("rejects bad due_date",   "error" in r14)

            # --- upcoming_bills ---
            print("\n── upcoming_bills ──")
            r15 = await call(s, "upcoming_bills", days_ahead=30)
            ok("returns bills list",     isinstance(r15.get("bills"), list))
            ok("total field present",    "total" in r15)

            r16 = await call(s, "upcoming_bills", days_ahead=0)
            ok("0-day window ok",        isinstance(r16.get("bills"), list))

            r17 = await call(s, "upcoming_bills", days_ahead=-1)
            ok("rejects negative days",  "error" in r17)

            # --- resource ---
            print("\n── resource: pantry://shopping-list ──")
            resources = await s.list_resources()
            uris = [str(r.uri) for r in resources.resources]
            ok("shopping-list resource exists", any("shopping-list" in u for u in uris))

            # --- prompt ---
            print("\n── prompt: weekly_review ──")
            prompts = await s.list_prompts()
            p_names = [p.name for p in prompts.prompts]
            ok("weekly_review prompt exists", "weekly_review" in p_names)

    print("\n" + "─" * 48)
    print("  Test run complete.")


if __name__ == "__main__":
    asyncio.run(run_tests())
