from app.db.base import Base
from app.db.session import engine
from app.models import clip, processing_job, transcript, upload  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
