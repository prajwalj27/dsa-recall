from pathlib import Path

from sqlalchemy import inspect

from app.config import get_settings
from app.db.migrate import upgrade_to_head
from app.db.models import Base
from app.db.session import get_engine

EXPECTED_TABLES = {
    "problems",
    "submissions",
    "solves",
    "cards",
    "review_log",
    "skills",
    "skill_edges",
    "problem_skills",
    "problem_analysis",
    "solution_analysis",
    "insights",
    "suggestions",
    "settings",
    "sync_state",
}


def test_upgrade_creates_all_tables(db_path: Path) -> None:
    upgrade_to_head(get_settings().database_url)

    tables = set(inspect(get_engine()).get_table_names())
    assert tables == EXPECTED_TABLES | {"alembic_version"}


def test_models_match_design() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
