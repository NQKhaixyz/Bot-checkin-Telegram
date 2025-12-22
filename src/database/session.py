"""Database session management for Telegram Attendance Bot."""

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy.orm import Session, sessionmaker

# Global session factory (set by init_db)
_SessionLocal: Optional[sessionmaker] = None


def set_session_factory(session_factory: sessionmaker) -> None:
    """Set the global session factory."""
    global _SessionLocal
    _SessionLocal = session_factory


def get_session_factory() -> sessionmaker:
    """Get the global session factory."""
    if _SessionLocal is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() first."
        )
    return _SessionLocal


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Yields a database session and handles commit/rollback automatically.
    Commits on successful completion, rolls back on exception.

    Yields:
        Session: A SQLAlchemy database session.

    Example:
        with get_db_session() as session:
            user = session.query(User).filter_by(user_id=123).first()
            user.status = UserStatus.ACTIVE
            # Session is automatically committed on exit
    """
    session_factory = get_session_factory()
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    Generator function for database sessions.

    Useful for dependency injection (e.g., FastAPI dependencies).

    Yields:
        Session: A SQLAlchemy database session.

    Example:
        def some_function(db: Session = Depends(get_db)):
            users = db.query(User).all()
    """
    session_factory = get_session_factory()
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
