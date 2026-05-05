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

### Tab PROCEDIMIENTOS
- Una fila por procedimiento realizado
- Fecha, Tipo Cirugía, Valor COP (sin puntos, ej: 4500000)

### Tab FACETECH
- Fecha, Leads, Compras, Valor Ticket COP

## Ver el dashboard
- URL pública: https://TU_USUARIO.github.io/dr-bareno-dashboard
- iPhone: Safari → compartir → "Agregar a pantalla de inicio"
