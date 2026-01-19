"""
Change Request and Audit Log Repository
"""
import sqlite3
import uuid
import json
from typing import Optional, Dict, List
from datetime import datetime


class ChangeRequestRepository:
    """Repository for change requests and audit logs"""

    def __init__(self, db_path: str = "backtest.db"):
        self.db_path = db_path

    def _get_conn(self):
        """Get database connection with WAL mode"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")  # Enable foreign key constraints
        return conn

    def create_change_request(
        self,
        session_id: str,
        strategy_name: str,
        target_env: str,
        change_payload: Dict,
        created_by: str,
        change_description: Optional[str] = None
    ) -> str:
        """
        Create a new change request

        Args:
            session_id: Backtest session ID
            strategy_name: Strategy name
            target_env: Target environment (staging/prod)
            change_payload: Dict with 'old_config' and 'new_config'
            created_by: User who created the request
            change_description: Optional description

        Returns:
            Request ID
        """
        conn = self._get_conn()
        try:
            request_id = str(uuid.uuid4())
            now_ts = int(datetime.utcnow().timestamp())

            conn.execute("""
                INSERT INTO backtest_change_requests (
                    id, created_at, created_by, status, session_id,
                    strategy_name, target_env, change_payload, change_description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id, now_ts, created_by, "pending", session_id,
                strategy_name, target_env, json.dumps(change_payload),
                change_description
            ))
            conn.commit()

            # Log the creation
            self.log_audit(
                actor=created_by,
                action="create_change_request",
                target_type="change_request",
                target_id=request_id,
                payload={"session_id": session_id, "target_env": target_env}
            )

            return request_id
        finally:
            conn.close()

    def get_change_request(self, request_id: str) -> Optional[Dict]:
        """Get a change request by ID"""
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT * FROM backtest_change_requests WHERE id = ?
            """, (request_id,))
            row = cursor.fetchone()

            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            request = dict(zip(columns, row))
            request["change_payload"] = json.loads(request["change_payload"])
            return request
        finally:
            conn.close()

    def list_change_requests(
        self,
        status: Optional[str] = None,
        target_env: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """List change requests with filters"""
        conn = self._get_conn()
        try:
            sql = "SELECT * FROM backtest_change_requests WHERE 1=1"
            params = []

            if status:
                sql += " AND status = ?"
                params.append(status)

            if target_env:
                sql += " AND target_env = ?"
                params.append(target_env)

            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            columns = [desc[0] for desc in cursor.description]
            requests = []
            for row in rows:
                request = dict(zip(columns, row))
                request["change_payload"] = json.loads(request["change_payload"])
                requests.append(request)

            return requests
        finally:
            conn.close()

    def approve_change_request(self, request_id: str, approved_by: str) -> None:
        """Approve a change request"""
        conn = self._get_conn()
        try:
            now_ts = int(datetime.utcnow().timestamp())

            conn.execute("""
                UPDATE backtest_change_requests
                SET status = 'approved', approved_by = ?, approved_at = ?
                WHERE id = ? AND status = 'pending'
            """, (approved_by, now_ts, request_id))

            if conn.total_changes == 0:
                raise ValueError("Request not found or not in pending status")

            conn.commit()

            # Log the approval
            self.log_audit(
                actor=approved_by,
                action="approve_change_request",
                target_type="change_request",
                target_id=request_id
            )
        finally:
            conn.close()

    def reject_change_request(self, request_id: str, rejected_by: str, reason: Optional[str] = None) -> None:
        """Reject a change request"""
        conn = self._get_conn()
        try:
            conn.execute("""
                UPDATE backtest_change_requests
                SET status = 'rejected', error_message = ?
                WHERE id = ? AND status = 'pending'
            """, (reason, request_id))

            if conn.total_changes == 0:
                raise ValueError("Request not found or not in pending status")

            conn.commit()

            # Log the rejection
            self.log_audit(
                actor=rejected_by,
                action="reject_change_request",
                target_type="change_request",
                target_id=request_id,
                payload={"reason": reason}
            )
        finally:
            conn.close()

    def mark_applied(self, request_id: str, applied_by: str) -> None:
        """Mark a change request as applied"""
        conn = self._get_conn()
        try:
            now_ts = int(datetime.utcnow().timestamp())

            conn.execute("""
                UPDATE backtest_change_requests
                SET status = 'applied', applied_by = ?, applied_at = ?
                WHERE id = ? AND status = 'approved'
            """, (applied_by, now_ts, request_id))

            if conn.total_changes == 0:
                raise ValueError("Request not found or not in approved status")

            conn.commit()

            # Log the application
            self.log_audit(
                actor=applied_by,
                action="apply_change_request",
                target_type="change_request",
                target_id=request_id
            )
        finally:
            conn.close()

    def mark_failed(self, request_id: str, error_message: str) -> None:
        """Mark a change request as failed"""
        conn = self._get_conn()
        try:
            conn.execute("""
                UPDATE backtest_change_requests
                SET status = 'failed', error_message = ?
                WHERE id = ?
            """, (error_message, request_id))
            conn.commit()
        finally:
            conn.close()

    def log_audit(
        self,
        actor: str,
        action: str,
        target_type: str,
        target_id: str,
        payload: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Log an audit event"""
        conn = self._get_conn()
        try:
            log_id = str(uuid.uuid4())
            now_ts = int(datetime.utcnow().timestamp())

            conn.execute("""
                INSERT INTO backtest_audit_logs (
                    id, created_at, actor, action, target_type, target_id,
                    payload, ip_address, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_id, now_ts, actor, action, target_type, target_id,
                json.dumps(payload) if payload else None,
                ip_address, user_agent
            ))
            conn.commit()
            return log_id
        finally:
            conn.close()

    def get_audit_logs(
        self,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        actor: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get audit logs with filters"""
        conn = self._get_conn()
        try:
            sql = "SELECT * FROM backtest_audit_logs WHERE 1=1"
            params = []

            if target_type:
                sql += " AND target_type = ?"
                params.append(target_type)

            if target_id:
                sql += " AND target_id = ?"
                params.append(target_id)

            if actor:
                sql += " AND actor = ?"
                params.append(actor)

            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            columns = [desc[0] for desc in cursor.description]
            logs = []
            for row in rows:
                log = dict(zip(columns, row))
                if log["payload"]:
                    log["payload"] = json.loads(log["payload"])
                logs.append(log)

            return logs
        finally:
            conn.close()
