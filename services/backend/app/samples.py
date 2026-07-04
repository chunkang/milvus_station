"""Sample data import: create & seed a fixed set of demo tables.

This module powers ``POST /databases/{db}/samples/import``. It creates
four demonstration tables (``products``, ``articles``, ``movies`` and
``faqs``) in the *application* database and seeds each with realistic,
embeddable text rows so the data console / vector-index flow has content
to work with out of the box.

SEED GENERATION
---------------
Each table is seeded with 100+ rows that are generated *programmatically*
at import time by composing curated component pools (product concepts,
article topics, movie genres, FAQ categories, and so on). Composition is
fully deterministic and index-driven -- no randomness and no dates read
from the wall clock -- so the seed data is identical on every run and the
tests stay stable. Every row carries a distinct, semantically varied value
in its embeddable column so semantic search over the data is interesting.

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

from datetime import date, timedelta
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


# ==========================================================================
# Seed generators
#
# Each builder composes curated component pools into 100+ unique rows. The
# embeddable column (products.description, articles.body, movies.overview,
# faqs.answer) is guaranteed distinct per row because it embeds the varying
# component(s) that drive the composition.
# ==========================================================================


# --------------------------------------------------------------------------
# products (embed `description`)
# --------------------------------------------------------------------------
def _build_product_rows() -> list[tuple[Any, ...]]:
    """Compose product rows from concept x brand/finish variants.

    20 product concepts x 6 brand/finish modifiers = 120 rows. Each name and
    description is unique because the (brand, finish, concept) triple varies.
    """
    # (noun, category, base_price, feature clause, use-case clause)
    concepts: list[tuple[str, str, float, str, str]] = [
        ("wireless headphones", "electronics", 149.99,
         "deliver immersive sound with active noise cancellation and a marathon battery life",
         "ideal for travel, commuting, and focused deep work"),
        ("running shoes", "apparel", 89.95,
         "cushion every stride with responsive foam and a breathable knit upper",
         "built for daily training runs and race-day personal bests"),
        ("burr coffee grinder", "home", 79.00,
         "produce a consistent grind across thirty settings from espresso to French press",
         "perfect for anyone chasing a better cup at home"),
        ("yoga mat", "sports", 39.50,
         "offer a non-slip, extra-cushioned surface that protects the joints",
         "great for daily flows, pilates, and floor workouts"),
        ("mechanical keyboard", "electronics", 119.00,
         "pair hot-swappable switches with a sturdy aluminium frame and crisp keycaps",
         "a favourite among programmers, writers, and gamers alike"),
        ("LED desk lamp", "home", 45.50,
         "cast flicker-free light with adjustable warmth and brightness",
         "designed to reduce eye strain during long study sessions"),
        ("travel backpack", "apparel", 99.00,
         "organise your gear with a padded laptop sleeve and weatherproof zippers",
         "sized for weekend getaways and busy daily commutes"),
        ("insulated water bottle", "home", 29.99,
         "keep drinks cold for twenty-four hours or hot for twelve behind a leakproof lid",
         "made for the gym, the trail, and the office desk"),
        ("smart thermostat", "home", 129.00,
         "learn your routine and trim energy bills automatically",
         "an easy upgrade for a more comfortable, efficient home"),
        ("action camera", "electronics", 249.00,
         "capture rock-steady 4K footage while staying waterproof to ten metres",
         "ready for surfing, cycling, and every backcountry adventure"),
        ("merino wool sweater", "apparel", 74.00,
         "regulate temperature year-round with soft, breathable natural fibres",
         "layers effortlessly for the office or a weekend hike"),
        ("portable power bank", "electronics", 59.99,
         "recharge a phone up to four times through fast dual-port output",
         "a travel essential for long flights and festival weekends"),
        ("down insulated jacket", "apparel", 159.00,
         "pack serious warmth into a featherweight, stuffable shell",
         "perfect for frosty commutes and alpine weekends"),
        ("bluetooth speaker", "electronics", 69.00,
         "fill a room with balanced sound and deep, distortion-free bass",
         "splash-proof and ready for the kitchen, patio, or beach"),
        ("cast iron skillet", "home", 42.00,
         "sear, bake, and fry with even heat across a pre-seasoned surface",
         "a lifetime workhorse for both stovetop and oven cooking"),
        ("ergonomic office chair", "home", 219.00,
         "support your back with adjustable lumbar tension and breathable mesh",
         "engineered for full days at the desk without the aches"),
        ("fitness tracker", "electronics", 99.00,
         "monitor heart rate, sleep, and workouts on a weeklong battery",
         "a gentle nudge toward healthier daily habits"),
        ("waterproof hiking boots", "apparel", 139.00,
         "grip loose terrain with a rugged sole and a supportive ankle collar",
         "trail-ready for muddy climbs and long-distance treks"),
        ("electric gooseneck kettle", "home", 64.00,
         "reach a precise temperature in minutes with variable controls",
         "a pour-over and loose-leaf tea lover's countertop companion"),
        ("polarised sunglasses", "apparel", 55.00,
         "cut glare and block UV behind lightweight, impact-resistant lenses",
         "styled for driving, the water, and bright city days"),
    ]
    # (brand, finish/colour, quality adjective)
    modifiers: list[tuple[str, str, str]] = [
        ("Aurora", "midnight black", "premium"),
        ("Summit", "slate gray", "rugged"),
        ("Nimbus", "arctic white", "lightweight"),
        ("Cascade", "forest green", "durable"),
        ("Vertex", "deep navy", "compact"),
        ("Lumen", "sand beige", "everyday"),
    ]

    rows: list[tuple[Any, ...]] = []
    for ci, (noun, category, base_price, feature, usecase) in enumerate(concepts):
        for mi, (brand, colour, adjective) in enumerate(modifiers):
            name = f"{brand} {noun.title()} ({colour.title()})"
            description = (
                f"{adjective.capitalize()} {colour} {noun} that {feature}, "
                f"{usecase}."
            )
            price = round(base_price + mi * 7.5, 2)
            in_stock = 0 if (ci + mi) % 7 == 0 else 1
            rows.append((name, description, category, price, in_stock))
    return rows


# --------------------------------------------------------------------------
# articles (embed `body`)
# --------------------------------------------------------------------------
def _build_article_rows() -> list[tuple[Any, ...]]:
    """Compose article rows from topic templates x subject pools.

    8 topics x 13 subjects = 104 rows. Titles and bodies both embed the
    subject, so each is unique. Publish dates are derived deterministically
    from a fixed base date minus the running row index.
    """
    base_date = date(2026, 6, 30)
    topics: list[dict[str, Any]] = [
        {
            "tag": "tech,innovation",
            "author": "Dana Weber",
            "headline": "The Quiet Rise of {S}",
            "body": (
                "{S} moved from research labs into everyday products this year. "
                "Companies large and small are racing to adopt the approach, and "
                "analysts expect the shift to accelerate over the coming quarter. "
                "Supporters point to lower costs, while skeptics urge a careful rollout."
            ),
            "subjects": [
                "open-source language models", "on-device AI assistants",
                "edge computing chips", "battery recycling",
                "autonomous delivery robots", "privacy-first browsers",
                "augmented reality glasses", "low-earth-orbit internet",
                "passwordless logins", "home energy storage",
                "wearable health sensors", "digital identity wallets",
                "solid-state batteries",
            ],
        },
        {
            "tag": "science,research",
            "author": "Priya Nair",
            "headline": "New Findings Reshape Our View of {S}",
            "body": (
                "A team of researchers has published fresh evidence about {s}. "
                "The results challenge long-held assumptions and open new questions "
                "for the field. Independent experts called the work careful and "
                "compelling, while cautioning that more study is still needed."
            ),
            "subjects": [
                "distant ocean moons", "coral reef recovery",
                "ancient human migration", "deep-sea ecosystems",
                "volcanic activity", "the early universe",
                "migratory bird routes", "desert aquifers",
                "glacier melt", "soil microbes", "solar weather",
                "urban insect populations", "mountain water cycles",
            ],
        },
        {
            "tag": "travel,destinations",
            "author": "Marco Ferretti",
            "headline": "A Slow Week Exploring {S}",
            "body": (
                "There is no better way to appreciate {s} than to take your time. "
                "Our writer spent a week wandering its quiet corners, trading a rushed "
                "itinerary for long lunches and unplanned detours. The reward was a "
                "trip that felt personal rather than packaged."
            ),
            "subjects": [
                "the Alpine railways", "coastal Portugal", "rural Japan",
                "the Scottish Highlands", "the Amalfi Coast", "Patagonia",
                "the Baltic capitals", "Morocco's medinas",
                "the Norwegian fjords", "Vietnam's river deltas",
                "the Canadian Rockies", "Iceland's ring road",
                "the Greek islands",
            ],
        },
        {
            "tag": "food,cooking",
            "author": "Helen Brooks",
            "headline": "Rediscovering {S} at Home",
            "body": (
                "Home cooks are falling back in love with {s}. A new wave of simple, "
                "seasonal recipes has stripped away the fuss and put the focus on "
                "good ingredients and a little patience. We break down the handful of "
                "steps that make all the difference."
            ),
            "subjects": [
                "slow-fermented bread", "one-pot weeknight dinners",
                "homemade pasta", "regional curries", "preserving and pickling",
                "wood-fired pizza", "plant-forward cooking", "handmade dumplings",
                "classic French sauces", "street-food snacks",
                "low-waste cooking", "fresh herb gardens", "artisan cheese boards",
            ],
        },
        {
            "tag": "finance,money",
            "author": "Samuel Osei",
            "headline": "A Plain-Language Guide to {S}",
            "body": (
                "For anyone confused by {s}, the basics are simpler than they look. "
                "This guide cuts through the jargon with clear examples and a few "
                "rules of thumb. The goal is to help you make confident decisions "
                "without taking on risk you do not understand."
            ),
            "subjects": [
                "high-yield savings", "index fund investing", "building an emergency fund",
                "paying down debt", "understanding credit scores", "budgeting that sticks",
                "retirement accounts", "reading an interest rate", "tax-loss basics",
                "diversifying a portfolio", "inflation and your cash",
                "first-time home buying", "side-income taxes",
            ],
        },
        {
            "tag": "health,wellbeing",
            "author": "Aisha Rahman",
            "headline": "What the Science Says About {S}",
            "body": (
                "Everyone has an opinion about {s}, but what does the evidence show? "
                "We reviewed recent studies and spoke with clinicians to separate the "
                "practical advice from the hype. The takeaway is reassuringly modest: "
                "small, consistent habits matter more than any quick fix."
            ),
            "subjects": [
                "better sleep", "strength training after forty", "gut health",
                "managing screen time", "hydration myths", "walking for fitness",
                "stress and breathing", "the Mediterranean diet", "morning sunlight",
                "recovery and rest days", "mindful eating", "posture at the desk",
                "cold-water swimming",
            ],
        },
        {
            "tag": "sport,competition",
            "author": "Toby Grant",
            "headline": "Inside the Comeback in {S}",
            "body": (
                "This season delivered one of the great stories in {s}. Underdogs "
                "found form at exactly the right moment, and a few tactical tweaks "
                "reshaped the whole competition. We look at how it happened and what "
                "it means for the campaigns ahead."
            ),
            "subjects": [
                "grassroots cycling", "women's football", "long-distance running",
                "amateur rowing", "club rugby", "table tennis", "open-water swimming",
                "indoor climbing", "youth athletics", "para sport",
                "mixed doubles tennis", "regional cricket", "urban skateboarding",
            ],
        },
        {
            "tag": "culture,arts",
            "author": "Lena Fischer",
            "headline": "How {S} Is Finding a New Audience",
            "body": (
                "Once considered niche, {s} is drawing curious newcomers in growing "
                "numbers. Small venues and online communities have lowered the barrier "
                "to entry, and a fresh generation of makers is reinterpreting old forms. "
                "We spoke with several about what keeps them going."
            ),
            "subjects": [
                "independent cinema", "vinyl records", "modern poetry",
                "community theatre", "documentary photography", "folk music revivals",
                "printmaking", "board-game design", "public murals",
                "audio drama", "contemporary dance", "small-press comics",
                "traditional crafts",
            ],
        },
    ]

    rows: list[tuple[Any, ...]] = []
    index = 0
    for topic in topics:
        for subject in topic["subjects"]:
            title = topic["headline"].format(s=subject, S=subject.capitalize())
            body = topic["body"].format(s=subject, S=subject.capitalize())
            published_at = (base_date - timedelta(days=index)).isoformat()
            rows.append((title, body, topic["author"], topic["tag"], published_at))
            index += 1
    return rows


# --------------------------------------------------------------------------
# movies (embed `overview`)
# --------------------------------------------------------------------------
# A handful of curated, real films kick off the list with hand-written plot
# overviews; the remainder are composed across genres so we reach 100+.
#
# Curated tuples are shaped (title, overview, actors, genre, year, rating):
# ``actors`` lists three to four real lead performers from each film.
_CURATED_MOVIES: tuple[tuple[Any, ...], ...] = (
    ("The Shawshank Redemption",
     "A banker sentenced to life in prison forms an enduring friendship and "
     "quietly holds on to hope over two long decades behind bars.",
     "Tim Robbins, Morgan Freeman, Bob Gunton, William Sadler",
     "Drama", 1994, 9.3),
    ("Inception",
     "A thief who steals corporate secrets through dream-sharing technology is "
     "offered a chance to erase his past by planting an idea in a target's mind.",
     "Leonardo DiCaprio, Joseph Gordon-Levitt, Elliot Page, Tom Hardy",
     "Science Fiction", 2010, 8.8),
    ("The Godfather",
     "The aging patriarch of a crime dynasty transfers control of his "
     "clandestine empire to his reluctant youngest son.",
     "Marlon Brando, Al Pacino, James Caan, Robert Duvall",
     "Crime", 1972, 9.2),
    ("Spirited Away",
     "A young girl wanders into a world of spirits and gods and must find the "
     "courage to free her parents and return home.",
     "Rumi Hiiragi, Miyu Irino, Mari Natsuki, Takashi Naito",
     "Animation", 2001, 8.6),
    ("The Dark Knight",
     "Batman faces the Joker, a criminal mastermind who plunges Gotham into "
     "chaos and tests the thin line between hero and vigilante.",
     "Christian Bale, Heath Ledger, Aaron Eckhart, Michael Caine",
     "Action", 2008, 9.0),
    ("Parasite",
     "A poor family schemes to become employed by a wealthy household, until a "
     "shocking discovery upends their carefully laid plan.",
     "Song Kang-ho, Lee Sun-kyun, Cho Yeo-jeong, Choi Woo-shik",
     "Thriller", 2019, 8.5),
    ("Forrest Gump",
     "Through sheer decency and luck, a good-hearted man from Alabama finds "
     "himself at the center of decades of American history.",
     "Tom Hanks, Robin Wright, Gary Sinise, Sally Field",
     "Drama", 1994, 8.8),
    ("Interstellar",
     "As Earth grows unlivable, a former pilot leads a mission through a "
     "wormhole in a desperate search for a new home for humanity.",
     "Matthew McConaughey, Anne Hathaway, Jessica Chastain, Michael Caine",
     "Science Fiction", 2014, 8.6),
    ("The Matrix",
     "A hacker discovers that reality is a simulation and joins a rebellion to "
     "overthrow the machines that enslave humankind.",
     "Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss, Hugo Weaving",
     "Science Fiction", 1999, 8.7),
    ("Coco",
     "A boy who dreams of becoming a musician journeys into the Land of the "
     "Dead to uncover his family's long-buried history.",
     "Anthony Gonzalez, Gael Garcia Bernal, Benjamin Bratt, Alanna Ubach",
     "Animation", 2017, 8.4),
    ("Pulp Fiction",
     "The lives of two hit men, a boxer, and a pair of diner robbers intertwine "
     "in four tales of violence and unexpected redemption.",
     "John Travolta, Samuel L. Jackson, Uma Thurman, Bruce Willis",
     "Crime", 1994, 8.9),
    ("Whiplash",
     "An ambitious young drummer clashes with a ruthless instructor whose "
     "brutal methods push him to the edge of his talent.",
     "Miles Teller, J.K. Simmons, Paul Reiser, Melissa Benoist",
     "Drama", 2014, 8.5),
)


def _build_movie_rows() -> list[tuple[Any, ...]]:
    """Curated real films plus composed synopses across ten genres.

    12 curated + (10 genres x 10 protagonists) = 112 rows. Each row is shaped
    (title, overview, actors, genre, year, rating). Composed titles are built
    from prefix/noun pools so each is unique, every overview embeds both the
    genre template and the protagonist, and each composed cast is derived
    deterministically from the running row index via fixed name pools.
    """
    rows: list[tuple[Any, ...]] = list(_CURATED_MOVIES)

    # (genre, overview template with a {role} slot)
    genres: list[tuple[str, str]] = [
        ("Drama",
         "A {role} confronts a painful secret from the past and must choose "
         "between protecting the family and finally telling the truth."),
        ("Thriller",
         "When a routine day turns deadly, a {role} races against the clock to "
         "expose a conspiracy before it silences them for good."),
        ("Science Fiction",
         "In a near-future city, a {role} discovers a technology that could "
         "save humanity or erase it, and must decide who to trust."),
        ("Romance",
         "A {role} and a stranger cross paths by chance, and one unforgettable "
         "season forces them both to risk everything for love."),
        ("Comedy",
         "A {role} stumbles into one absurd mishap after another, learning that "
         "the best-laid plans rarely survive contact with real life."),
        ("Horror",
         "A {role} moves into a quiet house where the walls seem to whisper, and "
         "the line between nightmare and waking slowly begins to blur."),
        ("Adventure",
         "A {role} sets out on a perilous journey across uncharted country, "
         "chasing a legend that everyone else swears is only a myth."),
        ("Mystery",
         "After a neighbour vanishes without a trace, a {role} follows a trail "
         "of small clues that leads somewhere no one expected."),
        ("Fantasy",
         "Gifted with a power they never asked for, a {role} must unite a "
         "fractured kingdom before an ancient darkness returns."),
        ("Crime",
         "A {role} is pulled into the city's underworld and must outwit both the "
         "law and the syndicate to protect the people they love."),
    ]
    roles: list[str] = [
        "young detective", "retired soldier", "small-town teacher",
        "struggling musician", "brilliant scientist", "single parent",
        "ambitious lawyer", "weary journalist", "runaway teenager",
        "seasoned pilot",
    ]
    title_prefixes = [
        "The Last", "Silent", "Broken", "Midnight", "Distant", "Crimson",
        "Hollow", "Golden", "Frozen", "Restless", "Quiet", "Burning",
    ]
    title_nouns = [
        "Horizon", "Promise", "Empire", "Harbor", "Requiem", "Frontier",
        "Lullaby", "Verdict", "Odyssey", "Mirage", "Covenant", "Ember",
    ]
    # Fixed name pools for composing a deterministic three-actor cast per row.
    # The (first, surname) picks are driven purely by the running index and
    # stride constants, so the same cast string is produced on every run.
    actor_first_names = [
        "Ava", "Marcus", "Lena", "Noah", "Priya", "Diego", "Sofia", "Ethan",
        "Maya", "Julian", "Nadia", "Owen", "Clara", "Theo", "Isla", "Malik",
        "Rosa", "Felix", "Ingrid", "Kenji", "Elena", "Hugo", "Simone", "Amara",
        "Leon", "Freya", "Rafael", "Yara",
    ]
    actor_surnames = [
        "Bennett", "Reed", "Fox", "Hale", "Marsh", "Quinn", "Vance", "Doyle",
        "Ashby", "Novak", "Cole", "Rios", "Frost", "Blake", "Mercer", "Sato",
        "Lange", "Okafor", "Pryce", "Dane", "Whitlock", "Ferro", "Nash",
        "Osei", "Krause", "Solberg", "Ibarra", "Wren",
    ]

    def _compose_cast(index: int) -> str:
        """Deterministically pick three distinct-looking actor names.

        The three first-name and surname positions use co-prime strides so
        successive rows shuffle through the pools without immediate repeats.
        """
        nf, ns = len(actor_first_names), len(actor_surnames)
        names = []
        for slot in range(3):
            fi = (index * 3 + slot * 7 + slot) % nf
            si = (index * 5 + slot * 11 + slot * 2) % ns
            names.append(f"{actor_first_names[fi]} {actor_surnames[si]}")
        return ", ".join(names)

    i = 0
    for gi, (genre, template) in enumerate(genres):
        for ri, role in enumerate(roles):
            prefix = title_prefixes[i % len(title_prefixes)]
            noun = title_nouns[(i // len(title_prefixes)) % len(title_nouns)]
            title = f"{prefix} {noun}"
            overview = template.format(role=role)
            actors = _compose_cast(i)
            year = 1995 + ((gi * 7 + ri * 3) % 30)
            rating = round(6.3 + ((gi * 3 + ri * 5) % 27) / 10.0, 1)
            rows.append((title, overview, actors, genre, year, rating))
            i += 1
    return rows


# --------------------------------------------------------------------------
# faqs (embed `answer`)
# --------------------------------------------------------------------------
def _build_faq_rows() -> list[tuple[Any, ...]]:
    """Compose support Q&A pairs across ten categories.

    10 categories x 11 subjects = 110 rows. Both the question and the answer
    embed the category-specific subject, so each question and each answer is
    unique across the whole set.
    """
    groups: list[dict[str, Any]] = [
        {
            "category": "account",
            "q": "How do I {s}?",
            "a": (
                "To {s}, open Account Settings and choose the matching option. "
                "Follow the guided steps and the change is applied to your account "
                "right away. If you get stuck, our support team can walk you through it."
            ),
            "subjects": [
                "reset my password", "change my email address",
                "update my profile photo", "close my account",
                "recover a locked account", "merge two accounts",
                "change my username", "set a display name",
                "link a social login", "verify my identity",
                "export my account data",
            ],
        },
        {
            "category": "billing",
            "q": "What should I do about {s}?",
            "a": (
                "If you have a question about {s}, open the Billing page where every "
                "transaction is listed in detail. Most issues can be resolved there in "
                "a few clicks, and anything unusual can be sent to our team for review."
            ),
            "subjects": [
                "a failed payment", "a duplicate charge", "an unexpected fee",
                "updating my card", "a missing invoice", "changing my billing cycle",
                "applying a promo code", "a currency conversion", "a partial refund",
                "a disputed charge", "tax on my invoice",
            ],
        },
        {
            "category": "shipping",
            "q": "How does {s} work?",
            "a": (
                "For {s}, you can review the full details on the Shipping page during "
                "checkout. Estimated timing and any costs are shown before you confirm, "
                "and a tracking link is emailed the moment your parcel leaves our warehouse."
            ),
            "subjects": [
                "standard delivery", "express shipping", "international orders",
                "order tracking", "delivery to a pickup point", "weekend delivery",
                "shipping insurance", "split shipments", "an address change",
                "signature on delivery", "free shipping thresholds",
            ],
        },
        {
            "category": "returns",
            "q": "Can I get help with {s}?",
            "a": (
                "Yes. For {s}, start from the Orders page and pick the item involved. "
                "We will guide you through the return or replacement, and most refunds "
                "reach your original payment method within a few business days."
            ),
            "subjects": [
                "returning an item", "a damaged product", "an incorrect order",
                "a late refund", "exchanging a size", "printing a return label",
                "a missing part", "a gift return", "a warranty claim",
                "a bulk return", "a restocking fee",
            ],
        },
        {
            "category": "technical",
            "q": "Why am I seeing {s}?",
            "a": (
                "If you are seeing {s}, first update to the latest version and restart "
                "the app to clear temporary memory. When the problem continues, a clean "
                "reinstall usually resolves it, since your data is stored safely in the "
                "cloud and syncs back automatically."
            ),
            "subjects": [
                "the app crashing on launch", "slow loading times", "a blank screen",
                "a sync error", "missing notifications", "a login loop",
                "a broken image", "an upload failure", "a frozen page",
                "an unexpected error code", "a playback issue",
            ],
        },
        {
            "category": "privacy",
            "q": "How do you handle {s}?",
            "a": (
                "When it comes to {s}, we follow a strict, transparency-first policy. "
                "You can review exactly what we collect and adjust your choices in "
                "Privacy settings at any time, and we never sell your personal "
                "information to outside parties."
            ),
            "subjects": [
                "my personal data", "cookies and tracking", "data deletion requests",
                "third-party sharing", "location information", "marketing preferences",
                "data encryption", "account visibility", "children's privacy",
                "data breach alerts", "analytics collection",
            ],
        },
        {
            "category": "subscription",
            "q": "How do I manage {s}?",
            "a": (
                "To manage {s}, open Billing and choose Manage subscription. Changes "
                "take effect at the start of your next billing period, and you keep "
                "full access to your current plan until then."
            ),
            "subjects": [
                "my subscription plan", "an upgrade", "a downgrade", "auto-renewal",
                "a free trial", "pausing my plan", "canceling my plan",
                "a family plan", "a student discount", "switching to annual billing",
                "reactivating a plan",
            ],
        },
        {
            "category": "security",
            "q": "How can I secure {s}?",
            "a": (
                "To secure {s}, head to Security settings where you can enable extra "
                "protection in a couple of steps. We recommend turning on two-factor "
                "authentication and keeping your recovery codes somewhere safe and offline."
            ),
            "subjects": [
                "my account", "two-factor authentication", "a lost device",
                "suspicious activity", "my active login sessions", "app passwords",
                "recovery codes", "a phishing email", "trusted devices",
                "password strength", "a compromised password",
            ],
        },
        {
            "category": "mobile-app",
            "q": "How do I use {s} in the mobile app?",
            "a": (
                "You can set up {s} from the mobile app's Settings menu. Toggle the "
                "feature on, grant any permissions it asks for, and your preference is "
                "saved and synced to every device signed in to your account."
            ),
            "subjects": [
                "offline mode", "push notifications", "biometric login", "the dark theme",
                "widget shortcuts", "data saver mode", "in-app search",
                "syncing across devices", "the camera scanner", "gesture controls",
                "accessibility options",
            ],
        },
        {
            "category": "orders",
            "q": "What happens with {s}?",
            "a": (
                "For {s}, the Orders page shows the current status and every available "
                "action. You can make most changes there while the order is still being "
                "prepared, and we email you an update whenever the status changes."
            ),
            "subjects": [
                "a canceled order", "an out-of-stock item", "a pre-order",
                "a backordered product", "order confirmation", "editing an order",
                "combining orders", "a gift message", "an order on hold",
                "bulk ordering", "my order history",
            ],
        },
    ]

    rows: list[tuple[Any, ...]] = []
    for group in groups:
        for subject in group["subjects"]:
            question = group["q"].format(s=subject)
            answer = group["a"].format(s=subject)
            rows.append((question, answer, group["category"]))
    return rows


# --------------------------------------------------------------------------
# Table definitions (schemas unchanged; rows generated programmatically)
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
    rows=_build_product_rows(),
)


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
    rows=_build_article_rows(),
)


_MOVIES = SampleTable(
    name="movies",
    create_sql=(
        "CREATE TABLE IF NOT EXISTS `movies` ("
        "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, "
        "title VARCHAR(255) NOT NULL, "
        "overview TEXT NOT NULL, "
        "actors VARCHAR(512), "
        "genre VARCHAR(100), "
        "year INT, "
        "rating DECIMAL(3,1), "
        "PRIMARY KEY (id)"
        f") {_TABLE_OPTS}"
    ),
    columns=("title", "overview", "actors", "genre", "year", "rating"),
    rows=_build_movie_rows(),
)


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
    rows=_build_faq_rows(),
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
