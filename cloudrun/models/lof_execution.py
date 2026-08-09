# -*- coding: utf-8 -*-
"""LOF 场内申赎规则的版本化证据模型。"""

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from models.database import Base


class LofExecutionFund(Base):
    __tablename__ = 'lof_execution_fund'

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, unique=True, index=True)
    fund_name = Column(String(200), nullable=True)
    exchange = Column(String(10), nullable=False, index=True)
    share_class = Column(String(80), nullable=False, default='listed')
    discovery_status = Column(String(30), nullable=False, default='unavailable')
    discovery_reason = Column(String(500), nullable=True)
    subscription_status = Column(String(20), nullable=True)
    redemption_status = Column(String(20), nullable=True)
    status_checked_at = Column(DateTime, nullable=True)
    status_source_url = Column(String(1000), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LofExecutionEvidence(Base):
    __tablename__ = 'lof_execution_evidence'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_kind = Column(String(50), nullable=False)
    source_identifier = Column(String(200), nullable=False)
    source_title = Column(String(500), nullable=False)
    source_url = Column(String(1000), nullable=False)
    applies_to = Column(String(80), nullable=False)
    published_at = Column(Date, nullable=True)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    verified_at = Column(DateTime, nullable=False, server_default=func.now())
    content_hash = Column(String(128), nullable=True)
    excerpt = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('source_kind', 'source_identifier', name='uq_lof_execution_evidence'),
    )


class LofExecutionRule(Base):
    __tablename__ = 'lof_execution_rule'

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey('lof_execution_fund.id'), nullable=True, index=True)
    exchange = Column(String(10), nullable=False, index=True)
    share_class = Column(String(80), nullable=False, default='listed')
    field_key = Column(String(80), nullable=False, index=True)
    value_text = Column(String(200), nullable=True)
    numeric_value = Column(Float, nullable=True)
    unit = Column(String(20), nullable=True)
    status = Column(String(30), nullable=False, default='verified')
    reason = Column(String(500), nullable=True)
    source_priority = Column(Integer, nullable=False, default=0)
    evidence_id = Column(Integer, ForeignKey('lof_execution_evidence.id'), nullable=True)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('fund_id', 'exchange', 'share_class', 'field_key', 'evidence_id', name='uq_lof_execution_rule_version'),
    )


class LofExecutionJob(Base):
    __tablename__ = 'lof_execution_job'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(40), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default='pending')
    cursor = Column(Text, nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
