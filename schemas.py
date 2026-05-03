from typing import Any, Optional

from pydantic import BaseModel


def model_dump(data: BaseModel):
    if hasattr(data, "model_dump"):
        return data.model_dump(exclude_none=True)
    return data.dict(exclude_none=True)


class AuthLogin(BaseModel):
    username: str
    password: str


class AuthMfaVerify(BaseModel):
    challenge_token: str
    code: str


class AuthRegister(BaseModel):
    name: str
    username: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None


class PasswordResetRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None


class PasswordResetConfirm(BaseModel):
    token: str
    password: str


class VerificationRequest(BaseModel):
    channel: str


class VerificationConfirm(BaseModel):
    channel: str
    code: str


class TwoFactorToggle(BaseModel):
    enabled: bool


class AppointmentCreate(BaseModel):
    user_id: Optional[int] = None
    doctor_user_id: Optional[int] = None
    doctor: Optional[str] = None
    date: str
    time: str
    reason: Optional[str] = ""


class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = ""
    user_id: Optional[int] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    dob: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    blood_type: Optional[str] = None
    iin: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    department: Optional[str] = None


class AnalysisOrderCreate(BaseModel):
    name: str
    scheduled_for: Optional[str] = None
    doctor_note: Optional[str] = None
    is_visible_to_patient: Optional[bool] = True


class AnalysisLabUpdate(BaseModel):
    status: str
    results: Optional[list[dict[str, Any]]] = None
    ready_at: Optional[str] = None
    lab_note: Optional[str] = None
    is_visible_to_patient: Optional[bool] = None


class AnalysisReviewUpdate(BaseModel):
    doctor_note: Optional[str] = None


class AdminUserCreate(BaseModel):
    name: str
    username: str
    password: str
    role: str = "user"
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    address: Optional[str] = None
    dob: Optional[str] = None
    blood_type: Optional[str] = None
    iin: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    password: Optional[str] = None
    two_factor_enabled: Optional[bool] = None
