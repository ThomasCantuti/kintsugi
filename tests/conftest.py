import asyncio
import os

# Tests use their own database on the local dev deployment (`atlas local`), never the live one.
os.environ["MONGODB_URI"] = os.environ.get("TEST_MONGODB_URI", "mongodb://localhost:59283/?directConnection=true")
os.environ["DB_NAME"] = "kintsugi_test"

import pytest  # noqa: E402

_loop = asyncio.new_event_loop()  # one loop for all tests: the Mongo client binds to it


@pytest.fixture
def run():
    from kintsugi import db, genome

    _loop.run_until_complete(db.client.drop_database("kintsugi_test"))
    _loop.run_until_complete(db.setup())
    genome._current = None
    return _loop.run_until_complete
