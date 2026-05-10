from pydantic import BaseModel, ConfigDict, field_serializer
from typing import Any, Optional, List
from datetime import datetime, date
from decimal import Decimal
import uuid


# ---- Service Schemas ----

class ServiceCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sort_order: int = 0


class ServiceCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool
    unit_id: Optional[uuid.UUID] = None
    service_ids: Optional[List[uuid.UUID]] = None
    model_config = ConfigDict(from_attributes=True)


class ServiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal = Decimal("0")
    duration_minutes: int
    buffer_before_minutes: int = 0
    buffer_after_minutes: int = 0
    category_id: Optional[uuid.UUID] = None
    image_url: Optional[str] = None
    requires_deposit: bool = False
    deposit_type: str = "none"
    deposit_value: Decimal = Decimal("0")


class ServiceUpdate(ServiceCreate):
    name: Optional[str] = None
    duration_minutes: Optional[int] = None


class ServiceResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    price: Decimal
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    category_id: Optional[uuid.UUID] = None
    image_url: Optional[str] = None
    requires_deposit: Optional[bool] = False
    deposit_type: Optional[str] = "none"
    is_active: bool
    unit_id: Optional[uuid.UUID] = None
    service_ids: Optional[List[uuid.UUID]] = None
    model_config = ConfigDict(from_attributes=True)


# ---- Professional Schemas ----

class ProfessionalCreate(BaseModel):
    name: str
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    unit_id: Optional[uuid.UUID] = None


class ProfessionalUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    unit_id: Optional[uuid.UUID] = None


class ProfessionalResponse(BaseModel):
    id: uuid.UUID
    name: str
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    unit_id: Optional[uuid.UUID] = None
    service_ids: Optional[List[uuid.UUID]] = None
    model_config = ConfigDict(from_attributes=True)


class ProfessionalServiceLink(BaseModel):
    service_ids: List[uuid.UUID]


class AvailabilityCreate(BaseModel):
    weekday: int
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    break_start_time: Optional[str] = None
    break_end_time: Optional[str] = None
    is_available: bool = True


class BusinessHourCreate(BaseModel):
    unit_id: Optional[uuid.UUID] = None
    weekday: int
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    break_start_time: Optional[str] = None
    break_end_time: Optional[str] = None
    is_closed: bool = False


class BusinessHourResponse(BaseModel):
    id: uuid.UUID
    unit_id: Optional[uuid.UUID] = None
    weekday: int
    open_time: Optional[Any] = None
    close_time: Optional[Any] = None
    is_closed: bool
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("open_time", "close_time")
    def serialize_time(self, v):
        if v is None: return None
        if hasattr(v, "strftime"): return v.strftime("%H:%M")
        return str(v)


class BlockedTimeCreate(BaseModel):
    professional_id: Optional[uuid.UUID] = None
    start_datetime: datetime
    end_datetime: datetime
    reason: Optional[str] = None
    block_type: str = "other"


class BlockedTimeResponse(BaseModel):
    id: uuid.UUID
    professional_id: Optional[uuid.UUID] = None
    start_datetime: datetime
    end_datetime: datetime
    reason: Optional[str] = None
    block_type: str
    model_config = ConfigDict(from_attributes=True)


# ---- Appointment Schemas ----

class AppointmentCreate(BaseModel):
    professional_id: uuid.UUID
    service_ids: List[uuid.UUID]
    start_datetime: datetime
    customer_notes: Optional[str] = None
    internal_notes: Optional[str] = None
    source: str = "admin_panel"
    customer_account_id: Optional[uuid.UUID] = None
    customer_package_id: Optional[uuid.UUID] = None
    idempotency_key: Optional[str] = None
    unit_id: Optional[uuid.UUID] = None


class AppointmentServiceSnapshot(BaseModel):
    service_id: Optional[uuid.UUID] = None
    package_session_id: Optional[uuid.UUID] = None
    service_name_snapshot: str
    service_price_snapshot: Decimal
    service_duration_snapshot: int
    model_config = ConfigDict(from_attributes=True)


class AppointmentResponse(BaseModel):
    id: uuid.UUID
    professional_id: uuid.UUID
    start_datetime: datetime
    end_datetime: datetime
    total_duration_minutes: int
    total_price: Decimal
    status: str
    payment_status: str
    uses_package: bool = False
    customer_package_id: Optional[uuid.UUID] = None
    source: str
    customer_notes: Optional[str] = None
    appointment_services: List[AppointmentServiceSnapshot] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AppointmentCancelRequest(BaseModel):
    reason: Optional[str] = None


class AppointmentRescheduleRequest(BaseModel):
    new_start_datetime: datetime
    reason: Optional[str] = None


# ---- Package Schemas ----

class PackageCreate(BaseModel):
    name: str
    description: Optional[str] = None
    total_sessions: int
    price: Decimal
    validity_days: Optional[int] = None
    service_ids: Optional[List[uuid.UUID]] = None


class PackageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    validity_days: Optional[int] = None
    is_active: Optional[bool] = None
    service_ids: Optional[List[uuid.UUID]] = None


class PackageResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    total_sessions: int
    price: Decimal
    validity_days: Optional[int] = None
    is_active: bool
    unit_id: Optional[uuid.UUID] = None
    service_ids: Optional[List[uuid.UUID]] = None
    model_config = ConfigDict(from_attributes=True)


class CustomerPackageCreate(BaseModel):
    customer_account_id: uuid.UUID
    package_id: uuid.UUID
    price_paid: Optional[Decimal] = None
    purchase_price: Optional[Decimal] = None
    payment_status: str = "pending"
    notes: Optional[str] = None


class CustomerPackageResponse(BaseModel):
    id: uuid.UUID
    package_id: uuid.UUID
    total_sessions: int
    used_sessions: int
    remaining_sessions: int
    status: str
    payment_status: str
    purchase_price: Optional[Decimal] = None
    created_by_user_id: Optional[uuid.UUID] = None
    expires_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# ---- Procedure History ----

class ProcedureHistoryCreate(BaseModel):
    title: str
    description: Optional[str] = None
    procedure_date: datetime
    public_notes: Optional[str] = None
    internal_notes: Optional[str] = None
    recommended_return_date: Optional[date] = None
    service_id: Optional[uuid.UUID] = None
    professional_id: Optional[uuid.UUID] = None


class ProcedureHistoryResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    procedure_date: datetime
    public_notes: Optional[str] = None
    recommended_return_date: Optional[date] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---- Dashboard ----

class DashboardResponse(BaseModel):
    today_appointments: int
    upcoming_appointments: int
    total_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    no_shows: int
    revenue_confirmed: float
    revenue_expected: float
    total_customers: int


# ---- Notification Template ----

class NotificationTemplateCreate(BaseModel):
    event_type: str
    channel: str
    subject: Optional[str] = None
    body: str
    is_active: bool = True


# ---- Webhook ----

class WebhookCreate(BaseModel):
    url: str
    secret: Optional[str] = None
    event_types: Optional[List[str]] = None
    is_active: bool = True


class WebhookResponse(BaseModel):
    id: uuid.UUID
    url: str
    event_types: Optional[List[str]] = None
    is_active: bool
    unit_id: Optional[uuid.UUID] = None
    service_ids: Optional[List[uuid.UUID]] = None
    model_config = ConfigDict(from_attributes=True)


# ---- Unit ----

class UnitCreate(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    timezone: Optional[str] = None
    is_main: bool = False


class UnitResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    is_main: bool
    is_active: bool
    unit_id: Optional[uuid.UUID] = None
    service_ids: Optional[List[uuid.UUID]] = None
    model_config = ConfigDict(from_attributes=True)


# ---- Customer Tag/Note ----

class CustomerTagCreate(BaseModel):
    name: str
    color: Optional[str] = None


class CustomerNoteCreate(BaseModel):
    content: Optional[str] = None
    note: Optional[str] = None
    is_internal: bool = True
    visibility: Optional[str] = None
    note_type: str = "manual"


# ---- Invite ----

class InviteCreate(BaseModel):
    email: str
    role: str
    phone: Optional[str] = None


class InviteAccept(BaseModel):
    token: str
    name: str
    password: str

# ---- Audit gap additions ----

class TenantPaymentSettingsUpdate(BaseModel):
    require_deposit_by_default: Optional[bool] = None
    default_deposit_type: Optional[str] = None
    default_deposit_value: Optional[Decimal] = None
    require_deposit_for_first_appointment: Optional[bool] = None
    require_deposit_after_no_show: Optional[bool] = None
    manual_payment_instructions: Optional[str] = None
    pix_key: Optional[str] = None


class TenantPaymentSettingsResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    require_deposit_by_default: bool
    default_deposit_type: str
    default_deposit_value: Decimal
    require_deposit_for_first_appointment: bool
    require_deposit_after_no_show: bool
    manual_payment_instructions: Optional[str] = None
    pix_key: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class PackageServicePayload(BaseModel):
    service_ids: List[uuid.UUID]


class PackageServiceResponse(BaseModel):
    id: uuid.UUID
    package_id: uuid.UUID
    service_id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReviewCreate(BaseModel):
    rating: int
    comment: Optional[str] = None
    visibility: str = "customer_visible"


class ReviewResponse(BaseModel):
    id: uuid.UUID
    appointment_id: uuid.UUID
    customer_account_id: uuid.UUID
    rating: int
    comment: Optional[str] = None
    visibility: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CouponCreate(BaseModel):
    code: str
    discount_type: str
    discount_value: Decimal
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    usage_limit: Optional[int] = None
    is_active: bool = True


class CouponUpdate(BaseModel):
    code: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    usage_limit: Optional[int] = None
    is_active: Optional[bool] = None


class CouponResponse(BaseModel):
    id: uuid.UUID
    code: str
    discount_type: str
    discount_value: Decimal
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    usage_limit: Optional[int] = None
    is_active: bool
    unit_id: Optional[uuid.UUID] = None
    service_ids: Optional[List[uuid.UUID]] = None
    model_config = ConfigDict(from_attributes=True)


class AppointmentHoldCreate(BaseModel):
    customer_account_id: Optional[uuid.UUID] = None
    professional_id: uuid.UUID
    start_datetime: datetime
    end_datetime: datetime
    service_ids: List[uuid.UUID]
    expires_at: datetime


class AppointmentHoldResponse(BaseModel):
    id: uuid.UUID
    customer_account_id: Optional[uuid.UUID] = None
    professional_id: uuid.UUID
    start_datetime: datetime
    end_datetime: datetime
    service_ids: List[uuid.UUID]
    expires_at: datetime
    status: str
    model_config = ConfigDict(from_attributes=True)


class CustomerProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    cpf: Optional[str] = None
    birth_date: Optional[date] = None
    notes: Optional[str] = None
    marketing_consent: Optional[bool] = None


class CustomerPortalProfileResponse(BaseModel):
    customer_account_id: uuid.UUID
    tenant_customer_id: Optional[uuid.UUID] = None
    name: str
    email: Optional[str] = None
    phone: str
    cpf: Optional[str] = None
    birth_date: Optional[date] = None
    notes: Optional[str] = None
    marketing_consent: Optional[bool] = None


# ---- Customer Portal safe response schemas ----

class CustomerPortalAppointmentServiceResponse(BaseModel):
    service_id: Optional[uuid.UUID] = None
    service_name_snapshot: str
    service_price_snapshot: Decimal
    service_duration_snapshot: int
    package_session_id: Optional[uuid.UUID] = None
    model_config = ConfigDict(from_attributes=True)


class CustomerPortalProfessionalResponse(BaseModel):
    id: uuid.UUID
    name: str
    photo_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class CustomerPortalUnitResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class CustomerPortalAppointmentResponse(BaseModel):
    id: uuid.UUID
    professional_id: uuid.UUID
    professional: Optional[CustomerPortalProfessionalResponse] = None
    unit: Optional[CustomerPortalUnitResponse] = None
    start_datetime: datetime
    end_datetime: datetime
    total_duration_minutes: int
    total_price: Decimal
    status: str
    payment_status: str
    source: str
    customer_notes: Optional[str] = None
    uses_package: bool = False
    customer_package_id: Optional[uuid.UUID] = None
    appointment_services: List[CustomerPortalAppointmentServiceResponse] = []
    model_config = ConfigDict(from_attributes=True)


class CustomerPortalPackageSessionResponse(BaseModel):
    id: uuid.UUID
    appointment_id: Optional[uuid.UUID] = None
    service_id: Optional[uuid.UUID] = None
    status: Optional[str] = None
    action: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CustomerPortalPackageResponse(BaseModel):
    id: uuid.UUID
    package_id: uuid.UUID
    total_sessions: int
    used_sessions: int
    remaining_sessions: int
    status: str
    payment_status: str
    purchase_price: Optional[Decimal] = None
    price_paid: Optional[Decimal] = None
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    sessions: List[CustomerPortalPackageSessionResponse] = []
    model_config = ConfigDict(from_attributes=True)


class CustomerPortalProcedureHistoryResponse(BaseModel):
    id: uuid.UUID
    appointment_id: Optional[uuid.UUID] = None
    professional_id: Optional[uuid.UUID] = None
    service_id: Optional[uuid.UUID] = None
    title: str
    description: Optional[str] = None
    procedure_date: datetime
    public_notes: Optional[str] = None
    recommended_return_date: Optional[date] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
