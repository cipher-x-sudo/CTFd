"""
Container plugin rate limiting: configurable, per-account limits to protect
the plugin and SSH from excessive requests.
"""
import functools

from flask import jsonify, request

from CTFd.cache import cache
from CTFd.utils.user import get_current_user

# Config key suffixes for limit and interval per action
DEFAULT_LIMITS = {
    "request": (10, 60),
    "info": (30, 60),
    "renew": (10, 60),
    "stop": (10, 60),
}

KEY_PREFIX = "rl_containers"

# All actions that have rate limit keys (used for clear API)
RATE_LIMIT_ACTIONS = ("request", "info", "renew", "stop")


def _get_account_id():
    """Get account ID (user or team) for rate limit key. Must run after auth."""
    from CTFd.utils import get_config

    user = get_current_user()
    if not user:
        return None
    if get_config("user_mode") == "teams" and user.team_id:
        return f"team_{user.team_id}"
    return f"user_{user.id}"


def _get_limit_interval(action):
    """Get (limit, interval) for action from ContainerConfig or defaults."""
    from .models.config import ContainerConfig

    default_limit, default_interval = DEFAULT_LIMITS.get(action, (10, 60))
    limit = int(ContainerConfig.get(f"container_ratelimit_{action}_limit", default_limit))
    interval = int(ContainerConfig.get(f"container_ratelimit_{action}_interval", default_interval))
    return limit, interval


def container_ratelimit(action):
    """
    Decorator: rate limit container API by action (request, info, renew, stop).
    Uses per-account keys and configurable limit/interval from ContainerConfig.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            account_id = _get_account_id()
            if account_id is None:
                return f(*args, **kwargs)

            limit, interval = _get_limit_interval(action)
            # Method to count: GET for info, POST for others
            method = "GET" if action == "info" else "POST"
            if request.method != method:
                return f(*args, **kwargs)

            key = "{}:{}:{}".format(KEY_PREFIX, action, account_id)
            current = cache.get(key)

            if current is not None and int(current) > limit - 1:
                # Log rate limit event for admin Rate Limit Logs
                try:
                    from CTFd.models import db
                    from CTFd.utils.user import get_ip
                    from .models.rate_limit_log import ContainerRateLimitLog
                    from datetime import datetime
                    log = ContainerRateLimitLog(
                        account_key=account_id,
                        action=action,
                        ip_address=get_ip(),
                        timestamp=datetime.utcnow(),
                    )
                    db.session.add(log)
                    db.session.commit()
                except Exception:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                resp = jsonify(
                    {
                        "code": 429,
                        "message": "Too many requests. Limit is %s requests in %s seconds"
                        % (limit, interval),
                    }
                )
                resp.status_code = 429
                return resp

            if current is None:
                cache.set(key, 1, timeout=interval)
            else:
                cache.set(key, int(current) + 1, timeout=interval)

            return f(*args, **kwargs)

        return wrapped

    return decorator
