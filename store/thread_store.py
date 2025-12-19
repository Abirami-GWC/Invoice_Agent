# store/thread_store.py
import json
import os
import uuid

STORE_FILE = os.environ.get("THREAD_STORE_FILE", "./data/thread_store.json")
os.makedirs(os.path.dirname(STORE_FILE), exist_ok=True)

def _load_store():
    if os.path.exists(STORE_FILE):
        try:
            with open(STORE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save_store(s):
    with open(STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, default=str)

def create_thread(payload: dict):
    store = _load_store()
    thread_id = str(uuid.uuid4())
    store[thread_id] = payload
    _save_store(store)
    return thread_id

def get_thread(thread_id: str):
    store = _load_store()
    return store.get(thread_id)

def update_thread(thread_id: str, payload: dict):
    store = _load_store()
    store[thread_id] = payload
    _save_store(store)
    return True
