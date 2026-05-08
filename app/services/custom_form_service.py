from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.custom_form import (
    CustomForm, CustomFormField, CustomFormResponse as CustomFormResponseModel,
    FormType, FieldType,
)
from app.models.appointment import Appointment
from app.models.customer import TenantCustomer
from app.core.exceptions import NotFoundError, ForbiddenError, ValidationError
from app.services.audit_service import audit_service
from app.services.customer_event_service import customer_event_service
from app.services.feature_flag_service import feature_flag_service

FEATURE_KEY = "custom_forms"


class CustomFormService:

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _require_feature(self, db: Session, tenant) -> None:
        feature_flag_service.require_feature(db, tenant, FEATURE_KEY)

    def _get_form(self, db: Session, tenant_id: UUID, form_id: UUID) -> CustomForm:
        form = db.query(CustomForm).filter(
            CustomForm.id == form_id,
            CustomForm.tenant_id == tenant_id,
        ).first()
        if not form:
            raise NotFoundError("Formulário não encontrado.")
        return form

    def _get_field(self, db: Session, tenant_id: UUID, form_id: UUID, field_id: UUID) -> CustomFormField:
        field = db.query(CustomFormField).filter(
            CustomFormField.id == field_id,
            CustomFormField.form_id == form_id,
            CustomFormField.tenant_id == tenant_id,
        ).first()
        if not field:
            raise NotFoundError("Campo não encontrado.")
        return field

    def _get_response(self, db: Session, tenant_id: UUID, response_id: UUID) -> CustomFormResponseModel:
        resp = db.query(CustomFormResponseModel).filter(
            CustomFormResponseModel.id == response_id,
            CustomFormResponseModel.tenant_id == tenant_id,
        ).first()
        if not resp:
            raise NotFoundError("Resposta não encontrada.")
        return resp

    def validate_answers(
        self,
        fields: List[CustomFormField],
        answers: Dict[str, Any],
    ) -> None:
        """Validate submitted answers against form field definitions."""
        for field in fields:
            field_id = str(field.id)
            value = answers.get(field_id)

            if field.required and (value is None or value == "" or value == []):
                raise ValidationError(f"Campo obrigatório não preenchido: '{field.label}'.")

            if value is None:
                continue

            if field.field_type == FieldType.select:
                allowed = field.options or []
                if value not in allowed:
                    raise ValidationError(
                        f"Valor '{value}' inválido para o campo '{field.label}'. "
                        f"Opções: {allowed}"
                    )

            if field.field_type == FieldType.multiselect:
                allowed = field.options or []
                if not isinstance(value, list):
                    raise ValidationError(f"Campo '{field.label}' deve ser uma lista.")
                invalid = [v for v in value if v not in allowed]
                if invalid:
                    raise ValidationError(
                        f"Opções inválidas para '{field.label}': {invalid}. "
                        f"Permitidas: {allowed}"
                    )

    # ── Admin — Forms ──────────────────────────────────────────────────────────

    def list_forms(
        self,
        db: Session,
        tenant,
        form_type: Optional[FormType] = None,
        is_active: Optional[bool] = None,
    ) -> List[CustomForm]:
        self._require_feature(db, tenant)
        q = db.query(CustomForm).filter(CustomForm.tenant_id == tenant.id)
        if form_type is not None:
            q = q.filter(CustomForm.form_type == form_type)
        if is_active is not None:
            q = q.filter(CustomForm.is_active == is_active)
        return q.order_by(CustomForm.created_at.desc()).all()

    def get_form(self, db: Session, tenant, form_id: UUID) -> CustomForm:
        self._require_feature(db, tenant)
        return self._get_form(db, tenant.id, form_id)

    def create_form(
        self,
        db: Session,
        tenant,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CustomForm:
        self._require_feature(db, tenant)
        form = CustomForm(tenant_id=tenant.id, **data)
        db.add(form)
        db.flush()
        audit_service.log(
            db=db, action="custom_form_created", entity_type="custom_form",
            entity_id=form.id, tenant_id=tenant.id, user_id=user_id,
            new_values={"title": form.title, "form_type": form.form_type.value},
            ip_address=ip_address, user_agent=user_agent,
        )
        db.commit()
        db.refresh(form)
        return form

    def update_form(
        self,
        db: Session,
        tenant,
        form_id: UUID,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CustomForm:
        self._require_feature(db, tenant)
        form = self._get_form(db, tenant.id, form_id)
        old = {"title": form.title, "form_type": form.form_type.value, "is_active": form.is_active}
        for k, v in data.items():
            if v is not None:
                setattr(form, k, v)
        db.flush()
        audit_service.log(
            db=db, action="custom_form_updated", entity_type="custom_form",
            entity_id=form.id, tenant_id=tenant.id, user_id=user_id,
            old_values=old,
            new_values={"title": form.title, "form_type": form.form_type.value, "is_active": form.is_active},
            ip_address=ip_address, user_agent=user_agent,
        )
        db.commit()
        db.refresh(form)
        return form

    def set_form_status(
        self,
        db: Session,
        tenant,
        form_id: UUID,
        is_active: bool,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CustomForm:
        self._require_feature(db, tenant)
        form = self._get_form(db, tenant.id, form_id)
        old = form.is_active
        form.is_active = is_active
        db.flush()
        action = "custom_form_activated" if is_active else "custom_form_deactivated"
        audit_service.log(
            db=db, action=action, entity_type="custom_form",
            entity_id=form.id, tenant_id=tenant.id, user_id=user_id,
            old_values={"is_active": old}, new_values={"is_active": is_active},
            ip_address=ip_address, user_agent=user_agent,
        )
        db.commit()
        db.refresh(form)
        return form

    # ── Admin — Fields ─────────────────────────────────────────────────────────

    def add_field(
        self,
        db: Session,
        tenant,
        form_id: UUID,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CustomFormField:
        self._require_feature(db, tenant)
        self._get_form(db, tenant.id, form_id)  # validates ownership
        field = CustomFormField(tenant_id=tenant.id, form_id=form_id, **data)
        db.add(field)
        db.flush()
        audit_service.log(
            db=db, action="custom_form_field_added", entity_type="custom_form_field",
            entity_id=field.id, tenant_id=tenant.id, user_id=user_id,
            new_values={"label": field.label, "field_type": field.field_type.value, "required": field.required},
            ip_address=ip_address, user_agent=user_agent,
        )
        db.commit()
        db.refresh(field)
        return field

    def update_field(
        self,
        db: Session,
        tenant,
        form_id: UUID,
        field_id: UUID,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CustomFormField:
        self._require_feature(db, tenant)
        field = self._get_field(db, tenant.id, form_id, field_id)
        old = {"label": field.label, "field_type": field.field_type.value}
        for k, v in data.items():
            if v is not None:
                setattr(field, k, v)
        db.flush()
        audit_service.log(
            db=db, action="custom_form_field_updated", entity_type="custom_form_field",
            entity_id=field.id, tenant_id=tenant.id, user_id=user_id,
            old_values=old,
            new_values={"label": field.label, "field_type": field.field_type.value},
            ip_address=ip_address, user_agent=user_agent,
        )
        db.commit()
        db.refresh(field)
        return field

    def delete_field(
        self,
        db: Session,
        tenant,
        form_id: UUID,
        field_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self._require_feature(db, tenant)
        field = self._get_field(db, tenant.id, form_id, field_id)
        audit_service.log(
            db=db, action="custom_form_field_deleted", entity_type="custom_form_field",
            entity_id=field.id, tenant_id=tenant.id, user_id=user_id,
            old_values={"label": field.label},
            ip_address=ip_address, user_agent=user_agent,
        )
        db.delete(field)
        db.commit()

    # ── Admin — Responses ──────────────────────────────────────────────────────

    def list_responses(
        self,
        db: Session,
        tenant,
        form_id: UUID,
    ) -> List[CustomFormResponseModel]:
        self._require_feature(db, tenant)
        self._get_form(db, tenant.id, form_id)
        return (
            db.query(CustomFormResponseModel)
            .filter(
                CustomFormResponseModel.tenant_id == tenant.id,
                CustomFormResponseModel.form_id == form_id,
            )
            .order_by(CustomFormResponseModel.submitted_at.desc())
            .all()
        )

    def get_response(self, db: Session, tenant, response_id: UUID) -> CustomFormResponseModel:
        self._require_feature(db, tenant)
        return self._get_response(db, tenant.id, response_id)

    # ── Customer portal ────────────────────────────────────────────────────────

    def list_active_forms_for_customer(self, db: Session, tenant) -> List[CustomForm]:
        self._require_feature(db, tenant)
        return (
            db.query(CustomForm)
            .filter(CustomForm.tenant_id == tenant.id, CustomForm.is_active == True)
            .order_by(CustomForm.created_at.asc())
            .all()
        )

    def get_active_form_for_customer(self, db: Session, tenant, form_id: UUID) -> CustomForm:
        self._require_feature(db, tenant)
        form = db.query(CustomForm).filter(
            CustomForm.id == form_id,
            CustomForm.tenant_id == tenant.id,
            CustomForm.is_active == True,
        ).first()
        if not form:
            raise NotFoundError("Formulário não encontrado ou inativo.")
        return form

    def submit_response(
        self,
        db: Session,
        tenant,
        form_id: UUID,
        customer_account_id: UUID,
        answers: Dict[str, Any],
        appointment_id: Optional[UUID] = None,
    ) -> CustomFormResponseModel:
        self._require_feature(db, tenant)
        form = self.get_active_form_for_customer(db, tenant, form_id)

        # Validate appointment belongs to tenant and customer
        if appointment_id:
            appt = db.query(Appointment).filter(
                Appointment.id == appointment_id,
                Appointment.tenant_id == tenant.id,
                Appointment.customer_account_id == customer_account_id,
            ).first()
            if not appt:
                raise ForbiddenError("Appointment não encontrado para este cliente/tenant.")

        # Get tenant_customer link
        tc = db.query(TenantCustomer).filter(
            TenantCustomer.tenant_id == tenant.id,
            TenantCustomer.customer_account_id == customer_account_id,
        ).first()

        # Load fields sorted
        fields = (
            db.query(CustomFormField)
            .filter(CustomFormField.form_id == form_id, CustomFormField.tenant_id == tenant.id)
            .order_by(CustomFormField.sort_order)
            .all()
        )

        self.validate_answers(fields, answers)

        now = datetime.now(timezone.utc)
        response = CustomFormResponseModel(
            tenant_id=tenant.id,
            form_id=form_id,
            customer_account_id=customer_account_id,
            tenant_customer_id=tc.id if tc else None,
            appointment_id=appointment_id,
            answers=answers,
            submitted_at=now,
        )
        db.add(response)
        db.flush()

        customer_event_service.emit(
            db=db,
            event_type="form_submitted",
            tenant_id=tenant.id,
            customer_account_id=customer_account_id,
            tenant_customer_id=tc.id if tc else None,
            entity_type="custom_form",
            entity_id=form_id,
            metadata={"form_type": form.form_type.value, "title": form.title},
        )

        db.commit()
        db.refresh(response)
        return response


custom_form_service = CustomFormService()
