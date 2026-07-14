"""รวม import ทุก model ไว้ที่เดียว เพื่อให้ Alembic autogenerate มองเห็นครบ"""
from app.models.enums import (
    Role,
    TripStatus,
    TripDifficulty,
    ReceiptKind,
    CorrectionStatus,
    GpsEvent,
    InspectionStatus,
    AdvanceStatus,
    IncidentKind,
    IncidentStatus,
)
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.trip import Trip, Drop, Receipt
from app.models.correction import Correction
from app.models.audit import AuditLog
from app.models.gps import GpsLog
from app.models.penalty import Penalty
from app.models.notification import Notification
from app.models.inspection import Inspection
from app.models.advance import Advance
from app.models.incident import Incident

__all__ = [
    "Role",
    "TripStatus",
    "TripDifficulty",
    "ReceiptKind",
    "CorrectionStatus",
    "GpsEvent",
    "InspectionStatus",
    "AdvanceStatus",
    "IncidentKind",
    "IncidentStatus",
    "User",
    "Vehicle",
    "Trip",
    "Drop",
    "Receipt",
    "Correction",
    "AuditLog",
    "GpsLog",
    "Penalty",
    "Notification",
    "Inspection",
    "Advance",
    "Incident",
]
