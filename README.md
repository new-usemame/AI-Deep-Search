# Multi-Agent Deep Web Search System for Activation-Locked MacBooks

A sophisticated multi-threaded AI agent system that uses 12 parallel agents to deeply search eBay (and other configurable sites) for activation-locked MacBooks. Each agent uses Playwright for browser automation and OpenRouter LLMs to analyze listings intelligently.

## Features

- **12 Parallel AI Agents**: Multiple agents search simultaneously for maximum coverage
- **Deep Search**: Automatically paginates through search results and analyzes each listing
- **Smart Detection**: Uses LLMs to detect activation locks (explicit or implicit mentions)
- **Exclusion Filtering**: Automatically excludes listings with broken screens, bad batteries, etc.
- **Real-time Dashboard**: Web UI to monitor search progress and download results
- **CSV Export**: All results exported to CSV with links and metadata

## Technology Stack

- **Python 3.11+** with FastAPI
- **Playwright** for browser automation
- **OpenRouter API** for LLM inference (supports cheap models like Llama)
- **SQLite** for tracking (optional)
- **Railway** for deployment

## Setup

### Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
playwright install chromium
```

2. **Create `.env` file:**
```bash
cp .env.example .env
# Edit .env and add your OpenRouter API key
```

3. **Run the application:**
```bash
uvicorn app.main:app --reload
```

4. **Access the dashboard:**
Open http://localhost:8000 in your browser

### Railway Deployment

1. **Create a Railway project** and connect your repository

2. **Set environment variables** in Railway dashboard:
   - `OPENROUTER_API_KEY`: Your OpenRouter API key
   - `OPENROUTER_MODEL`: Model to use (default: `meta-llama/llama-3.2-3b-instruct`)
   - `AGENT_COUNT`: Number of agents (default: 12)
   - Other optional variables from `.env.example`

3. **Deploy:**
Railway will automatically detect the `Procfile` and deploy the application.

## Usage

1. **Configure Search:**
   - Enter MacBook model numbers (e.g., A1706, A1707, A1932)
   - Set exclusion terms (e.g., "broken screen", "bad battery")
   - Select sites to search (default: ebay.com)

2. **Start Search:**
   - Click "Start Search" to begin
   - Monitor progress in real-time on the dashboard
   - View agent status and results as they're collected

3. **Download Results:**
   - Click "Download CSV" to get all results
   - CSV includes: title, price, model number, link, condition, activation lock status, seller, etc.

## Configuration

### Model Numbers
Comma-separated list of MacBook model numbers to search for (e.g., `A1706,A1707,A1932`)

### Exclusions
Comma-separated list of terms that should exclude a listing (e.g., `broken screen,bad battery,cracked`)

### OpenRouter Models
Recommended cheap models:
- `meta-llama/llama-3.2-3b-instruct` (~$0.05 per 1M tokens)
- `google/gemini-flash-1.5` (~$0.075 per 1M tokens)
- `openai/gpt-4o-mini` (~$0.15 per 1M tokens)

## How It Works

1. **Coordinator** spawns 12 parallel agents
2. Each **Agent**:
   - Uses Playwright to navigate eBay search pages
   - Extracts listing data from search results
   - Uses LLM to analyze each listing for activation lock mentions
   - Applies exclusion filters
   - Adds matching listings to CSV

3. **LLM Analysis** detects:
   - Explicit mentions: "activation lock", "iCloud locked"
   - Implicit mentions: "can't unlock", "previous owner", "for parts", "as-is"

4. **Results** are deduplicated and exported to CSV

## API Endpoints

- `GET /` - Web dashboard
- `POST /api/search/start` - Start a new search
- `POST /api/search/stop` - Stop current search
- `GET /api/search/status` - Get search status
- `GET /api/results/download` - Download CSV
- `GET /api/results/list` - List results

## Notes

- The system respects rate limits and includes delays to avoid detection
- CAPTCHAs will pause agents automatically
- Results are deduplicated by URL and listing hash
- The system can run for extended periods to deeply search through many pages

## License

MIT
