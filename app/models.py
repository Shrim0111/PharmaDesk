
from datetime import datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# ============================================================
# User
# ============================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


# ============================================================
# Medicine
# ============================================================

class Medicine(Base):
    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    sku: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    reorder_threshold: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    batches: Mapped[list["Batch"]] = relationship(
        "Batch",
        back_populates="medicine",
        cascade="all, delete-orphan",
    )


# ============================================================
# Batch
# ============================================================

class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    medicine_id: Mapped[int] = mapped_column(
        ForeignKey(
            "medicines.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    batch_no: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    expiry_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    medicine: Mapped["Medicine"] = relationship(
        "Medicine",
        back_populates="batches",
    )

    expiry_alerts: Mapped[list["ExpiryAlert"]] = relationship(
        "ExpiryAlert",
        back_populates="batch",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "medicine_id",
            "batch_no",
            name="uq_medicine_batch",
        ),
        Index(
            "ix_batches_fefo",
            "medicine_id",
            "expiry_date",
            "id",
        ),
    )


# ============================================================
# Expiry Alert
# ============================================================

class ExpiryAlert(Base):
    __tablename__ = "expiry_alerts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    batch_id: Mapped[int] = mapped_column(
        ForeignKey(
            "batches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="open",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    batch: Mapped["Batch"] = relationship(
        "Batch",
        back_populates="expiry_alerts",
    )


# ============================================================
# Outbox Message
# ============================================================

class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    recipient: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

