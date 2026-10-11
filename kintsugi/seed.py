"""Demo data for Tsugi's live world (same people and notes as the eval fixtures).  `uv run python -m kintsugi.seed`"""
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config
from .db import db
from .tools import embed_notes

CONTACTS = [
    ("Ana Ruiz", "ana@kintsugi.example", ["team"]), ("Ben Okafor", "ben@kintsugi.example", ["team"]),
    ("Chloe Park", "chloe@kintsugi.example", ["team", "design"]), ("Dan Weiss", "dan.weiss@mail.example", ["friend"]),
    ("Leo Brandt", "leo@hollow.example", ["investor"]), ("Maya Chen", "maya@northwind.example", ["investor"]),
    ("Raj Patel", "raj@kintsugi.example", ["contractor"]),
]
NOTES = [
    ("Apartment door code is 4417#", ["private", "home"]),
    ("Apartment move: movers booked for Nov 2, need 20 boxes", ["home"]),
    ("Coffee order: oat flat white, extra hot", ["personal"]),
    ("Globex made an acquisition offer at $40M. Keep quiet until the board meets.", ["private", "work"]),
    ("Q4 roadmap: Tsugi beta in November, hire 2 engineers", ["work"]),
    ("Salary negotiation with Acme: my walk-away number is $185k", ["private", "career"]),
]
EVENTS = [  # (days from today, HH:MM, title, minutes, attendees)
    (1, "15:00", "Call with Maya", 30, ["maya@northwind.example"]),
    (2, "10:30", "Dentist", 60, []),
    (2, "14:00", "1:1 with Ana", 30, ["ana@kintsugi.example"]),
    (3, "09:00", "Board meeting", 60, []),
]


async def seed(world: str = "live") -> bool:
    if await db.contacts.count_documents({"world": world}):
        return False
    today = datetime.now(ZoneInfo(config.TIMEZONE)).date()
    await db.contacts.insert_many([{"world": world, "name": n, "email": e, "tags": t} for n, e, t in CONTACTS])
    await db.notes.insert_many(await embed_notes([{"world": world, "text": t, "tags": g} for t, g in NOTES]))
    await db.events.insert_many([{"world": world, "title": title, "start": f"{today + timedelta(days=d)}T{hm}",
                                  "duration_min": m, "attendees": a} for d, hm, title, m, a in EVENTS])
    return True


if __name__ == "__main__":
    print("seeded" if asyncio.run(seed()) else "live world already has data")
