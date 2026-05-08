from fastapi import HTTPException, status
from typing import Optional, Any, Dict


class AppError(Exception):
    """Base application error with standard structure."""
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


# ---- Error Codes ----

class UnauthorizedError(AppError):
    def __init__(self, message: str = "Não autenticado."):
        super().__init__("UNAUTHORIZED", message, status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Acesso negado."):
        super().__init__("FORBIDDEN", message, status.HTTP_403_FORBIDDEN)


class NotFoundError(AppError):
    def __init__(self, code: str = "NOT_FOUND", message: str = "Recurso não encontrado."):
        super().__init__(code, message, status.HTTP_404_NOT_FOUND)


class ConflictError(AppError):
    def __init__(self, code: str = "CONFLICT", message: str = "Conflito de dados."):
        super().__init__(code, message, status.HTTP_409_CONFLICT)


class ValidationError(AppError):
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__("VALIDATION_ERROR", message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class TenantNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("TENANT_NOT_FOUND", "Empresa não encontrada.")


class TenantInactiveError(AppError):
    def __init__(self):
        super().__init__("TENANT_INACTIVE", "Esta empresa não está disponível.", status.HTTP_403_FORBIDDEN)


class TenantSuspendedError(AppError):
    def __init__(self):
        super().__init__("TENANT_SUSPENDED", "Esta conta está suspensa. Entre em contato com o suporte.", status.HTTP_403_FORBIDDEN)


class TenantCancelledError(AppError):
    def __init__(self):
        super().__init__("TENANT_CANCELLED", "Esta conta foi cancelada.", status.HTTP_403_FORBIDDEN)


class FeatureDisabledError(AppError):
    def __init__(self, feature: str = ""):
        msg = f"Funcionalidade não disponível no seu plano." if not feature else f"Funcionalidade '{feature}' não disponível no seu plano."
        super().__init__("FEATURE_DISABLED", msg, status.HTTP_403_FORBIDDEN)


class PlanLimitError(AppError):
    def __init__(self, code: str, message: str):
        super().__init__(code, message, status.HTTP_422_UNPROCESSABLE_ENTITY)


class ServiceLimitReachedError(PlanLimitError):
    def __init__(self):
        super().__init__("SERVICE_LIMIT_REACHED", "Você atingiu o limite de serviços do seu plano. Entre em contato para ampliar seu limite.")


class ProfessionalLimitReachedError(PlanLimitError):
    def __init__(self):
        super().__init__("PROFESSIONAL_LIMIT_REACHED", "Você atingiu o limite de profissionais do seu plano. Entre em contato para ampliar seu limite.")


class UserLimitReachedError(PlanLimitError):
    def __init__(self):
        super().__init__("USER_LIMIT_REACHED", "Você atingiu o limite de usuários do seu plano. Entre em contato para ampliar seu limite.")


class PackageLimitReachedError(PlanLimitError):
    def __init__(self):
        super().__init__("PACKAGE_LIMIT_REACHED", "Você atingiu o limite de pacotes do seu plano. Entre em contato para ampliar seu limite.")


class UnitLimitReachedError(PlanLimitError):
    def __init__(self):
        super().__init__("UNIT_LIMIT_REACHED", "Você atingiu o limite de unidades do seu plano. Entre em contato para ampliar seu limite.")


class AppointmentConflictError(AppError):
    def __init__(self):
        super().__init__("APPOINTMENT_CONFLICT", "Este horário não está mais disponível. Por favor, escolha outro horário.", status.HTTP_409_CONFLICT)


class InvalidAvailabilityError(AppError):
    def __init__(self, message: str = "Horário inválido ou indisponível."):
        super().__init__("INVALID_AVAILABILITY", message, status.HTTP_422_UNPROCESSABLE_ENTITY)


class CustomerNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("CUSTOMER_NOT_FOUND", "Cliente não encontrado.")


class ServiceNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("SERVICE_NOT_FOUND", "Serviço não encontrado.")


class ProfessionalNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("PROFESSIONAL_NOT_FOUND", "Profissional não encontrado.")


class InvalidTimezoneError(AppError):
    def __init__(self):
        super().__init__("INVALID_TIMEZONE", "Timezone inválido.", status.HTTP_422_UNPROCESSABLE_ENTITY)


class InvalidBookingPolicyError(AppError):
    def __init__(self, message: str):
        super().__init__("INVALID_BOOKING_POLICY", message, status.HTTP_422_UNPROCESSABLE_ENTITY)


class PaymentRequiredError(AppError):
    def __init__(self):
        super().__init__("PAYMENT_REQUIRED", "Pagamento ou sinal é obrigatório para confirmar este agendamento.", status.HTTP_402_PAYMENT_REQUIRED)


class InvalidCredentialsError(AppError):
    def __init__(self):
        super().__init__("INVALID_CREDENTIALS", "E-mail ou senha inválidos.", status.HTTP_401_UNAUTHORIZED)


class TokenExpiredError(AppError):
    def __init__(self):
        super().__init__("TOKEN_EXPIRED", "Token expirado. Faça login novamente.", status.HTTP_401_UNAUTHORIZED)


class PackageNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("PACKAGE_NOT_FOUND", "Pacote não encontrado.")


class CustomerPackageNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("CUSTOMER_PACKAGE_NOT_FOUND", "Pacote do cliente não encontrado.")


class PackageExpiredError(AppError):
    def __init__(self):
        super().__init__("PACKAGE_EXPIRED", "Este pacote está vencido.", status.HTTP_422_UNPROCESSABLE_ENTITY)


class PackageCancelledError(AppError):
    def __init__(self):
        super().__init__("PACKAGE_CANCELLED", "Este pacote foi cancelado.", status.HTTP_422_UNPROCESSABLE_ENTITY)


class PackageNoRemainingSessionsError(AppError):
    def __init__(self):
        super().__init__("PACKAGE_NO_REMAINING_SESSIONS", "Este pacote não possui sessões disponíveis.", status.HTTP_422_UNPROCESSABLE_ENTITY)


class PackageServiceNotAllowedError(AppError):
    def __init__(self):
        super().__init__("PACKAGE_SERVICE_NOT_ALLOWED", "Este serviço não está incluído no pacote.", status.HTTP_422_UNPROCESSABLE_ENTITY)


class PackagePaymentPendingError(AppError):
    def __init__(self):
        super().__init__("PACKAGE_PAYMENT_PENDING", "O pagamento deste pacote está pendente.", status.HTTP_422_UNPROCESSABLE_ENTITY)


class UnitNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("UNIT_NOT_FOUND", "Unidade não encontrada.")


class InternalError(AppError):
    def __init__(self, message: str = "Erro interno do servidor."):
        super().__init__("INTERNAL_ERROR", message, status.HTTP_500_INTERNAL_SERVER_ERROR)
