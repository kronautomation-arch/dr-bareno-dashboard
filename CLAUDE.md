# Dr. Bareño Dashboard

PWA mobile-first para iPhone. Dashboard ejecutivo de métricas para la clínica del Dr. John Bareño (oftalmólogo, cirugía estética facial, Colombia).

## WAT Framework
- TOOLS: `tools/meta/`, `tools/sheets/`, `tools/metrics/`, `tools/core/`
- AGENT: `main.py` (orquestador)
- WORKFLOWS: `workflows/`

## Dos líneas de negocio
1. **CLÍNICA**: citas (precio fijo en `.env`) + procedimientos (variable por cirugía)
2. **FACETECH**: congreso, leads vs compras

## Data flow
Meta Ads API + Google Sheets → `main.py` → `dashboard/data.json` → GitHub Pages → iPhone Safari

## Moneda
COP (pesos colombianos)

## Sheets structure
- Tab `CLINICA`: Fecha | Citas Agendadas | Procedimientos Vendidos
- Tab `PROCEDIMIENTOS`: Fecha | Tipo Cirugía | Valor COP
- Tab `FACETECH`: Fecha | Leads | Compras | Valor Ticket COP

## Setup
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # llenar valores
python main.py
```
