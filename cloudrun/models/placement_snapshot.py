# -*- coding: utf-8 -*-
"""Durable, source-aware snapshots for pending convertible placements."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from models.database import Base


class PlacementCandidate(Base):
    __tablename__ = 'placement_candidate'

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_key = Column(String(80), nullable=False, unique=True, index=True)
    stock_code = Column(String(20), nullable=False, index=True)
    bond_code = Column(String(20), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PlacementSnapshot(Base):
    __tablename__ = 'placement_snapshot'

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey('placement_candidate.id'), nullable=False, unique=True, index=True)
    payload = Column(Text, nullable=False, default='{}')
    registration_date = Column(String(20), nullable=True, index=True)
    data_as_of = Column(DateTime, nullable=False, server_default=func.now())
    freshness_state = Column(String(20), nullable=False, default='fresh')
    stale_reason = Column(String(500), nullable=True)
    verification_state = Column(String(30), nullable=False, default='unverified')
    review_required = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PlacementObservation(Base):
    __tablename__ = 'placement_observation'

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey('placement_candidate.id'), nullable=False, index=True)
    field_group = Column(String(30), nullable=False, default='snapshot')
    observed_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    source_kind = Column(String(50), nullable=False, default='market')
    source_priority = Column(Integer, nullable=False, default=0)
    source_evidence_id = Column(Integer, ForeignKey('placement_source_evidence.id'), nullable=True)
    payload = Column(Text, nullable=False, default='{}')
    reconciliation_result = Column(String(30), nullable=False, default='accepted')
    calculation_version = Column(String(30), nullable=True)
    input_snapshot_id = Column(Integer, ForeignKey('placement_snapshot.id'), nullable=True)


class PlacementSourceEvidence(Base):
    __tablename__ = 'placement_source_evidence'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_kind = Column(String(50), nullable=False)
    source_identifier = Column(String(200), nullable=False)
    source_url = Column(String(1000), nullable=True)
    published_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    content_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint('source_kind', 'source_identifier', name='uq_placement_source_evidence'),)


class PlacementRefreshJob(Base):
    __tablename__ = 'placement_refresh_job'

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(50), nullable=False, default='pending', index=True)
    status = Column(String(20), nullable=False, default='queued', index=True)
    attempts = Column(Integer, nullable=False, default=0)
    requested_at = Column(DateTime, nullable=False, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)
    last_error = Column(String(1000), nullable=True)
