"""Job polling endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rl_trade_api.api.deps import get_db_session
from rl_trade_api.schemas.errors import ErrorResponse
from rl_trade_api.schemas.jobs import JobStatusResponse
from rl_trade_api.services import jobs as jobs_service
from rl_trade_data import JobKind

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/{job_type}/{job_id}",
    response_model=JobStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
def read_job_status(
    job_type: JobKind,
    job_id: int,
    session: Session = Depends(get_db_session),
) -> JobStatusResponse:
    return jobs_service.get_job_status(session=session, job_type=job_type, job_id=job_id)
