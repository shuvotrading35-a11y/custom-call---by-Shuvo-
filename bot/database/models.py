"""
SQLAlchemy 2.x async ORM models — full schema for Bangladesh Call Bot.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, JSON, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─── Users ────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id             = Column(BigInteger, primary_key=True)  # Telegram user ID
    username       = Column(String(64), nullable=True)
    full_name      = Column(String(128), nullable=True)
    phone          = Column(String(20), nullable=True)
    credits        = Column(Integer, default=0)
    total_spent    = Column(Integer, default=0)           # in BDT
    membership     = Column(String(20), default="Free")
    referral_code  = Column(String(16), unique=True, nullable=True)
    referred_by    = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    is_banned      = Column(Boolean, default=False)
    ban_reason     = Column(Text, nullable=True)
    ban_until      = Column(DateTime, nullable=True)
    is_active      = Column(Boolean, default=True)
    language       = Column(String(4), default="bn")
    joined_at      = Column(DateTime, server_default=func.now())
    last_seen      = Column(DateTime, server_default=func.now(), onupdate=func.now())

    calls          = relationship("Call", back_populates="user")
    payments       = relationship("Payment", back_populates="user")
    campaigns      = relationship("BulkCampaign", back_populates="user")
    tickets        = relationship("SupportTicket", back_populates="user")


# ─── Admins ───────────────────────────────────────────────────────────────────
class Admin(Base):
    __tablename__ = "admins"

    id          = Column(BigInteger, primary_key=True)   # Telegram user ID
    username    = Column(String(64), nullable=True)
    role        = Column(String(32), default="moderator")
    permissions = Column(JSON, default=dict)
    is_active   = Column(Boolean, default=True)
    added_at    = Column(DateTime, server_default=func.now())
    added_by    = Column(BigInteger, nullable=True)


# ─── Calls ────────────────────────────────────────────────────────────────────
class Call(Base):
    __tablename__ = "calls"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    user_id          = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    number           = Column(String(20), nullable=False)
    operator         = Column(String(30), nullable=True)
    message          = Column(Text, nullable=True)
    voice            = Column(String(10), default="female")
    language         = Column(String(4), default="bn")
    call_type        = Column(String(10), default="tts")   # tts | voice
    audio_url        = Column(Text, nullable=True)
    status           = Column(String(20), default="pending")
    external_call_id = Column(String(64), nullable=True)   # was call_id
    api_response     = Column(JSON, nullable=True)
    credits_used     = Column(Integer, default=1)
    campaign_id      = Column(Integer, ForeignKey("bulk_campaigns.id"), nullable=True)
    retry_count      = Column(Integer, default=0)
    error_message    = Column(Text, nullable=True)         # was error_msg
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user         = relationship("User", back_populates="calls")
    campaign     = relationship("BulkCampaign", back_populates="calls")


# ─── Bulk Campaigns ───────────────────────────────────────────────────────────
class BulkCampaign(Base):
    __tablename__ = "bulk_campaigns"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    user_id             = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    name                = Column(String(128), nullable=False)
    description         = Column(Text, nullable=True)
    message             = Column(Text, nullable=True)
    voice               = Column(String(10), default="female")
    language            = Column(String(4), default="bn")
    call_type           = Column(String(10), default="tts")
    audio_url           = Column(Text, nullable=True)
    status              = Column(String(20), default="draft")
    total_recipients    = Column(Integer, default=0)
    completed           = Column(Integer, default=0)
    failed              = Column(Integer, default=0)
    retrying            = Column(Integer, default=0)
    retry_attempts      = Column(Integer, default=2)
    max_concurrent      = Column(Integer, default=5)
    call_timeout        = Column(Integer, default=30)
    call_interval       = Column(Integer, default=3)
    dnd_start_hour      = Column(Integer, nullable=True)
    dnd_end_hour        = Column(Integer, nullable=True)
    schedule_type       = Column(String(20), default="immediate")
    scheduled_at        = Column(DateTime, nullable=True)
    recurrence          = Column(String(20), default="once")
    celery_task_id      = Column(String(128), nullable=True)
    credits_used        = Column(Integer, default=0)
    created_at          = Column(DateTime, server_default=func.now())
    updated_at          = Column(DateTime, server_default=func.now(), onupdate=func.now())
    completed_at        = Column(DateTime, nullable=True)

    user                = relationship("User", back_populates="campaigns")
    calls               = relationship("Call", back_populates="campaign")
    recipients          = relationship("BulkRecipient", back_populates="campaign")
    report              = relationship("BulkReport", back_populates="campaign", uselist=False)


# ─── Bulk Recipients ──────────────────────────────────────────────────────────
class BulkRecipient(Base):
    __tablename__ = "bulk_recipients"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("bulk_campaigns.id"), nullable=False)
    number      = Column(String(20), nullable=False)
    operator    = Column(String(30), nullable=True)
    status      = Column(String(20), default="pending")
    call_id     = Column(String(64), nullable=True)
    error_msg   = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    attempted_at= Column(DateTime, nullable=True)

    campaign    = relationship("BulkCampaign", back_populates="recipients")


# ─── Bulk Reports ─────────────────────────────────────────────────────────────
class BulkReport(Base):
    __tablename__ = "bulk_reports"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("bulk_campaigns.id"), unique=True)
    total       = Column(Integer, default=0)
    success     = Column(Integer, default=0)
    failed      = Column(Integer, default=0)
    success_rate= Column(String(10), default="0%")
    duration_s  = Column(Integer, default=0)
    report_data = Column(JSON, nullable=True)
    generated_at= Column(DateTime, server_default=func.now())

    campaign    = relationship("BulkCampaign", back_populates="report")


# ─── Payments ─────────────────────────────────────────────────────────────────
class Payment(Base):
    __tablename__ = "payments"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    user_id          = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    method           = Column(String(20), nullable=False)   # bkash | nagad | rocket
    amount_bdt       = Column(Integer, nullable=False)       # BDT (was: amount)
    credits          = Column(Integer, nullable=False)
    trx_id           = Column(String(64), nullable=True)
    screenshot       = Column(Text, nullable=True)           # File ID
    status           = Column(String(20), default="pending")
    package_id       = Column(Integer, ForeignKey("credit_packages.id"), nullable=True)
    merchant_number  = Column(String(20), nullable=True)     # new
    reviewed_by      = Column(BigInteger, nullable=True)     # Admin ID
    reject_reason    = Column(Text, nullable=True)
    verified_by      = Column(BigInteger, nullable=True)     # new
    verified_at      = Column(DateTime, nullable=True)       # new
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user         = relationship("User", back_populates="payments")
    package      = relationship("CreditPackage", back_populates="payments")


# ─── Credit Packages ──────────────────────────────────────────────────────────
class CreditPackage(Base):
    __tablename__ = "credit_packages"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(64), nullable=False)
    credits     = Column(Integer, nullable=False)
    price_bdt   = Column(Integer, nullable=False)         # BDT (was: price)
    bonus       = Column(Integer, default=0)              # Extra credits
    is_active   = Column(Boolean, default=True)
    sort_order  = Column(Integer, default=0)
    created_at  = Column(DateTime, server_default=func.now())

    payments    = relationship("Payment", back_populates="package")


# ─── Redeem Codes ─────────────────────────────────────────────────────────────
class RedeemCode(Base):
    __tablename__ = "redeem_codes"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    code            = Column(String(32), unique=True, nullable=False)
    code_type       = Column(String(20), default="gift")
    credits         = Column(Integer, default=0)
    bonus_percent   = Column(Integer, default=0)
    max_uses        = Column(Integer, default=1)
    used_count      = Column(Integer, default=0)
    max_per_user    = Column(Integer, default=1)
    expires_at      = Column(DateTime, nullable=True)
    is_active       = Column(Boolean, default=True)
    created_by      = Column(BigInteger, nullable=True)
    created_at      = Column(DateTime, server_default=func.now())

    redemptions     = relationship("RedeemLog", back_populates="code")


# ─── Redeem Logs ──────────────────────────────────────────────────────────────
class RedeemLog(Base):
    __tablename__ = "redeem_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    code_id     = Column(Integer, ForeignKey("redeem_codes.id"), nullable=False)
    user_id     = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    credits     = Column(Integer, default=0)
    redeemed_at = Column(DateTime, server_default=func.now())

    code        = relationship("RedeemCode", back_populates="redemptions")


# ─── Referrals ────────────────────────────────────────────────────────────────
class Referral(Base):
    __tablename__ = "referrals"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id   = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    referred_id   = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    reward_credits= Column(Integer, default=0)
    reward_paid   = Column(Boolean, default=False)     # was reward_held (inverted logic)
    release_at    = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, server_default=func.now())


# ─── Support Tickets ──────────────────────────────────────────────────────────
class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    user_id            = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    category           = Column(String(64), nullable=False)
    subject            = Column(String(256), nullable=False)
    description        = Column(Text, nullable=True)       # new
    screenshot_file_id = Column(String(256), nullable=True) # new
    status             = Column(String(20), default="open")
    assigned_to        = Column(BigInteger, nullable=True)
    created_at         = Column(DateTime, server_default=func.now())
    updated_at         = Column(DateTime, server_default=func.now(), onupdate=func.now())
    closed_at          = Column(DateTime, nullable=True)

    user        = relationship("User", back_populates="tickets")
    messages    = relationship("TicketMessage", back_populates="ticket")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id   = Column(Integer, ForeignKey("support_tickets.id"), nullable=False)
    sender_id   = Column(BigInteger, nullable=False)
    is_admin    = Column(Boolean, default=False)
    text        = Column(Text, nullable=True)
    file_id     = Column(String(256), nullable=True)
    created_at  = Column(DateTime, server_default=func.now())

    ticket      = relationship("SupportTicket", back_populates="messages")


# ─── Settings ─────────────────────────────────────────────────────────────────
class Setting(Base):
    __tablename__ = "settings"

    key         = Column(String(64), primary_key=True)
    value       = Column(Text, nullable=True)
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by  = Column(BigInteger, nullable=True)


# ─── Blacklist ────────────────────────────────────────────────────────────────
class Blacklist(Base):
    __tablename__ = "blacklist"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    type        = Column(String(20), nullable=False)  # number | user
    value       = Column(String(64), nullable=False, unique=True)
    reason      = Column(Text, nullable=True)
    added_by    = Column(BigInteger, nullable=True)
    added_at    = Column(DateTime, server_default=func.now())


# ─── Audit Logs ───────────────────────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    actor_id    = Column(BigInteger, nullable=False)
    actor_type  = Column(String(10), default="admin")
    action      = Column(String(64), nullable=False)
    target_id   = Column(String(64), nullable=True)    # e.g. user id, payment id
    target_type = Column(String(32), nullable=True)    # e.g. "user", "payment"
    details     = Column(JSON, nullable=True)
    ip_address  = Column(String(45), nullable=True)
    created_at  = Column(DateTime, server_default=func.now())


# ─── Error Logs ───────────────────────────────────────────────────────────────
class ErrorLog(Base):
    __tablename__ = "error_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    module      = Column(String(64), nullable=True)
    error_type  = Column(String(64), nullable=True)
    message     = Column(Text, nullable=True)
    traceback   = Column(Text, nullable=True)
    user_id     = Column(BigInteger, nullable=True)
    created_at  = Column(DateTime, server_default=func.now())


# ─── API Logs ─────────────────────────────────────────────────────────────────
class ApiLog(Base):
    __tablename__ = "api_logs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    call_id         = Column(Integer, ForeignKey("calls.id"), nullable=True)
    user_id         = Column(BigInteger, nullable=True)
    number          = Column(String(20), nullable=True)
    message_preview = Column(Text, nullable=True)       # was message_text
    voice           = Column(String(10), nullable=True)
    request_url     = Column(Text, nullable=True)       # was api_url
    status_code     = Column(Integer, nullable=True)    # was status (String)
    response        = Column(JSON, nullable=True)
    latency_ms      = Column(Integer, nullable=True)
    success         = Column(Boolean, default=False)    # new
    created_at      = Column(DateTime, server_default=func.now())
