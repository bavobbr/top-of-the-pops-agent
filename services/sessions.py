"""Session management for the Top of the Pops app."""

import time
import uuid
from flask import session
from flask_limiter.util import get_remote_address

# Session configuration
SESSION_EXPIRY_SECONDS = 3600  # 1 hour
MAX_SESSIONS_PER_IP = 5
MAX_TOTAL_SESSIONS = 1000
CLEANUP_INTERVAL = 100  # Run cleanup every N requests

# In-memory session storage
# Structure: {session_id: {'data': {...}, 'ip': '...', 'created_at': timestamp, 'last_access': timestamp}}
sessions = {}
request_counter = 0


def cleanup_sessions():
    """Remove expired sessions and enforce limits."""
    global sessions
    now = time.time()

    # Remove expired sessions
    expired = [sid for sid, s in sessions.items()
               if now - s['last_access'] > SESSION_EXPIRY_SECONDS]
    for sid in expired:
        del sessions[sid]

    # If still over limit, remove oldest sessions
    if len(sessions) > MAX_TOTAL_SESSIONS:
        sorted_sessions = sorted(sessions.items(), key=lambda x: x[1]['last_access'])
        to_remove = len(sessions) - MAX_TOTAL_SESSIONS
        for sid, _ in sorted_sessions[:to_remove]:
            del sessions[sid]


def get_session_data():
    """Get or create session data for current user."""
    global request_counter

    # Periodic cleanup
    request_counter += 1
    if request_counter >= CLEANUP_INTERVAL:
        request_counter = 0
        cleanup_sessions()

    client_ip = get_remote_address()
    now = time.time()

    if 'session_id' not in session:
        # Check if IP has too many sessions
        ip_sessions = [s for s in sessions.values() if s['ip'] == client_ip]
        if len(ip_sessions) >= MAX_SESSIONS_PER_IP:
            # Remove oldest session for this IP
            oldest = min(ip_sessions, key=lambda x: x['last_access'])
            oldest_id = next(sid for sid, s in sessions.items() if s is oldest)
            del sessions[oldest_id]

        session['session_id'] = str(uuid.uuid4())

    session_id = session['session_id']

    if session_id not in sessions:
        sessions[session_id] = {
            'data': {
                'category': None,
                'items': [],
                'properties': [],
                'details_cache': {}
            },
            'ip': client_ip,
            'created_at': now,
            'last_access': now
        }
    else:
        # Update last access time
        sessions[session_id]['last_access'] = now

    return sessions[session_id]['data']
