import requests
from tools.core import env_loader
from tools.core.logger import get_logger
from pathlib import Path
import re

logger = get_logger("meta.refresh_token")

def refresh_long_lived_token() -> str:
    """
    Renueva el token de Meta antes de que expire.
    Llama a este script cada vez que corre main.py.
    El nuevo token dura otros 60 días — en la práctica nunca expira.
    """
    env_loader.load_env()
    current_token = env_loader.get("META_ACCESS_TOKEN")
    app_id = env_loader.get("META_APP_ID")
    app_secret = env_loader.get("META_APP_SECRET")

    url = "https://graph.facebook.com/v25.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": current_token,
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        if "access_token" in data:
            new_token = data["access_token"]
            expires_in = data.get("expires_in", 0)
            days = round(expires_in / 86400)

            # Actualizar el .env con el nuevo token
            env_path = Path(__file__).parent.parent.parent / ".env"
            content = env_path.read_text(encoding="utf-8")
            content = re.sub(
                r"META_ACCESS_TOKEN=.*",
                f"META_ACCESS_TOKEN={new_token}",
                content
            )
            env_path.write_text(content, encoding="utf-8")
            logger.info(f"Token renovado exitosamente. Válido por {days} días más.")
            return new_token
        else:
            logger.warning(f"No se pudo renovar el token: {data}")
            return current_token

    except Exception as e:
        logger.warning(f"Error renovando token: {e}. Usando token actual.")
        return current_token
