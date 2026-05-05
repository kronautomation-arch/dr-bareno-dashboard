import os
from dotenv import load_dotenv
from pathlib import Path

def load_env():
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)

def get(key: str, default=None):
    load_env()
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Variable de entorno requerida no encontrada: {key}")
    return value

def get_optional(key: str, default=None):
    load_env()
    return os.getenv(key, default)
