"""Zařazování úloh do DB fronty konektoru (`konektor_job_queue`)."""

from sqlalchemy.orm import Session

from app.konektor.models import KonektorJobQueue


def zarad(db: Session, typ: str, payload: dict) -> KonektorJobQueue:
    """Vloží úlohu ke zpracování workerem. Vrací zařazený job."""
    job = KonektorJobQueue(typ=typ, payload=payload, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
