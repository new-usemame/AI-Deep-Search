"""Coordinator to manage multiple parallel search agents."""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from app.agent import SearchAgent
from app.filters import ListingFilter
from app.data_manager import DataManager
from app.llm_client import LLMClient
from app.config import settings

logger = logging.getLogger(__name__)


class AgentCoordinator:
    """Manages a pool of search agents running in parallel."""
    
    def __init__(
        self,
        model_numbers: List[str],
        exclusions: List[str],
        sites: List[str] = None
    ):
        self.model_numbers = model_numbers
        self.exclusions = exclusions
        self.sites = sites or ["ebay.com"]
        
        self.agents: List[SearchAgent] = []
        self.data_manager = DataManager()
        self.llm_client = LLMClient()
        
        self.is_running = False
        self.search_task: Optional[asyncio.Task] = None
    
    async def start_search(self):
        """Start all agents in parallel."""
        if self.is_running:
            logger.warning("Search already running, ignoring start request")
            return
        
        logger.info(f"Starting search with {settings.agent_count} agents")
        logger.info(f"Model numbers: {self.model_numbers}")
        logger.info(f"Exclusions: {self.exclusions}")
        
        self.is_running = True
        self.agents = []
        
        # Create filters
        filter_config = ListingFilter(
            model_numbers=self.model_numbers,
            exclusions=self.exclusions,
            require_activation_lock=True
        )
        
        # Distribute model numbers across agents
        # If we have fewer model numbers than agents, some agents will search the same models
        agent_count = settings.agent_count
        tasks = []
        
        logger.info(f"Creating {agent_count} agents...")
        for agent_id in range(agent_count):
            # Assign model number (round-robin)
            model_number = self.model_numbers[agent_id % len(self.model_numbers)]
            
            logger.info(f"Creating Agent {agent_id} for model {model_number}")
            
            # Create agent
            agent = SearchAgent(
                agent_id=agent_id,
                model_number=model_number,
                filter_config=filter_config,
                data_manager=self.data_manager,
                llm_client=self.llm_client
            )
            
            self.agents.append(agent)
            
            # Start agent in background
            task = asyncio.create_task(agent.start())
            tasks.append(task)
        
        logger.info(f"All {len(tasks)} agents started. Waiting for completion...")
        
        # Wait for all agents to complete
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Agent {i} error: {result}", exc_info=True)
                else:
                    logger.info(f"Agent {i} completed successfully")
        except Exception as e:
            logger.error(f"Coordinator error: {e}", exc_info=True)
        finally:
            self.is_running = False
            logger.info("Search completed. All agents stopped.")
            # Don't close LLM client here as it might be reused
    
    async def stop_search(self):
        """Stop all agents."""
        self.is_running = False
        
        for agent in self.agents:
            await agent.stop()
        
        if self.search_task:
            self.search_task.cancel()
            try:
                await self.search_task
            except asyncio.CancelledError:
                pass
    
    async def pause_search(self):
        """Pause all agents."""
        for agent in self.agents:
            await agent.pause()
    
    async def resume_search(self):
        """Resume all agents."""
        for agent in self.agents:
            await agent.resume()
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        agent_stats = [agent.get_stats() for agent in self.agents]
        
        return {
            "is_running": self.is_running,
            "total_agents": len(self.agents),
            "active_agents": sum(1 for a in self.agents if a.is_running),
            "paused_agents": sum(1 for a in self.agents if a.is_paused),
            "agents": agent_stats,
            "data_stats": self.data_manager.get_stats(),
        }
    
    def get_results_count(self) -> int:
        """Get total number of results collected."""
        return self.data_manager.get_stats()["total_listings"]
