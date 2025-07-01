import time
import logging
import re
from typing import Dict, Any, List, Optional, Union, Callable, Pattern
from infrastructure.data.plugins.plugin_interface import DataPluginInterface

# Configure logging
logger = logging.getLogger(__name__)

class QueryProcessor(DataPluginInterface):
    """
    Plugin for processing queries in the data layer.
    
    This plugin handles query parsing, validation, and execution,
    with support for different query formats and data sources.
    """
    
    def __init__(self, data_sources: Optional[Dict[str, Any]] = None):
        """
        Initialize the query processor plugin.
        
        Args:
            data_sources: Dictionary of available data sources
        """
        self.data_sources = data_sources or {}
        self.query_handlers = {}
        self.query_patterns = {}
        
        # Register default handlers
        self._register_default_handlers()
    
    def process_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a query and return results.
        
        Args:
            query: The query string to process
            parameters: Additional parameters for query processing
            
        Returns:
            Dictionary containing the query results and metadata
        """
        start_time = time.time()
        parameters = parameters or {}
        
        try:
            # Log the query
            logger.info(f"Processing query: {query[:100]}{'...' if len(query) > 100 else ''}")
            
            # Validate the query
            if not self.validate_query(query, parameters):
                return {
                    "status": "error",
                    "message": "Invalid query format",
                    "query": query,
                    "execution_time": time.time() - start_time
                }
            
            # Determine the handler to use
            handler, match = self._get_handler(query)
            
            if not handler:
                return {
                    "status": "error",
                    "message": "No handler found for query",
                    "query": query,
                    "execution_time": time.time() - start_time
                }
            
            # Get data source
            data_source_id = parameters.get("data_source", "default")
            data_source = self.data_sources.get(data_source_id)
            
            if not data_source and data_source_id != "default":
                return {
                    "status": "error",
                    "message": f"Data source not found: {data_source_id}",
                    "query": query,
                    "execution_time": time.time() - start_time
                }
            
            # Execute the query
            results = handler(query, match, data_source, parameters)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Log the execution time
            logger.info(f"Query executed in {execution_time:.4f} seconds")
            
            # Return results with metadata
            return {
                "status": "success",
                "data": results,
                "query": query,
                "data_source": data_source_id,
                "execution_time": execution_time
            }
            
        except Exception as e:
            # Log the error
            logger.error(f"Error processing query: {str(e)}", exc_info=True)
            
            # Return error information
            return {
                "status": "error",
                "message": f"Error processing query: {str(e)}",
                "query": query,
                "execution_time": time.time() - start_time
            }
    
    def validate_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate if a query can be processed by this plugin.
        
        Args:
            query: The query string to validate
            parameters: Additional parameters for validation
            
        Returns:
            True if the query is valid for this plugin, False otherwise
        """
        if not query or not isinstance(query, str):
            return False
        
        # Check if any registered pattern matches
        handler, _ = self._get_handler(query)
        return handler is not None
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get the capabilities of this plugin.
        
        Returns:
            Dictionary containing plugin capabilities and metadata
        """
        return {
            "name": "Query Processor",
            "version": "1.0.0",
            "description": "Plugin for processing data queries",
            "supported_formats": list(self.query_patterns.keys()),
            "data_sources": list(self.data_sources.keys())
        }
    
    def register_data_source(self, source_id: str, source: Any) -> None:
        """
        Register a new data source.
        
        Args:
            source_id: Identifier for the data source
            source: The data source object or connection
        """
        self.data_sources[source_id] = source
        logger.info(f"Registered data source: {source_id}")
    
    def register_query_handler(self, name: str, pattern: str, handler: Callable) -> None:
        """
        Register a new query handler.
        
        Args:
            name: Name for the query handler
            pattern: Regex pattern for matching queries
            handler: Handler function for processing matching queries
        """
        self.query_patterns[name] = re.compile(pattern, re.IGNORECASE)
        self.query_handlers[name] = handler
        logger.info(f"Registered query handler: {name}")
    
    def _register_default_handlers(self) -> None:
        """Register default query handlers."""
        # Simple keyword query handler
        self.register_query_handler(
            "keyword",
            r"(?:find|search|get)\s+(.+?)(?:\s+from\s+(.+))?$",
            self._handle_keyword_query
        )
        
        # SQL-like query handler
        self.register_query_handler(
            "sql",
            r"SELECT\s+(.+?)\s+FROM\s+(.+?)(?:\s+WHERE\s+(.+))?(?:\s+LIMIT\s+(\d+))?$",
            self._handle_sql_query
        )
    
    def _get_handler(self, query: str) -> tuple:
        """
        Get the appropriate handler for a query.
        
        Args:
            query: The query string
            
        Returns:
            Tuple of (handler_function, regex_match)
        """
        for name, pattern in self.query_patterns.items():
            match = pattern.search(query)
            if match:
                return self.query_handlers[name], match
        
        return None, None
    
    def _handle_keyword_query(self, query: str, match, data_source: Any, parameters: Dict[str, Any]) -> Any:
        """Handle a keyword-based query."""
        keywords = match.group(1).strip()
        source = match.group(2).strip() if match.group(2) else None
        
        # Simple implementation for demonstration
        # In a real implementation, this would interact with the data source
        return {
            "query_type": "keyword",
            "keywords": keywords,
            "source": source,
            "results": [
                {"id": 1, "relevance": 0.95, "data": f"Result for {keywords}"},
                {"id": 2, "relevance": 0.85, "data": f"Another result for {keywords}"}
            ]
        }
    
    def _handle_sql_query(self, query: str, match, data_source: Any, parameters: Dict[str, Any]) -> Any:
        """Handle an SQL-like query."""
        select_clause = match.group(1).strip()
        from_clause = match.group(2).strip()
        where_clause = match.group(3).strip() if match.group(3) else None
        limit_clause = int(match.group(4)) if match.group(4) else None
        
        # Simple implementation for demonstration
        # In a real implementation, this would execute the query against the data source
        return {
            "query_type": "sql",
            "select": select_clause,
            "from": from_clause,
            "where": where_clause,
            "limit": limit_clause,
            "results": [
                {"id": 1, "data": f"Data from {from_clause}"},
                {"id": 2, "data": f"More data from {from_clause}"}
            ]
        }