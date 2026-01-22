"""
AI Report Repository - Persistence layer for AI analysis results
"""
import sqlite3
import uuid
import hashlib
import json
from typing import Optional, Dict, List
from datetime import datetime

from backtest.adapters.storage.supabase_client import get_supabase_client


class AIReportRepository:
    """Repository for AI analysis reports"""

    def __init__(self, db_path: str = "backtest.db"):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure AI report tables exist (SQLite)."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS backtest_ai_reports (
                  id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  model_name TEXT NOT NULL,
                  prompt_version TEXT NOT NULL,
                  input_digest TEXT NOT NULL,
                  summary TEXT NOT NULL,
                  strengths TEXT,
                  weaknesses TEXT,
                  recommendations TEXT,
                  param_suggestions TEXT,
                  compare_group_id TEXT,
                  FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_ai_session ON backtest_ai_reports(session_id);
                CREATE INDEX IF NOT EXISTS idx_ai_group ON backtest_ai_reports(compare_group_id);
                CREATE INDEX IF NOT EXISTS idx_ai_created_at ON backtest_ai_reports(created_at);
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_conn(self):
        """Get database connection with WAL mode"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")  # Enable foreign key constraints
        return conn

    def create_report(
        self,
        session_id: str,
        model_name: str,
        prompt_version: str,
        input_data: Dict,
        analysis_result: Dict,
        compare_group_id: Optional[str] = None
    ) -> str:
        """
        Create a new AI analysis report

        Args:
            session_id: Backtest session ID
            model_name: AI model name (e.g., "claude-sonnet-4.5")
            prompt_version: Prompt version identifier
            input_data: Input data used for analysis (for digest)
            analysis_result: AI analysis result with keys:
                - summary: Overall summary
                - strengths: List of strengths
                - weaknesses: List of weaknesses
                - recommendations: List of recommendations
                - param_suggestions: Suggested parameter changes (JSON)
            compare_group_id: Optional group ID for batch comparison

        Returns:
            Report ID
        """
        conn = self._get_conn()
        try:
            report_id = str(uuid.uuid4())
            now_ts = int(datetime.utcnow().timestamp())

            # Create input digest for caching/deduplication
            input_digest = hashlib.sha256(
                json.dumps(input_data, sort_keys=True).encode()
            ).hexdigest()[:16]

            # Convert lists to JSON strings
            strengths = json.dumps(analysis_result.get("strengths", []))
            weaknesses = json.dumps(analysis_result.get("weaknesses", []))
            recommendations = json.dumps(analysis_result.get("recommendations", []))
            param_suggestions = json.dumps(analysis_result.get("param_suggestions", {}))

            conn.execute("""
                INSERT INTO backtest_ai_reports (
                    id, session_id, created_at, model_name, prompt_version,
                    input_digest, summary, strengths, weaknesses,
                    recommendations, param_suggestions, compare_group_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id, session_id, now_ts, model_name, prompt_version,
                input_digest, analysis_result.get("summary", ""),
                strengths, weaknesses, recommendations,
                param_suggestions, compare_group_id
            ))
            conn.commit()
            return report_id
        finally:
            conn.close()


class SupabaseAIReportRepository:
    """Repository for AI analysis reports (Supabase 实现)"""

    def __init__(self):
        self.client = get_supabase_client()

    def _parse_report(self, report: Dict) -> Dict:
        report["strengths"] = json.loads(report["strengths"]) if report.get("strengths") else []
        report["weaknesses"] = json.loads(report["weaknesses"]) if report.get("weaknesses") else []
        report["recommendations"] = json.loads(report["recommendations"]) if report.get("recommendations") else []
        report["param_suggestions"] = json.loads(report["param_suggestions"]) if report.get("param_suggestions") else {}
        return report

    def create_report(
        self,
        session_id: str,
        model_name: str,
        prompt_version: str,
        input_data: Dict,
        analysis_result: Dict,
        compare_group_id: Optional[str] = None
    ) -> str:
        report_id = str(uuid.uuid4())
        now_ts = int(datetime.utcnow().timestamp())
        input_digest = hashlib.sha256(
            json.dumps(input_data, sort_keys=True).encode()
        ).hexdigest()[:16]

        payload = {
            "id": report_id,
            "session_id": session_id,
            "created_at": now_ts,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "input_digest": input_digest,
            "summary": analysis_result.get("summary", ""),
            "strengths": json.dumps(analysis_result.get("strengths", [])),
            "weaknesses": json.dumps(analysis_result.get("weaknesses", [])),
            "recommendations": json.dumps(analysis_result.get("recommendations", [])),
            "param_suggestions": json.dumps(analysis_result.get("param_suggestions", {})),
            "compare_group_id": compare_group_id,
        }

        self.client.table("backtest_ai_reports").insert(payload).execute()
        return report_id

    def get_latest_report(self, session_id: str) -> Optional[Dict]:
        response = self.client.table("backtest_ai_reports") \
            .select("*") \
            .eq("session_id", session_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

        if not response.data:
            return None
        return self._parse_report(response.data[0])

    def get_report(self, report_id: str) -> Optional[Dict]:
        response = self.client.table("backtest_ai_reports") \
            .select("*") \
            .eq("id", report_id) \
            .limit(1) \
            .execute()

        if not response.data:
            return None
        return self._parse_report(response.data[0])

    def get_reports_by_group(self, compare_group_id: str) -> List[Dict]:
        response = self.client.table("backtest_ai_reports") \
            .select("*") \
            .eq("compare_group_id", compare_group_id) \
            .order("created_at", desc=True) \
            .execute()

        return [self._parse_report(row) for row in (response.data or [])]

    def get_latest_report(self, session_id: str) -> Optional[Dict]:
        """Get the latest AI report for a session"""
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT * FROM backtest_ai_reports
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (session_id,))
            row = cursor.fetchone()

            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            report = dict(zip(columns, row))

            # Parse JSON fields
            report["strengths"] = json.loads(report["strengths"]) if report["strengths"] else []
            report["weaknesses"] = json.loads(report["weaknesses"]) if report["weaknesses"] else []
            report["recommendations"] = json.loads(report["recommendations"]) if report["recommendations"] else []
            report["param_suggestions"] = json.loads(report["param_suggestions"]) if report["param_suggestions"] else {}

            return report
        finally:
            conn.close()

    def get_report(self, report_id: str) -> Optional[Dict]:
        """Get a specific AI report by ID"""
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT * FROM backtest_ai_reports WHERE id = ?
            """, (report_id,))
            row = cursor.fetchone()

            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            report = dict(zip(columns, row))

            # Parse JSON fields
            report["strengths"] = json.loads(report["strengths"]) if report["strengths"] else []
            report["weaknesses"] = json.loads(report["weaknesses"]) if report["weaknesses"] else []
            report["recommendations"] = json.loads(report["recommendations"]) if report["recommendations"] else []
            report["param_suggestions"] = json.loads(report["param_suggestions"]) if report["param_suggestions"] else {}

            return report
        finally:
            conn.close()

    def get_reports_by_group(self, compare_group_id: str) -> List[Dict]:
        """Get all reports in a comparison group"""
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT * FROM backtest_ai_reports
                WHERE compare_group_id = ?
                ORDER BY created_at DESC
            """, (compare_group_id,))
            rows = cursor.fetchall()

            columns = [desc[0] for desc in cursor.description]
            reports = []
            for row in rows:
                report = dict(zip(columns, row))
                # Parse JSON fields
                report["strengths"] = json.loads(report["strengths"]) if report["strengths"] else []
                report["weaknesses"] = json.loads(report["weaknesses"]) if report["weaknesses"] else []
                report["recommendations"] = json.loads(report["recommendations"]) if report["recommendations"] else []
                report["param_suggestions"] = json.loads(report["param_suggestions"]) if report["param_suggestions"] else {}
                reports.append(report)

            return reports
        finally:
            conn.close()
