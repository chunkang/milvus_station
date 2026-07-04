"""Sample data import: create & seed a fixed set of demo tables.

This module powers ``POST /databases/{db}/samples/import``. It creates
four demonstration tables (``products``, ``articles``, ``movies`` and
``faqs``) in the *application* database and seeds each with realistic,
embeddable text rows so the data console / vector-index flow has content
to work with out of the box.

SECURITY & SCOPE
----------------
* The table set is FIXED and hard-coded here. No identifier ever comes
  from user input, so there is no SQL-injection surface: all DDL and the
  column lists are compile-time constants and every seed *value* is passed
  as a bound parameter via ``executemany``.
* Import is restricted to the configured application database
  (``settings.mariadb_db``, default ``"milvus_station"``). A request for
  any other schema is rejected with HTTP 400 before a connection is even
  opened, so this endpoint can never seed arbitrary schemas.

IDEMPOTENCY
-----------
Each table is created with ``CREATE TABLE IF NOT EXISTS``. Seed rows are
inserted only when the table is currently empty (``SELECT COUNT(*) == 0``),
so importing repeatedly never duplicates rows. The response reports
``created`` (whether the table did not exist before this call) and ``rows``
(the final ``COUNT(*)``).

TESTABILITY
-----------
Execution goes through :func:`app.console.get_connection`, which unit tests
monkeypatch with a fake connection/cursor so no live MariaDB is required.
"""

from __future__ import annotations

from typing import Any, Sequence

from fastapi import HTTPException

from . import console
from .config import Settings, get_settings

# Common table options: utf8mb4 so seed text is stored losslessly.
_TABLE_OPTS = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"


class SampleTable:
    """A fixed sample table: its DDL, insert column list and seed rows."""

    def __init__(
        self,
        name: str,
        create_sql: str,
        columns: Sequence[str],
        rows: Sequence[tuple[Any, ...]],
    ) -> None:
        self.name = name
        self.create_sql = create_sql
        self.columns = tuple(columns)
        self.rows = tuple(rows)

    def insert_sql(self) -> str:
        """Build the parameterised INSERT statement for this table.

        Column names are hard-coded constants (never user input); values
        are always passed as bound ``%s`` parameters.
        """
        cols = ", ".join(console.quote_ident(c) for c in self.columns)
        placeholders = ", ".join(["%s"] * len(self.columns))
        table = console.quote_ident(self.name)
        return f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"


# --------------------------------------------------------------------------
# products (~12 rows)
# --------------------------------------------------------------------------
_PRODUCTS = SampleTable(
    name="products",
    create_sql=(
        "CREATE TABLE IF NOT EXISTS `products` ("
        "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, "
        "name VARCHAR(255) NOT NULL, "
        "description TEXT NOT NULL, "
        "category VARCHAR(100), "
        "price DECIMAL(10,2), "
        "in_stock TINYINT(1) DEFAULT 1, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
        "PRIMARY KEY (id)"
        f") {_TABLE_OPTS}"
    ),
    columns=("name", "description", "category", "price", "in_stock"),
    rows=[
        (
            "Aurora Wireless Headphones",
            "Immersive over-ear headphones with active noise cancellation and "
            "a 40-hour battery, tuned for rich bass and crisp vocals.",
            "electronics",
            199.99,
            1,
        ),
        (
            "Nimbus Smart Thermostat",
            "Learns your daily routine and adjusts the temperature "
            "automatically, trimming energy bills while keeping every room "
            "comfortable.",
            "home",
            129.00,
            1,
        ),
        (
            "TrailBlazer Pro Running Shoes",
            "Lightweight trail runners with a grippy outsole and responsive "
            "foam midsole built to carry you comfortably over any terrain.",
            "apparel",
            89.95,
            1,
        ),
        (
            "Lumen Desk Lamp",
            "A minimalist LED desk lamp with adjustable warmth and brightness, "
            "plus a built-in USB-C port to keep your devices charged.",
            "home",
            45.50,
            1,
        ),
        (
            "The Quiet Tide",
            "A sweeping literary novel about family, memory, and the sea that "
            "critics are calling the standout debut of the year.",
            "books",
            18.99,
            1,
        ),
        (
            "Cascade Stainless Water Bottle",
            "A vacuum-insulated bottle that keeps drinks cold for 24 hours or "
            "hot for 12, with a leakproof lid made for busy commutes.",
            "home",
            29.99,
            1,
        ),
        (
            "Pixel 4K Action Camera",
            "A pocket-sized action camera that captures stunning 4K footage "
            "with rock-steady stabilization, waterproof to 10 meters.",
            "electronics",
            249.00,
            0,
        ),
        (
            "Meridian Merino Sweater",
            "A breathable merino wool sweater that regulates temperature "
            "year-round and layers effortlessly for work or weekends.",
            "apparel",
            74.00,
            1,
        ),
        (
            "GreenThumb Herb Garden Kit",
            "Everything you need to grow fresh basil, mint, and cilantro "
            "indoors, including self-watering pots and organic seeds.",
            "home",
            34.95,
            1,
        ),
        (
            "Cook Smart: 100 Weeknight Meals",
            "A practical cookbook packed with fast, wholesome recipes that turn "
            "everyday pantry staples into memorable dinners.",
            "books",
            24.50,
            1,
        ),
        (
            "Voltix Portable Power Bank",
            "A 20,000mAh power bank with fast charging and dual USB-C ports, "
            "enough to recharge a phone up to four times on a single charge.",
            "electronics",
            59.99,
            1,
        ),
        (
            "Summit Insulated Jacket",
            "A packable down jacket that delivers serious warmth without the "
            "bulk, ideal for cold commutes and mountain weekends alike.",
            "apparel",
            149.00,
            1,
        ),
    ],
)


# --------------------------------------------------------------------------
# articles (~10 rows)
# --------------------------------------------------------------------------
_ARTICLES = SampleTable(
    name="articles",
    create_sql=(
        "CREATE TABLE IF NOT EXISTS `articles` ("
        "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, "
        "title VARCHAR(255) NOT NULL, "
        "body TEXT NOT NULL, "
        "author VARCHAR(120), "
        "tags VARCHAR(255), "
        "published_at DATE, "
        "PRIMARY KEY (id)"
        f") {_TABLE_OPTS}"
    ),
    columns=("title", "body", "author", "tags", "published_at"),
    rows=[
        (
            "Open-Source Model Rivals the Giants",
            "A new open-source language model released this week matches the "
            "performance of far larger commercial systems on common "
            "benchmarks. Researchers say the compact design could bring "
            "advanced AI to devices that run entirely offline.",
            "Dana Weber",
            "tech,ai,open-source",
            "2026-02-11",
        ),
        (
            "Astronomers Map a Hidden Ocean World",
            "Using data from a long-running space telescope, scientists have "
            "identified strong evidence of a liquid ocean beneath the icy "
            "crust of a distant moon. The discovery renews interest in the "
            "search for life beyond Earth.",
            "Priya Nair",
            "science,space,astronomy",
            "2026-01-29",
        ),
        (
            "A Slow Train Through the Alps",
            "There is no faster way to fall in love with a mountain range than "
            "to cross it by rail. Our writer spent five days riding scenic "
            "lines between quiet villages, trading speed for sweeping views "
            "and unhurried afternoons.",
            "Marco Ferretti",
            "travel,europe,rail",
            "2026-03-04",
        ),
        (
            "The Comeback of the Home-Cooked Loaf",
            "Home baking never really went away, but a fresh generation of "
            "cooks is rediscovering the simple pleasure of bread. We break "
            "down the handful of ingredients and the patience it takes to "
            "pull a golden loaf from your own oven.",
            "Helen Brooks",
            "food,baking,recipes",
            "2026-02-22",
        ),
        (
            "What Rising Rates Mean for Your Savings",
            "As central banks hold interest rates steady, savers finally have "
            "options that outpace inflation. Here is a plain-language guide to "
            "where your cash can work harder without taking on undue risk.",
            "Samuel Osei",
            "finance,personal-finance,savings",
            "2026-01-15",
        ),
        (
            "Tiny Sensors, Greener Cities",
            "Low-cost air-quality sensors are quietly reshaping how cities "
            "respond to pollution. By mapping problem areas block by block, "
            "planners can target traffic changes and green spaces where they "
            "matter most.",
            "Lena Fischer",
            "tech,environment,cities",
            "2026-03-18",
        ),
        (
            "The Physics of a Perfect Cup of Coffee",
            "Why does one pour-over taste bright and another taste bitter? It "
            "comes down to temperature, grind size, and time. We visited a lab "
            "that studies extraction to explain the science in your morning "
            "routine.",
            "Toby Grant",
            "science,food,coffee",
            "2026-02-06",
        ),
        (
            "Working Remotely From a Small Island",
            "With a laptop and a reliable connection, a growing number of "
            "professionals are trading city apartments for island life. We "
            "look at the practical trade-offs, from time zones to community, "
            "for anyone tempted to make the leap.",
            "Aisha Rahman",
            "travel,remote-work,lifestyle",
            "2026-03-11",
        ),
        (
            "A Simple Budget That Actually Sticks",
            "Most budgets fail because they are too complicated to follow. "
            "This approach uses three broad categories and a single monthly "
            "check-in, making it easy to see where your money goes without "
            "tracking every receipt.",
            "Samuel Osei",
            "finance,budgeting,how-to",
            "2026-01-08",
        ),
        (
            "Robots Learn to Fold the Laundry",
            "A research team has trained a general-purpose robot to handle "
            "soft, unpredictable objects like clothing. The advance hints at a "
            "future where household chores are shared with capable machines.",
            "Dana Weber",
            "tech,ai,robotics",
            "2026-02-27",
        ),
    ],
)


# --------------------------------------------------------------------------
# movies (~12 rows)
# --------------------------------------------------------------------------
_MOVIES = SampleTable(
    name="movies",
    create_sql=(
        "CREATE TABLE IF NOT EXISTS `movies` ("
        "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, "
        "title VARCHAR(255) NOT NULL, "
        "overview TEXT NOT NULL, "
        "genre VARCHAR(100), "
        "year INT, "
        "rating DECIMAL(3,1), "
        "PRIMARY KEY (id)"
        f") {_TABLE_OPTS}"
    ),
    columns=("title", "overview", "genre", "year", "rating"),
    rows=[
        (
            "The Shawshank Redemption",
            "A banker sentenced to life in prison forms an enduring friendship "
            "and quietly holds on to hope over two long decades behind bars.",
            "Drama",
            1994,
            9.3,
        ),
        (
            "Inception",
            "A thief who steals corporate secrets through dream-sharing "
            "technology is offered a chance to erase his past by planting an "
            "idea in a target's mind.",
            "Science Fiction",
            2010,
            8.8,
        ),
        (
            "The Godfather",
            "The aging patriarch of a crime dynasty transfers control of his "
            "clandestine empire to his reluctant youngest son.",
            "Crime",
            1972,
            9.2,
        ),
        (
            "Spirited Away",
            "A young girl wanders into a world of spirits and gods and must "
            "find the courage to free her parents and return home.",
            "Animation",
            2001,
            8.6,
        ),
        (
            "The Dark Knight",
            "Batman faces the Joker, a criminal mastermind who plunges Gotham "
            "into chaos and tests the thin line between hero and vigilante.",
            "Action",
            2008,
            9.0,
        ),
        (
            "Parasite",
            "A poor family schemes to become employed by a wealthy household, "
            "until a shocking discovery upends their carefully laid plan.",
            "Thriller",
            2019,
            8.5,
        ),
        (
            "Forrest Gump",
            "Through sheer decency and luck, a good-hearted man from Alabama "
            "finds himself at the center of decades of American history.",
            "Drama",
            1994,
            8.8,
        ),
        (
            "Interstellar",
            "As Earth grows unlivable, a former pilot leads a mission through "
            "a wormhole in a desperate search for a new home for humanity.",
            "Science Fiction",
            2014,
            8.6,
        ),
        (
            "The Matrix",
            "A hacker discovers that reality is a simulation and joins a "
            "rebellion to overthrow the machines that enslave humankind.",
            "Science Fiction",
            1999,
            8.7,
        ),
        (
            "Coco",
            "A boy who dreams of becoming a musician journeys into the Land of "
            "the Dead to uncover his family's long-buried history.",
            "Animation",
            2017,
            8.4,
        ),
        (
            "Pulp Fiction",
            "The lives of two hit men, a boxer, and a pair of diner robbers "
            "intertwine in four tales of violence and unexpected redemption.",
            "Crime",
            1994,
            8.9,
        ),
        (
            "Whiplash",
            "An ambitious young drummer clashes with a ruthless instructor "
            "whose brutal methods push him to the edge of his talent.",
            "Drama",
            2014,
            8.5,
        ),
    ],
)


# --------------------------------------------------------------------------
# faqs (~15 rows)
# --------------------------------------------------------------------------
_FAQS = SampleTable(
    name="faqs",
    create_sql=(
        "CREATE TABLE IF NOT EXISTS `faqs` ("
        "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, "
        "question VARCHAR(500) NOT NULL, "
        "answer TEXT NOT NULL, "
        "category VARCHAR(100), "
        "PRIMARY KEY (id)"
        f") {_TABLE_OPTS}"
    ),
    columns=("question", "answer", "category"),
    rows=[
        (
            "How do I reset my password?",
            "Go to the sign-in page and choose Forgot password. Enter the "
            "email on your account and we will send a secure reset link that "
            "stays valid for one hour. Follow it to set a new password.",
            "account",
        ),
        (
            "How can I change the email address on my account?",
            "Open Account Settings, select Profile, and update the email "
            "field. We will send a confirmation message to the new address; "
            "the change takes effect once you click the link inside it.",
            "account",
        ),
        (
            "Why was I charged twice this month?",
            "Duplicate charges are usually a temporary authorization hold that "
            "clears within a few business days. If a second charge still shows "
            "after five days, contact support and we will investigate.",
            "billing",
        ),
        (
            "How do I update my payment method?",
            "In Billing, select Payment methods, then add a new card and mark "
            "it as default. Your next invoice will use the updated card, and "
            "you can safely remove the old one afterward.",
            "billing",
        ),
        (
            "Can I get a refund?",
            "Refunds are available within 30 days of purchase for most plans. "
            "Submit a request from the Billing page and, once approved, the "
            "amount is returned to your original payment method.",
            "billing",
        ),
        (
            "How long does shipping take?",
            "Standard shipping arrives in three to five business days, while "
            "express orders placed before noon usually arrive the next day. "
            "You will receive tracking details as soon as your order ships.",
            "shipping",
        ),
        (
            "Do you ship internationally?",
            "Yes, we ship to more than 60 countries. International delivery "
            "times vary from 7 to 14 business days, and any customs duties are "
            "calculated and shown at checkout before you pay.",
            "shipping",
        ),
        (
            "How do I track my order?",
            "Once your order ships, we email a tracking number and a link to "
            "the carrier. You can also find live tracking under Orders in your "
            "account at any time.",
            "shipping",
        ),
        (
            "My order arrived damaged. What should I do?",
            "We are sorry to hear that. Take a photo of the damage and start a "
            "return from the Orders page within 14 days; we will send a "
            "replacement or issue a full refund at no cost to you.",
            "shipping",
        ),
        (
            "How do I cancel my subscription?",
            "Open Billing, choose Manage subscription, and select Cancel. Your "
            "plan stays active until the end of the current billing period, "
            "after which no further charges are made.",
            "billing",
        ),
        (
            "Is my personal data secure?",
            "We encrypt data in transit and at rest, and we never sell your "
            "personal information. You can review exactly what we store and "
            "request deletion at any time from Privacy settings.",
            "account",
        ),
        (
            "The app keeps crashing on launch. How do I fix it?",
            "First make sure you are on the latest version, then restart your "
            "device to clear memory. If the problem persists, reinstall the "
            "app; your data is stored in the cloud and will sync back.",
            "technical",
        ),
        (
            "How do I enable two-factor authentication?",
            "Under Security settings, turn on two-factor authentication and "
            "scan the QR code with an authenticator app. Save the backup codes "
            "somewhere safe in case you lose access to your phone.",
            "account",
        ),
        (
            "Why am I not receiving email notifications?",
            "Check that notifications are enabled under Preferences and look "
            "in your spam folder. Adding our address to your contacts helps "
            "ensure future messages land in your inbox.",
            "technical",
        ),
        (
            "How do I contact customer support?",
            "You can reach us through the in-app chat during business hours or "
            "by opening a ticket from the Help Center. Most inquiries receive "
            "a response within one business day.",
            "account",
        ),
    ],
)


# Ordered, fixed set of sample tables to create/seed.
SAMPLE_TABLES: tuple[SampleTable, ...] = (_PRODUCTS, _ARTICLES, _MOVIES, _FAQS)


def _row_count(row: Any) -> int:
    """Extract the ``cnt`` value from a COUNT(*) result row.

    Supports both DictCursor rows (``{"cnt": n}``) and plain tuple rows
    (``(n,)``) so the helper is robust to cursor configuration.
    """
    if row is None:
        return 0
    if isinstance(row, dict):
        return int(row.get("cnt", 0) or 0)
    try:
        return int(row[0] or 0)
    except (IndexError, TypeError, ValueError):
        return 0


def _table_exists(cur: Any, db: str, table: str) -> bool:
    """Return True if ``db.table`` already exists (before this import)."""
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (db, table),
    )
    return _row_count(cur.fetchone()) > 0


def import_samples(
    db: str, settings: Settings | None = None
) -> dict[str, Any]:
    """Create and seed the fixed sample tables in the application database.

    Restricted to ``settings.mariadb_db``; any other ``db`` raises HTTP 400
    before a connection is opened. Idempotent: tables use
    ``CREATE TABLE IF NOT EXISTS`` and seed rows are inserted only when the
    table is empty.
    """
    settings = settings or get_settings()
    app_db = settings.mariadb_db

    if db != app_db:
        raise HTTPException(
            status_code=400,
            detail=(
                "sample import is only allowed into the application database "
                f"'{app_db}', not '{db}'"
            ),
        )

    conn = console.get_connection(settings)
    results: list[dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            for table in SAMPLE_TABLES:
                name = table.name
                quoted = console.quote_ident(name)

                existed_before = _table_exists(cur, app_db, name)

                # Idempotent DDL: only creates the table if it is missing.
                cur.execute(table.create_sql)

                cur.execute(f"SELECT COUNT(*) AS cnt FROM {quoted}")
                count_before = _row_count(cur.fetchone())

                # Seed only when empty so repeated imports never duplicate.
                if count_before == 0:
                    cur.executemany(table.insert_sql(), list(table.rows))

                cur.execute(f"SELECT COUNT(*) AS cnt FROM {quoted}")
                count_after = _row_count(cur.fetchone())

                results.append(
                    {
                        "name": name,
                        "created": not existed_before,
                        "rows": count_after,
                    }
                )
        conn.commit()
    except Exception:
        # Roll back on any failure so a partial import leaves no half state.
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    return {"status": "ok", "database": db, "tables": results}
