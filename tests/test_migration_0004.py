from alembic import command
from sqlalchemy import create_engine, text

from app.config import get_settings
from app.db.migrate import alembic_config

SEED_0003 = [
    """INSERT INTO problems (slug, title, difficulty, topic_tags, similar_questions, is_paid_only)
       VALUES ('kept', 'K', 'Easy', '[]', '[]', 0), ('paused', 'P', 'Easy', '[]', '[]', 0)""",
    """INSERT INTO cards (slug, due, reps, lapses, state, suspended)
       VALUES ('kept', '2026-01-01 00:00:00', 1, 0, 2, 0),
              ('paused', '2026-01-01 00:00:00', 1, 0, 2, 1)""",
]


def test_paused_cards_become_paused_problems(db_path) -> None:
    url = get_settings().database_url
    config = alembic_config(url)
    command.upgrade(config, "0003")

    engine = create_engine(url)
    with engine.begin() as conn:
        for statement in SEED_0003:
            conn.execute(text(statement))

    command.upgrade(config, "0004")

    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT slug, paused FROM problems")).all())
        card_columns = {r[1] for r in conn.execute(text("PRAGMA table_info(cards)"))}
    engine.dispose()
    assert rows == {"kept": 0, "paused": 1}
    assert "suspended" not in card_columns
