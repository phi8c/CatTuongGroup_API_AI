# app/core/database/models/sync_job.py

from datetime import datetime

from sqlalchemy import (
    DateTime,
    String
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from app.core.database import (
    Base
)


class SyncJob(Base):

    __tablename__ = "sync_jobs"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
