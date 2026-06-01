from sqlalchemy import text
from app.db.session import Base, engine

from app.models.audit_log import AuditLog  # noqa: F401
from app.models.brief import Brief, BriefSource  # noqa: F401
from app.models.chunk import Chunk  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.source import Source  # noqa: F401


def init_db() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
