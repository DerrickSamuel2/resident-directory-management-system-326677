from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type (always 'bearer')")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password (plaintext)")


class MeResponse(BaseModel):
    user_id: uuid.UUID = Field(..., description="Authenticated user id")
    email: str = Field(..., description="Authenticated user email")
    full_name: str | None = Field(None, description="Full name")
    roles: list[str] = Field(default_factory=list, description="Role names for RBAC")
    resident_id: uuid.UUID | None = Field(None, description="Linked resident profile id, if any")


class ResidentPrivacySettingsIn(BaseModel):
    show_email: bool = Field(False, description="Whether email is visible in directory")
    show_phone: bool = Field(False, description="Whether phone is visible in directory")
    show_unit: bool = Field(True, description="Whether unit number is visible in directory")
    allow_messages: bool = Field(True, description="Whether other residents can message this resident")
    directory_visible: bool = Field(True, description="Whether resident shows in directory listings")


class ResidentPrivacySettingsOut(ResidentPrivacySettingsIn):
    resident_id: uuid.UUID = Field(..., description="Resident id")
    updated_at: datetime = Field(..., description="Last update time")


class ResidentBase(BaseModel):
    unit_number: str | None = Field(None, description="Unit/apartment number")
    building: str | None = Field(None, description="Building name/label")
    phone: str | None = Field(None, description="Phone number")
    email: str | None = Field(None, description="Email address (may match user email)")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    bio: str | None = Field(None, description="Short bio")
    profile_image_url: str | None = Field(None, description="URL to profile image")
    is_active: bool = Field(True, description="Whether profile is active")


class ResidentCreate(ResidentBase):
    user_id: uuid.UUID | None = Field(None, description="Optional link to an existing user account")
    privacy: ResidentPrivacySettingsIn | None = Field(None, description="Optional initial privacy settings")


class ResidentUpdate(BaseModel):
    unit_number: str | None = Field(None, description="Unit/apartment number")
    building: str | None = Field(None, description="Building name/label")
    phone: str | None = Field(None, description="Phone number")
    email: str | None = Field(None, description="Email address")
    first_name: str | None = Field(None, description="First name")
    last_name: str | None = Field(None, description="Last name")
    bio: str | None = Field(None, description="Short bio")
    profile_image_url: str | None = Field(None, description="URL to profile image")
    is_active: bool | None = Field(None, description="Whether profile is active")
    privacy: ResidentPrivacySettingsIn | None = Field(None, description="Updated privacy settings (partial overwrite)")


class ResidentOut(ResidentBase):
    id: uuid.UUID = Field(..., description="Resident id")
    user_id: uuid.UUID | None = Field(None, description="Linked user account id")
    created_at: datetime = Field(..., description="Created time")
    updated_at: datetime = Field(..., description="Updated time")
    privacy: ResidentPrivacySettingsOut | None = Field(None, description="Privacy settings")


class DirectoryResidentOut(BaseModel):
    """
    Privacy-projected resident profile for directory browsing.

    Only fields allowed by the target resident's privacy settings are included.
    """

    id: uuid.UUID = Field(..., description="Resident id")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    building: str | None = Field(None, description="Building")
    unit_number: str | None = Field(None, description="Unit number (if allowed)")
    bio: str | None = Field(None, description="Bio")
    profile_image_url: str | None = Field(None, description="Profile image URL")
    email: str | None = Field(None, description="Email (if allowed)")
    phone: str | None = Field(None, description="Phone (if allowed)")
    allow_messages: bool = Field(True, description="Whether this resident accepts messages")


class MessageCreate(BaseModel):
    recipient_user_id: uuid.UUID = Field(..., description="Recipient user id")
    subject: str | None = Field(None, description="Optional subject")
    body: str = Field(..., description="Message body")


class MessageOut(BaseModel):
    id: uuid.UUID = Field(..., description="Message id")
    sender_user_id: uuid.UUID | None = Field(None, description="Sender user id")
    recipient_user_id: uuid.UUID | None = Field(None, description="Recipient user id")
    subject: str | None = Field(None, description="Subject")
    body: str = Field(..., description="Body")
    sent_at: datetime = Field(..., description="Sent timestamp")
    read_at: datetime | None = Field(None, description="Read timestamp")


class NotificationOut(BaseModel):
    id: uuid.UUID = Field(..., description="Notification id")
    type: str = Field(..., description="Notification type")
    title: str | None = Field(None, description="Title")
    body: str | None = Field(None, description="Body")
    data: dict[str, Any] = Field(default_factory=dict, description="Arbitrary payload")
    created_at: datetime = Field(..., description="Created timestamp")
    read_at: datetime | None = Field(None, description="Read timestamp")


class AuditLogOut(BaseModel):
    id: uuid.UUID = Field(..., description="Audit id")
    actor_user_id: uuid.UUID | None = Field(None, description="Actor user id")
    action: str = Field(..., description="Action string")
    entity_type: str = Field(..., description="Entity type/table")
    entity_id: uuid.UUID | None = Field(None, description="Entity id")
    details: dict[str, Any] = Field(default_factory=dict, description="Extra details")
    ip_address: str | None = Field(None, description="IP address")
    user_agent: str | None = Field(None, description="User agent")
    created_at: datetime = Field(..., description="Created timestamp")
