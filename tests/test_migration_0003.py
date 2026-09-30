from alembic import command
from sqlalchemy import create_engine, text

from app.config import get_settings
from app.db.migrate import alembic_config

SEED_0002 = [
    """INSERT INTO problems (slug, title, difficulty, topic_tags, similar_questions, is_paid_only)
       VALUES ('p', 'P', 'Easy', '[]', '[]', 0)""",
    """INSERT INTO submissions (submission_id, slug, status, lang, timestamp)
       VALUES (1, 'p', 'Accepted', 'python3', '2026-01-01 00:00:00')""",
    """INSERT INTO solves (slug, accepted_submission_id, wrong_before_ac, accepted_at,
                           rating_inferred)
       VALUES ('p', 1, 0, '2026-01-01 00:00:00', 0)""",
]


def test_existing_solves_become_history(db_path) -> None:
    url = get_settings().database_url
    config = alembic_config(url)
    command.upgrade(config, "0002")

    engine = create_engine(url)
    with engine.begin() as conn:
        for statement in SEED_0002:
            conn.execute(text(statement))

    command.upgrade(config, "head")

    with engine.connect() as conn:
        row = conn.execute(text("SELECT rating_source, used_solution FROM solves")).one()
    engine.dispose()
    assert tuple(row) == ("history", 0)
