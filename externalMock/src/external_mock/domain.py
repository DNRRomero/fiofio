from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class Source(StrEnum):
    CROWDSTRIKE_FALCON_EDR = "crowdstrike_falcon_edr"
    MICROSOFT_DEFENDER_FOR_IDENTITY = "microsoft_defender_for_identity"
    PALO_ALTO_NGFW = "palo_alto_ngfw"
    CLOUDFLARE_WAF = "cloudflare_waf"
    AWS_GUARDDUTY = "aws_guardduty"
    OKTA_THREATINSIGHT = "okta_threatinsight"
    PROOFPOINT_EMAIL_PROTECTION = "proofpoint_email_protection"
    SPLUNK_ENTERPRISE_SECURITY = "splunk_enterprise_security"
    TENABLE_VULNERABILITY_MANAGEMENT = "tenable_vulnerability_management"
    RECORDED_FUTURE_INTELLIGENCE_CLOUD = "recorded_future_intelligence_cloud"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Alert(BaseModel):
    id: UUID
    source: Source
    severity: Severity
    description: str
    created_at: datetime


class AlertsEnvelope(BaseModel):
    alerts: list[Alert]


DESCRIPTIONS = (
    "Suspicious process behavior.",
    "Flagged anomalous directory activity.",
    "Bocked traffic matching a known exploit signature.",
    "Detected repeated SQL injection attempts.",
    "Reported anomalous API usage in the account.",
    "Identified an impossible-travel login pattern.",
    "Quarantined a phishing attachment.",
    "Found multi-stage attack indicators.",
    "Reported new critical exposure.",
    "Matched traffic to a malicious IOC.",
)
