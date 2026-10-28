# SOP: Setup gws CLI (Google Workspace) — Piloto Dr. Bareño

> WAT Framework — Workflow. Estado: PILOTO (no producción).
> Objetivo: reemplazar el lector de Sheets (gspread) por `gws sheets` en Dr. Bareño.
> Herramienta: `@googleworkspace/cli` — NO es producto oficial soportado de Google.

## Decisiones tomadas (no cambiar sin razón)

| Decisión | Valor | Por qué |
|---|---|---|
| Versión pineada | `0.22.5` | Es 0.x, breaking changes anunciados camino a v1.0. Nunca instalar `latest` a ciegas. |
| Modo integración | bash/skills (NO `gws mcp`) | Ya hay 6 MCPs + context-mode inestable. El modo bash no ocupa contexto. |
| Cuenta OAuth | `logosimportadores@gmail.com` (cuenta "logos") | Confirmado 2026-05-15: TODOS los Sheets de Dr. Bareño viven en logos. NO usar la cuenta "kron". |
| credentials.json del proyecto | NO se toca | Es el service account de gspread. gws guarda su auth en el keyring del OS, es independiente. |

## Prerrequisito descubierto: gcloud CLI

`gws auth setup` FALLA con `gcloud CLI not found` si no está el Google Cloud SDK.
Instalado el 2026-05-15 via `winget install --id Google.CloudSDK --silent`.
- Versión: Google Cloud SDK 568.0.0
- Ruta: `C:\Users\USER\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin`
- IMPORTANTE: tras instalar, abrir terminal NUEVA (PATH no se refresca en sesiones abiertas).
- Para replicar en Marfil/otra máquina: instalar gcloud ANTES de `gws auth setup`.

## Proyecto GCP

El wizard se cancelaba en Step 3/5 porque NO había proyecto por defecto.
Fix aplicado 2026-05-15 (via gcloud CLI, sin navegador):
- Ya existían proyectos GCP en logos. Usado el existente: **`dr-bareno-dashboard`**
- `gcloud config set project dr-bareno-dashboard`
- APIs habilitadas: sheets, drive, docs, gmail, calendar-json (exit 0)
- NOTA: también existe proyecto GCP `moda-marfil` en logos → usar ese para el
  futuro piloto/migración de Reporte Marfil.

## Estado de instalación

- [x] node v22.14.0 / npm 10.9.2 verificados
- [x] `npm install -g @googleworkspace/cli@0.22.5` — instalado, `gws --version` → `gws 0.22.5`
- [x] Google Cloud SDK 568.0.0 instalado (prerrequisito de `gws auth setup`)
- [ ] `gws auth setup` — PENDIENTE (manual, navegador, en terminal NUEVA)
- [ ] `gws auth login` — PENDIENTE (manual, navegador)
- [ ] Test read-only contra un Sheet — PENDIENTE
- [ ] Migrar `tools/sheets/` de gspread a `gws sheets` — PENDIENTE

## Pasos manuales del usuario (auth) — USAR FLAGS, NO EL WIZARD INTERACTIVO

CRÍTICO: el wizard interactivo se cancela en Step 3/5 (menú TUI de proyecto).
SIEMPRE pasar `--project` para saltar ese menú. Comando correcto:

```
gws auth setup --project dr-bareno-dashboard      # salta el menu TUI roto
gws auth login --readonly --services sheets,drive  # piloto = solo lectura
gws auth status
```

Flags útiles (de `gws auth login --help`):
- `--readonly` → scopes de solo lectura (ideal piloto, consentimiento más simple)
- `--services drive,gmail,sheets` → limita el selector de scopes
- `gws auth setup --project <id> --login` → setup + login en un comando
- `gws auth setup --dry-run` → preview sin cambios

Notas:
- Levanta un loopback local en `http://127.0.0.1:8080` para el callback OAuth.
- Credenciales se guardan cifradas (AES-256-GCM) en el keyring del OS.
- Si la app queda en modo "Testing": agregar el email como Test user en
  APIs & Services > OAuth consent screen, o el login se bloquea.
- Verificar después: `gws auth status` (debe mostrar la cuenta logueada).

## Test de aceptación (read-only, no destructivo)

Una vez logueado, validar SIN escribir nada:

```
gws sheets values get <SPREADSHEET_ID> --range "Hoja1!A1:D10"
```

Criterio de éxito: devuelve JSON estructurado con los valores. Si sale JSON
limpio → el piloto pasa. Recién ahí se migra `tools/sheets/`.

## Reglas de promoción a producción (Marfil)

NO migrar Reporte Marfil hasta que:
1. El piloto Dr. Bareño funcione 1 semana sin fallos.
2. La versión siga pineada en cada runner (.bat / Task Scheduler).
3. Exista plan de rollback (mantener el script gspread viejo hasta confirmar).

## Rollback

`gws` es global y no modifica el proyecto. Para revertir:
`npm uninstall -g @googleworkspace/cli`. El código gspread original queda intacto.
