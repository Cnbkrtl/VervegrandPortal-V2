# operations/log_manager.py - YENİ DOSYA

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from pathlib import Path

@dataclass
class LogEntry:
    """Log entry data structure"""
    id: Optional[int] = None
    timestamp: str = None
    log_type: str = None  # 'sync', 'price_update', 'error', 'system'
    status: str = None    # 'started', 'completed', 'failed', 'running'
    source: str = None    # 'web_ui', 'github_actions', 'scheduled'
    sync_mode: str = None
    user_id: str = None
    total_products: int = 0
    processed: int = 0
    created: int = 0
    updated: int = 0
    failed: int = 0
    skipped: int = 0
    duration: str = None
    error_message: str = None
    details: str = None  # JSON string
    worker_count: int = 0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

class LogManager:
    """Centralized logging system"""
    
    def __init__(self, db_path: str = "logs/sync_logs.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._ensure_db_exists()
        
    def _ensure_db_exists(self):
        """Create database and tables if they don't exist"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    log_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    sync_mode TEXT,
                    user_id TEXT,
                    total_products INTEGER DEFAULT 0,
                    processed INTEGER DEFAULT 0,
                    created INTEGER DEFAULT 0,
                    updated INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    skipped INTEGER DEFAULT 0,
                    duration TEXT,
                    error_message TEXT,
                    details TEXT,
                    worker_count INTEGER DEFAULT 0
                )
            """)
            
            # Index'ler ekle
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON sync_logs(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_log_type ON sync_logs(log_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON sync_logs(status)")
    
    def log_sync_start(self, sync_mode: str, source: str, user_id: str = None, worker_count: int = 0) -> int:
        """Start a new sync operation log"""
        entry = LogEntry(
            log_type="sync",
            status="started",
            source=source,
            sync_mode=sync_mode,
            user_id=user_id,
            worker_count=worker_count
        )
        return self._insert_log(entry)
    
    def log_sync_progress(self, log_id: int, stats: Dict[str, Any]):
        """Update sync progress"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE sync_logs 
                    SET processed = ?, created = ?, updated = ?, failed = ?, skipped = ?,
                        total_products = ?, status = 'running'
                    WHERE id = ?
                """, (
                    stats.get('processed', 0),
                    stats.get('created', 0),
                    stats.get('updated', 0),
                    stats.get('failed', 0),
                    stats.get('skipped', 0),
                    stats.get('total', 0),
                    log_id
                ))
    
    def log_sync_complete(self, log_id: int, stats: Dict[str, Any], duration: str, success: bool = True):
        """Complete a sync operation log"""
        status = "completed" if success else "failed"
        
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE sync_logs 
                    SET status = ?, duration = ?, processed = ?, created = ?, updated = ?, 
                        failed = ?, skipped = ?, total_products = ?, details = ?
                    WHERE id = ?
                """, (
                    status, duration,
                    stats.get('processed', 0),
                    stats.get('created', 0),
                    stats.get('updated', 0),
                    stats.get('failed', 0),
                    stats.get('skipped', 0),
                    stats.get('total', 0),
                    json.dumps(stats),
                    log_id
                ))
    
    def log_error(self, error_message: str, source: str, details: Dict[str, Any] = None):
        """Log an error"""
        entry = LogEntry(
            log_type="error",
            status="failed",
            source=source,
            error_message=error_message,
            details=json.dumps(details) if details else None
        )
        return self._insert_log(entry)
    
    def log_price_update(self, source: str, user_id: str, updated_count: int, failed_count: int, duration: str):
        """Log price update operation"""
        entry = LogEntry(
            log_type="price_update",
            status="completed" if failed_count == 0 else "partial",
            source=source,
            user_id=user_id,
            updated=updated_count,
            failed=failed_count,
            duration=duration
        )
        return self._insert_log(entry)
    
    def _insert_log(self, entry: LogEntry) -> int:
        """Insert log entry and return ID"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO sync_logs 
                    (timestamp, log_type, status, source, sync_mode, user_id, 
                     total_products, processed, created, updated, failed, skipped, 
                     duration, error_message, details, worker_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.timestamp, entry.log_type, entry.status, entry.source,
                    entry.sync_mode, entry.user_id, entry.total_products,
                    entry.processed, entry.created, entry.updated, entry.failed,
                    entry.skipped, entry.duration, entry.error_message,
                    entry.details, entry.worker_count
                ))
                return cursor.lastrowid
    
    def get_recent_logs(self, limit: int = 50, log_type: str = None) -> List[Dict]:
        """Get recent log entries"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = "SELECT * FROM sync_logs"
            params = []
            
            if log_type:
                query += " WHERE log_type = ?"
                params.append(log_type)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stats_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get statistics summary for the last N days"""
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Total operations
            total_ops = conn.execute("""
                SELECT COUNT(*) FROM sync_logs 
                WHERE timestamp >= ? AND log_type = 'sync'
            """, (since_date,)).fetchone()[0]
            
            # Successful operations
            successful_ops = conn.execute("""
                SELECT COUNT(*) FROM sync_logs 
                WHERE timestamp >= ? AND log_type = 'sync' AND status = 'completed'
            """, (since_date,)).fetchone()[0]
            
            # Total products processed
            products_stats = conn.execute("""
                SELECT SUM(processed) as total_processed, SUM(created) as total_created,
                       SUM(updated) as total_updated, SUM(failed) as total_failed
                FROM sync_logs 
                WHERE timestamp >= ? AND log_type = 'sync' AND status = 'completed'
            """, (since_date,)).fetchone()
            
            # Error count
            error_count = conn.execute("""
                SELECT COUNT(*) FROM sync_logs 
                WHERE timestamp >= ? AND log_type = 'error'
            """, (since_date,)).fetchone()[0]
            
            return {
                'total_operations': total_ops,
                'successful_operations': successful_ops,
                'success_rate': (successful_ops / total_ops * 100) if total_ops > 0 else 0,
                'total_processed': products_stats[0] or 0,
                'total_created': products_stats[1] or 0,
                'total_updated': products_stats[2] or 0,
                'total_failed': products_stats[3] or 0,
                'error_count': error_count,
                'days': days
            }
    
    def cleanup_old_logs(self, days: int = 30):
        """Clean up logs older than specified days"""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM sync_logs WHERE timestamp < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            logging.info(f"Cleaned up {deleted_count} old log entries")
            return deleted_count

# Global log manager instance
log_manager = LogManager()