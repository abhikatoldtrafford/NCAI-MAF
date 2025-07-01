from typing import Dict, Any, List, Optional
from src.orchestration.coordinators.service_coordinator import ServiceCoordinator
# TODO from src.application -> services -> query_service, stock_data_service, analysis_service, llm_service, prompt_service
from src.orchestration.workflows.stock_analysis_workflow import StockAnalysisWorkflow

class AnalysisCoordinator(ServiceCoordinator[str, Dict[str, Any]]):
    """Coordinator for analysis services."""
    
    async def coordinate(self, input_data: str) -> Dict[str, Any]:
        """
        Coordinate analysis services to process the input data.
        
        Args:
            input_data: The raw query string
            
        Returns:
            The analysis result
        """
        # Get required services
        query_service = self.services.get("query_service")
        stock_data_service = self.services.get("stock_data_service")
        analysis_service = self.services.get("analysis_service")
        llm_service = self.services.get("llm_service")
        prompt_service = self.services.get("prompt_service")
        
        # Check that all required services are available
        if not all([query_service, stock_data_service, analysis_service, llm_service, prompt_service]):
            missing_services = []
            if not query_service:
                missing_services.append("query_service")
            if not stock_data_service:
                missing_services.append("stock_data_service")
            if not analysis_service:
                missing_services.append("analysis_service")
            if not llm_service:
                missing_services.append("llm_service")
            if not prompt_service:
                missing_services.append("prompt_service")
            
            raise ValueError(f"Missing required services: {', '.join(missing_services)}")
        
        # Create and execute the workflow
        workflow = StockAnalysisWorkflow(
            query_service=query_service,
            stock_data_service=stock_data_service,
            analysis_service=analysis_service,
            llm_service=llm_service,
            prompt_service=prompt_service
        )
        
        return await workflow.execute(input_data)