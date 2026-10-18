"""Settings for web_scrape, read from the environment (and ``.env``) once.

Pydantic settings with the same environment variable names and defaults as
the former ``src/config.py``. ``Settings`` is the only code that reads these
variables; import ``settings`` or one of the module-level names below.

Booleans keep the old parsing: ``1``, ``true``, ``yes`` or ``on`` (any case)
is true and anything else is false, so an odd value never stops the service.
"""

from pathlib import Path
from typing import Annotated, Any, ClassVar

from dotenv import load_dotenv
from pydantic import BeforeValidator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ as before: some code (the DB pool, the sync and
# vendor services) reads DATABASE_URL with os.getenv.
load_dotenv()

_TRUE = {"1", "true", "yes", "on"}


def _flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUE


def _stripped(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def _float_or_zero(value: Any) -> Any:
    """``SENTRY_TRACES_SAMPLE_RATE=`` (empty) means 0.0, as before."""
    return value if not (isinstance(value, str) and not value.strip()) else 0.0


Flag = Annotated[bool, BeforeValidator(_flag)]
Stripped = Annotated[str, BeforeValidator(_stripped)]

TIME_RANGES_DEFAULT: list[str] = ["24h", "7d", "14d", "30d"]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(extra="ignore")

    # Database settings
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/peptides_db"

    # Selenium settings
    TIMEOUT: int = 5

    # ── Gateway integration settings ──────────────────────────────────────
    # Shared secret the orchestrator gateway presents in UPSTREAM_AUTH_HEADER.
    # When empty, API routes run open (local dev only).
    API_TOKEN: str = ""
    # Header that carries the gateway token.
    GATEWAY_AUTH_HEADER: str = "X-Gateway-Token"
    # Start the APScheduler background sync on boot. Disable when the
    # orchestrator/gateway manages sync (default: on, preserves old behavior).
    # Staging pins it to false: only one scheduler per database.
    START_SCHEDULER: Flag = True

    # Directory settings (created on startup)
    OUTPUT_DIR: Path = Path("output")
    LOG_DIR: Path = Path("log")

    # ── Competitor vendor scraping (peptides-platform#288) ────────────────
    # Targets are managed through the API (vendor_scrape_targets table, the
    # admin Pepti.AI -> Scrape tab). This file is the seed / fallback: its
    # targets apply only where no DB target has the same slug. Never code.
    VENDOR_TARGETS_FILE: Path = Path("config/vendor_targets.json")
    # Contact URL embedded in the User-Agent so a site owner who wants us to
    # stop has somewhere to go. Keep it real.
    VENDOR_SCRAPER_CONTACT_URL: str = "https://github.com/peptides-ai-ecosystem/web_scrape"
    # Honest, identifiable User-Agent. This is NOT the spoofed browser string
    # used by app/infrastructure/webdriver_factory.py for our own pep-pedia
    # scrape — competitor sites get told exactly who is calling. Empty/unset
    # means "PeptidesVendorScraper/1.0 (+<VENDOR_SCRAPER_CONTACT_URL>)".
    VENDOR_SCRAPER_USER_AGENT: str = ""
    # Politeness floor, seconds between requests to the same host. The
    # effective delay is max(this, target override, robots.txt Crawl-delay).
    VENDOR_SCRAPE_MIN_INTERVAL_SECONDS: float = 5.0
    # Retries on 429/5xx before the host is abandoned for the run.
    VENDOR_SCRAPE_MAX_RETRIES: int = 2
    VENDOR_SCRAPE_BACKOFF_SECONDS: float = 30.0
    VENDOR_SCRAPE_TIMEOUT_MS: int = 20000
    # SSRF guard (app/infrastructure/url_safety.py): targets on loopback,
    # private, link-local (cloud metadata), multicast or reserved addresses are
    # refused at save and at fetch time. true disables that address check for
    # LOCAL TESTING ONLY (a fixture site on 127.0.0.1). Never set it deployed.
    VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS: Flag = False
    # Relative price move that flags an observation for review instead of
    # letting it overwrite a previously accepted price. 0.25 == 25%.
    VENDOR_PRICE_DELTA_THRESHOLD: float = 0.25
    # Below this confidence an observation is always flagged.
    VENDOR_MIN_CONFIDENCE: float = 0.6
    # Nightly cron. Off by default — turn it on deliberately, per environment.
    VENDOR_SCRAPE_CRON_ENABLED: Flag = False
    VENDOR_SCRAPE_CRON_HOUR: int = 3
    VENDOR_SCRAPE_CRON_MINUTE: int = 15
    # Publishing accepted observations onward into the platform's
    # `vendor_products` table. Off, and unimplemented — see
    # app/scrapers/vendors/vendor_products_publisher.py for why.
    VENDOR_PRODUCTS_PUBLISH_ENABLED: Flag = False

    # ── URL-only competitor discovery (AAD-1) ─────────────────────────────
    # A target saved with only a store URL (no CSS selectors) is read through
    # the WooCommerce Store API, Shopify products.json, sitemaps + schema.org
    # JSON-LD, in that order. See docs/product/url-only-discovery.md.
    # Hard cap on HTTP requests one discovery may make against one store.
    VENDOR_DISCOVERY_MAX_REQUESTS: int = 60
    # Cap on products (not variants) read per store per run when the target
    # sets no max_products_per_run of its own.
    VENDOR_DISCOVERY_MAX_PRODUCTS: int = 200
    # In-flight requests against one host; clamped to 1..4. Hosts are read one
    # at a time and the per-host rate limit still spaces request starts.
    VENDOR_DISCOVERY_CONCURRENCY: int = 2
    VENDOR_DISCOVERY_TIMEOUT_SECONDS: float = 15
    # Our own stores. A competitor target on one of these domains, or with one
    # of these slugs, is refused (422) and never scraped: competitor and own
    # vendors stay separate. Comma-separated; subdomains match too.
    OWNED_STORE_DOMAINS: str = "arcanepeptides.com,ruo.bio,bulkpeptides.com,moglabs.bio"
    OWNED_STORE_VENDORS: str = "arcane,ruo,bulk,bulkpeptides,moglabs"

    # Run `alembic upgrade head` (vendor_scrape_targets, vendor_price_observations;
    # version table alembic_version_web_scrape) at startup. Off by default, as in
    # peptide: the deploy runs the migration. Needs a DB role with DDL rights.
    VENDOR_SCHEMA_AUTO_CREATE: Flag = False

    # ── Sentry error capture (FEEDBACK-3 G15) ─────────────────────────────
    # Empty SENTRY_DSN (the default) means sentry_sdk.init is never called.
    # The deploy workflow's `set_sentry_dsn` input writes it into the box's .env.
    SENTRY_DSN: Stripped = ""
    # Blank -> ENVIRONMENT, else "production".
    SENTRY_ENVIRONMENT: Stripped = ""
    # Blank -> GIT_SHA (set by the Dockerfile build arg), else unset.
    SENTRY_RELEASE: Stripped = ""
    SENTRY_TRACES_SAMPLE_RATE: Annotated[float, BeforeValidator(_float_or_zero)] = 0.0

    # Time range settings (constants, not environment)
    TIME_RANGES: ClassVar[list[str]] = TIME_RANGES_DEFAULT
    # Skip list settings
    BUTTON_SKIP_LIST: ClassVar[list[str]] = [
        "peak",
        "half-life",
        "cleared",
        "hrs",
        "hr",
        "day",
    ] + TIME_RANGES_DEFAULT

    @model_validator(mode="after")
    def _derive(self) -> "Settings":
        if not self.VENDOR_SCRAPER_USER_AGENT:
            self.VENDOR_SCRAPER_USER_AGENT = f"PeptidesVendorScraper/1.0 (+{self.VENDOR_SCRAPER_CONTACT_URL})"
        self.OUTPUT_DIR.mkdir(exist_ok=True)
        self.LOG_DIR.mkdir(exist_ok=True)
        return self

    # File paths — manual sync flows use dedicated files to avoid race conditions
    @property
    def ENHANCED_CSV(self) -> Path:
        return self.OUTPUT_DIR / "pep_pedia_enhanced.csv"

    @property
    def GRAPH_CSV(self) -> Path:
        return self.OUTPUT_DIR / "pep_pedia_graph.csv"

    @property
    def FULL_CSV(self) -> Path:
        return self.OUTPUT_DIR / "pep_pedia_full.csv"

    @property
    def MASTER_CSV(self) -> Path:
        """Alias of ENHANCED_CSV (the CSV store's default path)."""
        return self.ENHANCED_CSV

    @property
    def ERROR_LOG(self) -> Path:
        return self.LOG_DIR / "error_log.txt"

    @property
    def DEBUG_LOG(self) -> Path:
        return self.LOG_DIR / "debug_log.txt"

    @property
    def sqlalchemy_database_url(self) -> str:
        """``DATABASE_URL`` for SQLAlchemy (Alembic): the psycopg2 driver this service ships.

        ``postgres://`` and ``postgresql://`` become ``postgresql+psycopg2://``; a URL that
        already names a driver is left alone.
        """
        url = self.DATABASE_URL
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg2://" + url[len(prefix) :]
        return url


# -------------------- MODULE-LEVEL EXPORTS -------------------- #
settings = Settings()

DATABASE_URL = settings.DATABASE_URL
TIMEOUT = settings.TIMEOUT
API_TOKEN = settings.API_TOKEN
GATEWAY_AUTH_HEADER = settings.GATEWAY_AUTH_HEADER
START_SCHEDULER = settings.START_SCHEDULER
OUTPUT_DIR = settings.OUTPUT_DIR
ENHANCED_CSV = settings.ENHANCED_CSV
GRAPH_CSV = settings.GRAPH_CSV
FULL_CSV = settings.FULL_CSV
MASTER_CSV = settings.MASTER_CSV  # alias for ENHANCED_CSV
ERROR_LOG = settings.ERROR_LOG
DEBUG_LOG = settings.DEBUG_LOG
TIME_RANGES = settings.TIME_RANGES
BUTTON_SKIP_LIST = settings.BUTTON_SKIP_LIST

# Competitor vendor scraping (peptides-platform#288)
VENDOR_TARGETS_FILE = settings.VENDOR_TARGETS_FILE
VENDOR_SCRAPER_CONTACT_URL = settings.VENDOR_SCRAPER_CONTACT_URL
VENDOR_SCRAPER_USER_AGENT = settings.VENDOR_SCRAPER_USER_AGENT
VENDOR_SCRAPE_MIN_INTERVAL_SECONDS = settings.VENDOR_SCRAPE_MIN_INTERVAL_SECONDS
VENDOR_SCRAPE_MAX_RETRIES = settings.VENDOR_SCRAPE_MAX_RETRIES
VENDOR_SCRAPE_BACKOFF_SECONDS = settings.VENDOR_SCRAPE_BACKOFF_SECONDS
VENDOR_SCRAPE_TIMEOUT_MS = settings.VENDOR_SCRAPE_TIMEOUT_MS
# Read it as settings.VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS (url_safety does, per
# call) so a test or operator change is seen without a re-import.
VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS = settings.VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS
VENDOR_PRICE_DELTA_THRESHOLD = settings.VENDOR_PRICE_DELTA_THRESHOLD
VENDOR_MIN_CONFIDENCE = settings.VENDOR_MIN_CONFIDENCE
VENDOR_SCRAPE_CRON_ENABLED = settings.VENDOR_SCRAPE_CRON_ENABLED
VENDOR_SCRAPE_CRON_HOUR = settings.VENDOR_SCRAPE_CRON_HOUR
VENDOR_SCRAPE_CRON_MINUTE = settings.VENDOR_SCRAPE_CRON_MINUTE
VENDOR_PRODUCTS_PUBLISH_ENABLED = settings.VENDOR_PRODUCTS_PUBLISH_ENABLED
VENDOR_SCHEMA_AUTO_CREATE = settings.VENDOR_SCHEMA_AUTO_CREATE
VENDOR_DISCOVERY_MAX_REQUESTS = settings.VENDOR_DISCOVERY_MAX_REQUESTS
VENDOR_DISCOVERY_MAX_PRODUCTS = settings.VENDOR_DISCOVERY_MAX_PRODUCTS
VENDOR_DISCOVERY_CONCURRENCY = settings.VENDOR_DISCOVERY_CONCURRENCY
VENDOR_DISCOVERY_TIMEOUT_SECONDS = settings.VENDOR_DISCOVERY_TIMEOUT_SECONDS
