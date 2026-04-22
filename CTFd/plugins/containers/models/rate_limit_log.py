"""
Container Rate Limit Log Model

Records each time an account hits the container API rate limit (429).
Used for admin Rate Limit Logs view and to support "Clear rate limit" per account.
"""
from datetime import datetime

from CTFd.models import db


class ContainerRateLimitLog(db.Model):
    """
    Log entry when a user/team is rate limited (429) on a container API action.
    account_key matches the cache key suffix (e.g. user_123, team_456).
    """
    __tablename__ = 'container_rate_limit_logs'

    id = db.Column(db.Integer, primary_key=True)
    account_key = db.Column(db.String(64), nullable=False, index=True)
    action = db.Column(db.String(32), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
