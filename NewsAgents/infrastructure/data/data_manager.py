import logging
from typing import Dict, Any, Optional
from NewsAgents.infrastructure.data.plugin_manager import PluginManager
from NewsAgents.infrastructure.data.plugins.query_processor import QueryProcessor

# Configure logging
logger = logging.getLogger(__name__)

class DataManager:
    """
    Manager for data operations and sources.
    
    Coordinates data access, plugin management, and query processing.
    """
    
    def __init__(self):
        """Initialize the data manager."""
        # Initialize data sources first
        self.data_sources = {}
        
        # Initialize plugin manager
        self.plugin_manager = PluginManager()
        
        # Initialize and register default plugins
        self._register_default_plugins()
    
    def get_data(self, query: str, source: str = "default", parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get data based on a query.
        
        Args:
            query: The query string
            source: The data source identifier
            parameters: Additional parameters for query execution
            
        Returns:
            Dictionary containing the query results and metadata
        """
        # Merge parameters
        params = parameters or {}
        params["data_source"] = source
        
        # Execute the query using the plugin manager
        return self.plugin_manager.execute_query(query, params)
    
    def register_data_source(self, source_id: str, source_config: Dict[str, Any]) -> None:
        """
        Register a new data source.
        
        Args:
            source_id: Identifier for the data source
            source_config: Configuration for the data source
        """
        # Store the data source configuration
        self.data_sources[source_id] = source_config
        
        # Register with each plugin that needs data sources
        query_processor = self.plugin_manager.get_plugin("query_processor")
        if query_processor:
            query_processor.register_data_source(source_id, source_config)
        
        logger.info(f"Registered data source: {source_id}")
    
    def register_custom_plugin(self, plugin_id: str, plugin) -> None:
        """
        Register a custom plugin.
        
        Args:
            plugin_id: Identifier for the plugin
            plugin: The plugin instance
        """
        self.plugin_manager.register_plugin(plugin_id, plugin)
    
    def _register_default_plugins(self) -> None:
        """Register default plugins."""
        # Register the query processor plugin
        query_processor = QueryProcessor(self.data_sources)
        self.plugin_manager.register_plugin("query_processor", query_processor)