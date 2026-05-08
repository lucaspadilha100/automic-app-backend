from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    error: bool = True
    code: str
    message: str
    details: Dict[str, Any] = {}


class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "Operação realizada com sucesso."


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int) -> "PaginatedResponse[T]":
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


def error_response(code: str, message: str, details: Optional[Dict] = None) -> Dict:
    return {"error": True, "code": code, "message": message, "details": details or {}}
