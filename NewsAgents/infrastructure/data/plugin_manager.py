import logging
from typing import Dict, Any, List, Optional
from NewsAgents.infrastructure.data.plugins.plugin_interface import DataPluginInterface

# Configure logging
logger = logging.getLogger(__name__)

class PluginManager:
    """
    Manager for data layer plugins.
    
    Handles registration, discovery, and execution of plugins.
    """
    
    def __init__(self):
        """Initialize the plugin manager."""
        self.plugins = {}
    
    def register_plugin(self, plugin_id: str, plugin: DataPluginInterface) -> None:
        """
        Register a plugin.
        
        Args:
            plugin_id: Identifier for the plugin
            plugin: The plugin instance
        """
        self.plugins[plugin_id] = plugin
        logger.info(f"Registered plugin: {plugin_id}")
    
    def get_plugin(self, plugin_id: str) -> Optional[DataPluginInterface]:
        """
        Get a plugin by ID.
        
        Args:
            plugin_id: Identifier for the plugin
            
        Returns:
            The plugin instance or None if not found
        """
        return self.plugins.get(plugin_id)
    
    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a query using the appropriate plugin.
        
        Args:
            query: The query string to execute
            parameters: Additional parameters for query execution
            
        Returns:
            Dictionary containing the query results and metadata
        """
        parameters = parameters or {}
        
        # Get specific plugin if requested
        plugin_id = parameters.get("plugin")
        if plugin_id:
            plugin = self.get_plugin(plugin_id)
            if not plugin:
                return {
                    "status": "error",
                    "message": f"Plugin not found: {plugin_id}",
                    "query": query
                }
            
            # Execute query with the specified plugin
            return plugin.process_query(query, parameters)
        
        # Find a suitable plugin automatically
        for plugin_id, plugin in self.plugins.items():
            if plugin.validate_query(query, parameters):
                logger.info(f"Using plugin {plugin_id} for query: {query[:50]}...")
                return plugin.process_query(query, parameters)
        
        # No suitable plugin found
        return {
            "status": "error",
            "message": "No suitable plugin found for query",
            "query": query
        }
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        Get a list of all registered plugins and their capabilities.
        
        Returns:
            List of dictionaries containing plugin information
        """
        return [
            {"id": plugin_id, **plugin.get_capabilities()}
            for plugin_id, plugin in self.plugins.items()
        ]