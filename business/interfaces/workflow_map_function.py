from typing import Dict, Any

def get_workflow_map(self, prompt: str, parameters: Dict[str, Any] = {}) -> Dict[str, Any]:
    """
    Get a mapping of workflows to execute for a given prompt.
    
    Args:
        prompt: The user prompt
        parameters: Additional parameters
        
    Returns:
        Dictionary with workflow information including:
        - primary: The primary workflow ID
        - parallel: List of workflow IDs to execute in parallel
    """
    # If explicitly specified in parameters, use that
    if "workflow_map" in parameters:
        return parameters["workflow_map"]
    
    # Determine primary workflow (default approach)
    primary_workflow = self.determine_workflow(prompt, parameters)
    
    # Default behavior - just return the primary workflow
    workflow_map = {
        "primary": primary_workflow,
        "parallel": []
    }
    
    # For specific types of queries, we might want to run additional workflows
    
    # If this is a master news query, it already handles everything
    if primary_workflow == "master_news_query":
        return workflow_map
    
    # For news-related queries, add the direct query workflow to provide 
    # general information while news data is being fetched
    prompt_lower = prompt.lower()
    if primary_workflow == "news_query" and not any(term in parameters.get("workflow_exclude", []) for term in ["direct_query"]):
        workflow_map["parallel"].append("direct_query")
    
    # For direct queries about markets or stocks, consider adding news query
    if primary_workflow == "direct_query" and any(term in prompt_lower for term in ["stock", "market", "price", "share", "ticker"]):
        if not any(term in parameters.get("workflow_exclude", []) for term in ["news_query"]):
            workflow_map["parallel"].append("news_query")
    
    return workflow_map