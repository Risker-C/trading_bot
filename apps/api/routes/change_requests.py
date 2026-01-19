"""
Change Request API routes
"""
from fastapi import APIRouter, HTTPException, Request
from typing import List, Optional
from pydantic import BaseModel
from backtest.change_request_repository import ChangeRequestRepository
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtests", tags=["change-requests"])


class CreateChangeRequestRequest(BaseModel):
    """Request to create a change request"""
    session_id: str
    strategy_name: str
    target_env: str  # staging or prod
    old_config: dict
    new_config: dict
    description: Optional[str] = None


class ChangeRequestResponse(BaseModel):
    """Change request response"""
    id: str
    created_at: int
    created_by: str
    status: str
    session_id: str
    strategy_name: str
    target_env: str
    change_payload: dict
    change_description: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[int] = None
    applied_by: Optional[str] = None
    applied_at: Optional[int] = None
    error_message: Optional[str] = None


class ApproveRejectRequest(BaseModel):
    """Request to approve or reject a change"""
    reason: Optional[str] = None


class AuditLogResponse(BaseModel):
    """Audit log response"""
    id: str
    created_at: int
    actor: str
    action: str
    target_type: str
    target_id: str
    payload: Optional[dict] = None


@router.post("/change-requests", response_model=ChangeRequestResponse)
async def create_change_request(request: CreateChangeRequestRequest, http_request: Request):
    """
    Create a new change request

    This initiates the approval workflow for applying backtest-optimized
    parameters to the production environment.

    Requires:
    - Session ID from a completed backtest
    - Old and new configuration for comparison
    - Target environment (staging/prod)
    """
    try:
        # In a real app, get user from authentication
        created_by = "system"  # TODO: Get from auth token

        repo = ChangeRequestRepository()
        request_id = repo.create_change_request(
            session_id=request.session_id,
            strategy_name=request.strategy_name,
            target_env=request.target_env,
            change_payload={
                "old_config": request.old_config,
                "new_config": request.new_config
            },
            created_by=created_by,
            change_description=request.description
        )

        change_request = repo.get_change_request(request_id)
        return ChangeRequestResponse(**change_request)

    except Exception as e:
        logger.exception("Failed to create change request")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/change-requests", response_model=List[ChangeRequestResponse])
async def list_change_requests(
    status: Optional[str] = None,
    target_env: Optional[str] = None,
    limit: int = 50
):
    """
    List change requests

    Filter by:
    - status: pending, approved, rejected, applied, failed
    - target_env: staging, prod
    """
    try:
        repo = ChangeRequestRepository()
        requests = repo.list_change_requests(
            status=status,
            target_env=target_env,
            limit=limit
        )

        return [ChangeRequestResponse(**r) for r in requests]

    except Exception as e:
        logger.exception("Failed to list change requests")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/change-requests/{request_id}", response_model=ChangeRequestResponse)
async def get_change_request(request_id: str):
    """Get a specific change request"""
    try:
        repo = ChangeRequestRepository()
        change_request = repo.get_change_request(request_id)

        if not change_request:
            raise HTTPException(status_code=404, detail="Change request not found")

        return ChangeRequestResponse(**change_request)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get change request {request_id}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/change-requests/{request_id}/approve")
async def approve_change_request(request_id: str, request: ApproveRejectRequest):
    """
    Approve a change request

    Requires admin/approver role.
    After approval, the change can be applied to the target environment.
    """
    try:
        # In a real app, check user role
        approved_by = "admin"  # TODO: Get from auth token and verify role

        repo = ChangeRequestRepository()
        repo.approve_change_request(request_id, approved_by)

        return {"status": "approved", "request_id": request_id}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to approve change request {request_id}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/change-requests/{request_id}/reject")
async def reject_change_request(request_id: str, request: ApproveRejectRequest):
    """
    Reject a change request

    Requires admin/approver role.
    """
    try:
        # In a real app, check user role
        rejected_by = "admin"  # TODO: Get from auth token and verify role

        repo = ChangeRequestRepository()
        repo.reject_change_request(request_id, rejected_by, request.reason)

        return {"status": "rejected", "request_id": request_id}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to reject change request {request_id}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/change-requests/{request_id}/apply")
async def apply_change_request(request_id: str):
    """
    Apply an approved change request

    WARNING: This modifies production configuration!

    Requires:
    - Request must be in 'approved' status
    - Admin role
    - Proper backup and rollback procedures

    This is a MOCK implementation. In production:
    1. Validate request is approved
    2. Create configuration backup
    3. Apply changes to config file
    4. Restart trading system (if needed)
    5. Verify changes took effect
    6. Log all actions
    """
    try:
        # In a real app, check user role
        applied_by = "admin"  # TODO: Get from auth token and verify role

        repo = ChangeRequestRepository()
        change_request = repo.get_change_request(request_id)

        if not change_request:
            raise HTTPException(status_code=404, detail="Change request not found")

        if change_request["status"] != "approved":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot apply request in status: {change_request['status']}"
            )

        # MOCK: In production, this would:
        # 1. Read current config
        # 2. Apply changes from change_payload['new_config']
        # 3. Write to config file
        # 4. Restart trading system
        # 5. Verify system is healthy

        # For now, just mark as applied
        repo.mark_applied(request_id, applied_by)

        return {
            "status": "applied",
            "request_id": request_id,
            "message": "Change request applied successfully (MOCK)"
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to apply change request {request_id}")
        repo = ChangeRequestRepository()
        repo.mark_failed(request_id, str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    actor: Optional[str] = None,
    limit: int = 100
):
    """
    Get audit logs

    Filter by:
    - target_type: change_request, session, etc.
    - target_id: Specific resource ID
    - actor: User who performed the action
    """
    try:
        repo = ChangeRequestRepository()
        logs = repo.get_audit_logs(
            target_type=target_type,
            target_id=target_id,
            actor=actor,
            limit=limit
        )

        return [AuditLogResponse(**log) for log in logs]

    except Exception as e:
        logger.exception("Failed to get audit logs")
        raise HTTPException(status_code=500, detail="Internal server error")
