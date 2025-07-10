from fastapi import FastAPI, HTTPException, Depends
from typing import Dict, Any
from NewsAgents.orchestration.coordinators.orchestrator import Orchestrator
from api.schema import PromptRequest, PromptResponse

# Create FastAPI app
app = FastAPI(title="Bedrock Claude API")

# Store orchestrator and config in app state
APP_STATE = {"orchestrator": None, "business_name": "barrons", "config": {}}


def setup_app(orchestrator: Orchestrator, business_name: str = "barrons", config: Dict[str, Any] = None) -> FastAPI:
    """
    Set up the FastAPI app with orchestrator.

    Args:
        orchestrator: The orchestrator instance
        business_name: The business implementation name (default: barrons)
        config: Configuration dictionary

    Returns:
        The FastAPI app
    """
    APP_STATE["orchestrator"] = orchestrator
    APP_STATE["business_name"] = business_name
    APP_STATE["config"] = config or {}
    return app


def get_orchestrator() -> Orchestrator:
    """
    Get the orchestrator from app state.

    Returns:
        The orchestrator instance
    """
    orchestrator = APP_STATE.get("orchestrator")
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    return orchestrator


def get_business_name() -> str:
    """
    Get the business name from app state.

    Returns:
        The business name
    """
    return APP_STATE.get("business_name", "barrons")


def get_config() -> Dict[str, Any]:
    """
    Get the config from app state.

    Returns:
        The config dictionary
    """
    return APP_STATE.get("config", {})


@app.post("/query", response_model=PromptResponse)
async def process_query(request: PromptRequest, orchestrator: Orchestrator = Depends(get_orchestrator)):
    """
    Process a prompt and generate a response.

    Args:
        request: The prompt request
        orchestrator: The orchestrator instance

    Returns:
        The response
    """
    try:
        # Add business name and config to parameters
        business_name = get_business_name()
        enriched_params = {**request.parameters, "business_name": business_name}

        # Handle string vs. dictionary prompt format
        prompt = request.prompt
        if isinstance(prompt, str):
            # If prompt is a string, convert to dictionary format expected by orchestrator
            # We need to provide id and version as required by the orchestrator
            # For string prompts, we'll use a special format to indicate it's a raw prompt
            prompt = {
                "id": "raw_prompt",
                "version": "1",
                "text": prompt,  # Store original text for reference
            }

            # Ensure system prompt is also in dictionary format
            if "system_prompt" in enriched_params and isinstance(enriched_params["system_prompt"], str):
                enriched_params["system_prompt"] = {
                    "id": "raw_system_prompt",
                    "version": "1",
                    "text": enriched_params["system_prompt"],
                }
            else:
                # Create default system prompt if not provided
                enriched_params["system_prompt"] = {"id": "default_system_prompt", "version": "1.0"}

        # Process the prompt - now with await since process_prompt is async
        result = await orchestrator.process_prompt(prompt, enriched_params)

        # Ensure result is properly formatted for PromptResponse
        if isinstance(result, dict):
            # Handle case where response field is itself a dictionary
            response_value = result.get("response", "")

            # If response is a dictionary, extract its message or convert to string
            if isinstance(response_value, dict):
                if "message" in response_value:
                    response_text = response_value["message"]
                else:
                    # Convert dictionary to string representation as fallback
                    response_text = str(response_value)
            else:
                response_text = response_value

            # Create a response that matches our model
            response_obj = PromptResponse(
                response=response_text,
                request_id=result.get("request_id", ""),
                workflow=result.get("workflow"),
                status=result.get("status") or (response_value.get("status") if isinstance(response_value, dict) else None),
                error=result.get("error") or (response_value.get("error") if isinstance(response_value, dict) else None),
                data=result.get("data") or (response_value.get("data") if isinstance(response_value, dict) else None),
            )
            return response_obj
        else:
            # If somehow result is not a dict, convert to string
            return PromptResponse(response=str(result), request_id="unknown")

    except Exception as e:
        error_msg = str(e)
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/health")
async def health_check():
    """
    Check the health of the API.

    Returns:
        Health status
    """
    return {"status": "healthy"}


@app.get("/status/{request_id}")
async def get_request_status(request_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)):
    """
    Get the status of a request.

    Args:
        request_id: The request ID
        orchestrator: The orchestrator instance

    Returns:
        Request status
    """
    status = orchestrator.get_request_status(request_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
    return status
