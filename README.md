# Project: Banco Master Stock Timeline / Projeto: Linha do Tempo Banco Master

## 🇬🇧 English

### About the Project
This repository contains the assets for a **Banco Master stock timeline** developed for the _Data Extraction and Preparation_ course. It combines a Python data pipeline, a lightweight Django API, and a React + Vite dashboard to help investigate how Banco Masters liquidation reverberated through Banco de Braslia (BSLI4.SA) prices.

### Architecture at a Glance
1. **`data_pipeline.py`** pulls BSLI4.SA quotes from Yahoo Finance, snaps them to the official B3 (BMF) business calendar, derives 7-day/30-day SMAs and annualized volatility, then exports `brb_market_data.json`.
2. **`backend/api/views.py`** exposes `GET /api/market-data/`, serving the cached JSON so the frontend never hammers the Yahoo API during demos.
3. **`frontend/src/App.jsx`** renders an interactive timeline with Recharts, highlighting the Banco Master liquidation window and the "Operação Compliance Zero" investigation period.

### Key Features
- **Deterministic calendar alignment** using `pandas_market_calendars` to prevent gaps on B3 holidays.
- **Rolling analytics** (SMA 7, SMA 30, 30-day volatility) ready for contagion storytelling.
- **CORS-friendly Django API** that guards against missing or corrupted caches with defensive logging.
- **Responsive React dashboard** (Tailwind + Recharts) with contextual Reference Areas, brush-based zoom, and friendly error states.

### Prerequisites
- Python 3.11+
- Node.js 20+
- Recommended Python packages: `django`, `django-cors-headers`, `pandas`, `pandas-market-calendars`, `yfinance`

### Local Setup & Usage
```bash
# 1) Create & activate a virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows

# 2) Install Python dependencies
pip install django django-cors-headers pandas pandas-market-calendars yfinance

# 3) Generate / refresh cached market data
python data_pipeline.py

# 4) Run the Django API (inside backend/)
cd backend
python manage.py migrate
python manage.py runserver 8000

# 5) Start the React client (inside frontend/)
cd ../frontend
npm install
npm run dev
```
Visit `http://localhost:5173` while the backend listens on `http://127.0.0.1:8000`.

### API Contract
- **Endpoint:** `GET /api/market-data/`
- **Response:** Array of objects `{ Date, Open, High, Low, Close, Adj Close, Volume, SMA_7, SMA_30, Volatility_30 }`
- **Errors:**
  - `404` when `brb_market_data.json` has not been generated yet
  - `500` if the JSON cache is corrupted

### Frontend Highlights
- Located in `frontend/src/App.jsx` and powered by **Vite**, **Tailwind CSS**, and **Recharts**
- Reference overlays mark Banco Master liquidation (Nov/2025) and Operação Compliance Zero (Mar/2026)
- Custom tooltips + brush interaction for high-level narrative plus zoomed inspection

### Repository Layout
```
.
├── data_pipeline.py
├── backend/
│   ├── brb_market_data.json         # JSON cache consumed by Django
│   └── api/
│       └── views.py                 # get_market_data endpoint
└── frontend/
    └── src/App.jsx                  # React timeline
```

### Troubleshooting
- **"Data cache not found"** → rerun `python data_pipeline.py` so the JSON exists before hitting the API.
- **CORS or network errors** → confirm the Django server is on `127.0.0.1:8000` and adjust the fetch URL if hosting elsewhere.
- **Empty charts** → check Yahoo Finance rate limits or ticker spelling (`BSLI4.SA`).

### Suggested Next Steps
- Schedule the pipeline (Cron/GitHub Actions) to keep the cache fresh.
- Add authentication + query parameters so researchers can request different tickers or date ranges.
- Persist raw candles in the SQLite DB for audit trails.

---

## 🇧🇷 Português

### Sobre o Projeto
Este repositório centraliza a **linha do tempo das ações do Banco Master**, desenvolvida para a disciplina de _Extração e Preparação de Dados_. O fluxo integra uma pipeline em Python, uma API Django minimalista e um dashboard React + Vite para analisar como a liquidação do Banco Master afetou os preços do Banco de Braslia (BSLI4.SA).

### Arquitetura em Resumo
1. **`data_pipeline.py`** baixa as cotações do BSLI4.SA no Yahoo Finance, alinha com o calendário oficial da B3 (BMF), calcula as médias móveis de 7/30 dias e a volatilidade anualizada, e exporta `brb_market_data.json`.
2. **`backend/api/views.py`** publica o endpoint `GET /api/market-data/`, servindo o JSON em cache para evitar chamadas repetidas ao Yahoo durante as apresentações.
3. **`frontend/src/App.jsx`** exibe a linha do tempo interativa no Recharts, destacando o período da liquidação do Banco Master e da "Operação Compliance Zero".

### Funcionalidades Principais
- **Alinhamento determinstico ao calendário da B3** via `pandas_market_calendars`, evitando buracos em feriados.
- **Mtricas em janela deslizante** (MM7, MM30 e volatilidade de 30 dias) prontas para narrativas de contágio.
- **API Django preparada para CORS** com logging defensivo para caches ausentes ou corrompidos.
- **Dashboard React responsivo** (Tailwind + Recharts) com Reference Areas contextuais, zoom com brush e mensagens de erro amigveis.

### Pré-requisitos
- Python 3.11+
- Node.js 20+
- Pacotes Python recomendados: `django`, `django-cors-headers`, `pandas`, `pandas-market-calendars`, `yfinance`

### Configuração e Uso Local
```bash
# 1) Crie e ative o ambiente virtual
python -m venv .venv
.venv\Scripts\activate  # Windows

# 2) Instale as dependências Python
pip install django django-cors-headers pandas pandas-market-calendars yfinance

# 3) Gere ou atualize o cache de mercado
python data_pipeline.py

# 4) Suba a API Django (dentro de backend/)
cd backend
python manage.py migrate
python manage.py runserver 8000

# 5) Inicie o cliente React (dentro de frontend/)
cd ../frontend
npm install
npm run dev
```
Acesse `http://localhost:5173` enquanto o backend roda em `http://127.0.0.1:8000`.

### Contrato da API
- **Endpoint:** `GET /api/market-data/`
- **Resposta:** Lista de objetos `{ Date, Open, High, Low, Close, Adj Close, Volume, SMA_7, SMA_30, Volatility_30 }`
- **Erros:**
  - `404` quando `brb_market_data.json` ainda no foi gerado
  - `500` se o JSON em cache estiver corrompido

### Destaques do Frontend
- Código em `frontend/src/App.jsx`, construído com **Vite**, **Tailwind CSS** e **Recharts**
- Overlays destacam tanto a liquidação do Banco Master (nov/2025) quanto a Operação Compliance Zero (mar/2026)
- Tooltips customizados e brush para combinar visão macro e investigaes detalhadas

### Estrutura do Repositório
```
.
├── data_pipeline.py
├── backend/
│   ├── brb_market_data.json         # Cache consumido pelo Django
│   └── api/
│       └── views.py                 # Endpoint get_market_data
└── frontend/
    └── src/App.jsx                  # Timeline em React
```

### Dicas de Solução de Problemas
- **"Data cache not found"**  rode `python data_pipeline.py` antes de chamar a API.
- **Erros de CORS ou rede**  confirme se o Django est ouvindo em `127.0.0.1:8000` e ajuste a URL do fetch quando publicar em outro host.
- **Grficos vazios**  verifique limites do Yahoo Finance ou o ticker (`BSLI4.SA`).

### Próximos Passos Sugeridos
- Agende a pipeline (Cron / GitHub Actions) para manter o cache atualizado.
- Adicione autentica e filtros para permitir outros tickers ou intervalos.
- Armazene os candles brutos no SQLite para auditoria.
