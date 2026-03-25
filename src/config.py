import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Database
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", PROJECT_ROOT / "data" / "candidates_ai.db"))

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FEC_API_KEY = os.getenv("FEC_API_KEY", "DEMO_KEY")

# FEC API
FEC_BASE_URL = "https://api.open.fec.gov/v1"
FEC_ELECTION_YEAR = 2026

# Scraping
SCRAPE_DELAY_SECONDS = 2.0
SCRAPE_MAX_DEPTH = 2
SCRAPE_PRIORITY_PATHS = ["/issues", "/policy", "/policies", "/about", "/blog", "/press", "/news", "/platform"]

# Analysis
ANALYSIS_MODEL = "claude-sonnet-4-20250514"
ANALYSIS_BATCH_SIZE = 10

# Embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Predefined tags
AI_TAGS = [
    "ai_regulation",
    "ai_education",
    "ai_jobs_workforce",
    "ai_military_defense",
    "ai_healthcare",
    "ai_surveillance_privacy",
    "ai_bias_fairness",
    "ai_copyright_ip",
    "ai_existential_risk",
    "ai_competitiveness_china",
    "ai_open_source",
    "ai_government_use",
    "automation_general",
    "tech_regulation_general",
    "algorithmic_accountability",
    "deepfakes_misinfo",
    "ai_energy_climate",
    "ai_agriculture",
]
