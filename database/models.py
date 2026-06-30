from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SMS(Base):
    __tablename__ = "sms"

    id = Column(Integer, primary_key=True)
    module_id = Column(String(64), index=True)
    modem_name = Column(String(128), default="")
    modem_model = Column(String(128), default="")
    imei = Column(String(64), index=True, default="")
    sms_index = Column(Integer, nullable=True)
    storage = Column(String(16), default="")
    phone = Column(String(64), index=True, default="")
    receive_time = Column(String(32), index=True, default="")
    content = Column(Text, default="")
    encoding = Column(String(32), default="UTF-8")
    is_read = Column(Boolean, default=True, index=True)
    is_synced = Column(Boolean, default=False, index=True)
    forwarded = Column(Boolean, default=False, index=True)
    forward_count = Column(Integer, default=0)
    last_forward_time = Column(String(32), default="")
    sync_time = Column(String(32), default="")
    hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_sms_filters", "module_id", "phone", "forwarded", "is_read", "receive_time"),
    )


class Modem(Base):
    __tablename__ = "modem"

    id = Column(Integer, primary_key=True)
    module_id = Column(String(64), unique=True, index=True)
    port = Column(String(128), unique=True, index=True)
    remark = Column(String(128), default="")
    model = Column(String(128), default="")
    firmware = Column(String(128), default="")
    imei = Column(String(64), index=True, default="")
    iccid = Column(String(64), default="")
    imsi = Column(String(64), default="")
    sim_status = Column(String(64), default="")
    operator_name = Column(String(128), default="")
    network_type = Column(String(64), default="")
    signal_raw = Column(String(64), default="")
    signal_percent = Column(Integer, default=0)
    is_online = Column(Boolean, default=False, index=True)
    is_roaming = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True, index=True)
    last_seen_at = Column(String(32), default="")
    last_init_at = Column(String(32), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MailLog(Base):
    __tablename__ = "mail_log"

    id = Column(Integer, primary_key=True)
    sms_id = Column(Integer, index=True, nullable=True)
    recipient = Column(String(255), index=True, default="")
    success = Column(Boolean, default=False, index=True)
    error_message = Column(Text, default="")
    sent_at = Column(String(32), index=True, default="")


class ATHistory(Base):
    __tablename__ = "at_history"

    id = Column(Integer, primary_key=True)
    module_id = Column(String(64), index=True, default="")
    command = Column(String(255), default="")
    response = Column(Text, default="")
    duration_ms = Column(Integer, default=0)
    success = Column(Boolean, default=False, index=True)
    created_at = Column(String(32), index=True, default="")


class SentSMS(Base):
    __tablename__ = "sent_sms"

    id = Column(Integer, primary_key=True)
    module_id = Column(String(64), index=True, default="")
    phone = Column(String(64), index=True, default="")
    content = Column(Text, default="")
    success = Column(Boolean, default=False, index=True)
    error_message = Column(Text, default="")
    sent_at = Column(String(32), index=True, default="")

    __table_args__ = (UniqueConstraint("module_id", "phone", "sent_at", name="uq_sent_sms_once"),)
