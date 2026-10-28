# SOP: Actualización diaria del Dashboard

## Automático (Task Scheduler)
- `run_update.bat` corre cada hora
- Jala Meta Ads API + Google Sheets → genera `data.json` → push a GitHub Pages

## Manual
1. Abrir terminal en la carpeta del proyecto
2. `venv\Scripts\activate`
3. `python main.py`

## Google Sheets — qué llena la asistente cada día
### Tab CLINICA
- Fecha (YYYY-MM-DD)
- Citas Agendadas (número)
- Procedimientos Vendidos (número)
- **Citas Bot** (número): citas que llegaron por el WhatsApp del bot
- **Citas Asistente** (número): citas que cerró la asistente en su WhatsApp
  - Citas Bot + Citas Asistente debería dar Citas Agendadas. Lo que no cuadre sale
    como "sin atribuir" en la pestaña Bot vs Asistente.

### Tab PROCEDIMIENTOS
- Una fila por procedimiento realizado
- Fecha, Que se hizo, Valor (sin puntos, ej: 4500000)
- **Canal**: `Bot` o `Asistente`, según por dónde llegó el paciente. Vacío = sin atribuir.

## Pestaña "Bot vs Asistente"
- Bot = campañas de Meta con **ASISTENTE** en el nombre. Asistente = el resto de
  campañas de la clínica (FaceTech se excluye por `META_CAMPAIGN_ID_FACETECH`).
  Si se crea una campaña nueva para el bot, DEBE llevar "ASISTENTE" en el nombre.
- Gasto y conversaciones: Meta (`onsite_conversion.messaging_conversation_started_7d`).
- Citas y ventas: el Sheet (las dos columnas de arriba + Canal).
- Control: Pancake cuenta chats del bot y la primera vez que puso la etiqueta
  `CITA AGENDADA` (necesita `PANCAKE_API_KEY` / `PANCAKE_PAGE_ID` en `.env`).
  Si Pancake marca más citas que el Sheet, alguien no está registrando las del bot.

### Tab FACETECH
- Fecha, Leads, Compras, Valor Ticket COP

## Ver el dashboard
- URL pública: https://TU_USUARIO.github.io/dr-bareno-dashboard
- iPhone: Safari → compartir → "Agregar a pantalla de inicio"
