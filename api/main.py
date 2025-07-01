import uvicorn
import os
import argparse
from business.barrons.business_logic.business_logic_service import BusinessLogicManager
from business.barrons.config.config import get_config as get_barrons_config
from orchestration.coordinators.orchestrator import Orchestrator
from api.endpoints import setup_app

def main():
    """Entry point for the application."""
    parser = argparse.ArgumentParser(description="Bedrock Claude API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--environment", default="staging", help="Environment (staging, production)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--business", default="barrons", help="Business implementation to use")
    
    args = parser.parse_args()
    
    # Get configuration based on business implementation
    config = None
    business_logic = None
    
    if args.business == "barrons":
        # Get Barron's configuration
        config = get_barrons_config(args.environment)
        # Initialize Barron's business logic
        business_logic = BusinessLogicManager()
    else:
        # Could add support for other business implementations here
        print(f"Warning: Unknown business implementation '{args.business}', defaulting to Barrons")
        config = get_barrons_config(args.environment)
        business_logic = BusinessLogicManager()
    
    # Initialize the orchestrator with business logic and config
    orchestrator = Orchestrator(business_logic, config)
    
    # Setup the app with orchestrator, business name, and config
    app = setup_app(orchestrator, config.get("business_name", args.business), config)
    
    # Start the server
    uvicorn.run(
        app, 
        host=args.host, 
        port=args.port, 
        reload=args.debug
    )

def dev():
    """Development entry point with auto-reload."""
    os.environ["ENVIRONMENT"] = "development"
    main()

if __name__ == "__main__":
    main()
