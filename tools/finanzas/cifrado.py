"""Cifra el bloque de finanzas antes de publicarlo en data.json (que es público).

AES-256-GCM con llave derivada de FINANZAS_CLAVE por PBKDF2-SHA256. El
navegador la descifra con WebCrypto (dashboard/finanzas.js) cuando alguien
escribe la clave. Sin la clave, data.json solo muestra bytes al azar.
"""
import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERACIONES = 250_000


def cifrar(datos: dict, clave: str) -> dict:
    sal, iv = os.urandom(16), os.urandom(12)
    llave = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sal,
                       iterations=ITERACIONES).derive(clave.encode())
    ct = AESGCM(llave).encrypt(iv, json.dumps(datos, ensure_ascii=False).encode(), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"v": 1, "iter": ITERACIONES, "salt": b64(sal), "iv": b64(iv), "ct": b64(ct)}


def descifrar(caja: dict, clave: str) -> dict:
    d = lambda s: base64.b64decode(s)
    llave = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=d(caja["salt"]),
                       iterations=caja["iter"]).derive(clave.encode())
    return json.loads(AESGCM(llave).decrypt(d(caja["iv"]), d(caja["ct"]), None))
