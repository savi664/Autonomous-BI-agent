import uuid
import time

_sessions = {}


def create_session(df, dataset_profile, dataset_path) -> str:
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "df": df,
        "dataset_profile": dataset_profile,
        "dataset_path": dataset_path,
        "history": [],
        "session_last_accessed": time.time(),
    }
    return session_id


def get_session(session_id: str):
    session = _sessions.get(session_id)
    if session:
        session["session_last_accessed"] = time.time()
    return session


def append_to_session_history(session_id: str, question: str, answer: str):
    session = _sessions.get(session_id)
    if session:
        session["history"].append({"question": question, "result": answer})
        session["session_last_accessed"] = time.time()


def update_session(session_id: str, key: str, value):
    session = _sessions.get(session_id)
    if session:
        session[key] = value
        session["session_last_accessed"] = time.time()


def cleanup_stale_sessions(max_age_seconds=1800):
    current_time = time.time()
    stale_sessions = [
        session_id
        for session_id, session in _sessions.items()
        if current_time - session["session_last_accessed"] > max_age_seconds
    ]
    for session_id in stale_sessions:
        session = _sessions.pop(session_id, None)
        try:
            import os

            if (
                session
                and "dataset_path" in session
                and os.path.exists(session["dataset_path"])
            ):
                os.remove(session["dataset_path"])
        except Exception as e:
            print(f"Error cleaning up session {session_id}: {e}")
