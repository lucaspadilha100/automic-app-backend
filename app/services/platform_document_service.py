"""Service for AUTOMIC platform legal documents (ToS, privacy, etc.)."""
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models.platform_document import PlatformDocument, PlatformDocumentType
from app.core.exceptions import NotFoundError


class PlatformDocumentService:
    def get(
        self,
        db: Session,
        document_type: PlatformDocumentType,
    ) -> Optional[PlatformDocument]:
        return (
            db.query(PlatformDocument)
            .filter(PlatformDocument.document_type == document_type)
            .first()
        )

    def get_or_404(
        self,
        db: Session,
        document_type: PlatformDocumentType,
    ) -> PlatformDocument:
        doc = self.get(db, document_type)
        if not doc:
            raise NotFoundError(f"Documento '{document_type.value}' ainda não foi publicado.")
        return doc

    def upsert(
        self,
        db: Session,
        document_type: PlatformDocumentType,
        title: str,
        content: str,
        version: str,
    ) -> PlatformDocument:
        doc = self.get(db, document_type)
        if doc is None:
            doc = PlatformDocument(
                document_type=document_type,
                title=title,
                content=content,
                version=version,
                revision_count=1,
            )
            db.add(doc)
        else:
            doc.title = title
            doc.content = content
            doc.version = version
            doc.revision_count = (doc.revision_count or 0) + 1
            db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc


platform_document_service = PlatformDocumentService()
