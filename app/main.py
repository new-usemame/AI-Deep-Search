"""FastAPI application entry point."""
import asyncio
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app.coordinator import AgentCoordinator
from app.config import settings
from app.data_manager import DataManager
import os

app = FastAPI(title="Multi-Agent MacBook Searcher")

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Global coordinator instance
coordinator: AgentCoordinator = None
coordinator_task: asyncio.Task = None


class SearchRequest(BaseModel):
    """Request model for starting a search."""
    model_numbers: List[str]
    exclusions: List[str]
    sites: List[str] = ["ebay.com"]


class SearchConfig(BaseModel):
    """Configuration for search parameters."""
    model_numbers: List[str]
    exclusions: List[str]
    sites: List[str]


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main dashboard."""
    index_path = os.path.join(templates_dir, "index.html")
    with open(index_path, "r") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/search/start")
async def start_search(request: SearchRequest):
    """Start a new search with the specified parameters."""
    global coordinator, coordinator_task
    
    if coordinator and coordinator.is_running:
        raise HTTPException(status_code=400, detail="Search already running")
    
    # Stop any existing coordinator
    if coordinator:
        await coordinator.stop_search()
    
    # Create new coordinator
    coordinator = AgentCoordinator(
        model_numbers=request.model_numbers,
        exclusions=request.exclusions,
        sites=request.sites
    )
    
    # Start search in background
    coordinator_task = asyncio.create_task(coordinator.start_search())
    
    return {"status": "started", "message": "Search started successfully"}


@app.post("/api/search/stop")
async def stop_search():
    """Stop the current search."""
    global coordinator
    
    if not coordinator:
        raise HTTPException(status_code=400, detail="No search running")
    
    await coordinator.stop_search()
    
    return {"status": "stopped", "message": "Search stopped successfully"}


@app.post("/api/search/pause")
async def pause_search():
    """Pause the current search."""
    global coordinator
    
    if not coordinator:
        raise HTTPException(status_code=400, detail="No search running")
    
    await coordinator.pause_search()
    
    return {"status": "paused", "message": "Search paused successfully"}


@app.post("/api/search/resume")
async def resume_search():
    """Resume the current search."""
    global coordinator
    
    if not coordinator:
        raise HTTPException(status_code=400, detail="No search running")
    
    await coordinator.resume_search()
    
    return {"status": "resumed", "message": "Search resumed successfully"}


@app.get("/api/search/status")
async def get_status():
    """Get the current search status."""
    global coordinator
    
    if not coordinator:
        return {
            "is_running": False,
            "total_agents": 0,
            "active_agents": 0,
            "paused_agents": 0,
            "agents": [],
            "data_stats": {"total_listings": 0},
        }
    
    return coordinator.get_status()


@app.get("/api/config/default")
async def get_default_config():
    """Get default configuration."""
    return {
        "model_numbers": settings.get_model_numbers(),
        "exclusions": settings.get_exclusions(),
        "sites": settings.get_sites(),
        "agent_count": settings.agent_count,
        "max_pages_per_search": settings.max_pages_per_search,
    }


@app.get("/api/results/download")
async def download_results():
    """Download the CSV file with results."""
    data_manager = DataManager()
    csv_path = data_manager.csv_path
    
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="No results file found")
    
    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename="macbook_results.csv"
    )


@app.get("/api/results/count")
async def get_results_count():
    """Get the number of results collected."""
    data_manager = DataManager()
    stats = data_manager.get_stats()
    
    return {
        "total_listings": stats["total_listings"],
        "csv_path": stats["csv_path"],
        "csv_exists": stats["csv_exists"],
    }


@app.get("/api/results/list")
async def list_results(limit: int = 100):
    """Get a list of results."""
    data_manager = DataManager()
    listings = data_manager.get_all_listings()
    
    # Return most recent first, limited
    listings.reverse()
    return {"results": listings[:limit], "total": len(listings)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
