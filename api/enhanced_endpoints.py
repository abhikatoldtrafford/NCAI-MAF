from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import json
import asyncio
from datetime import datetime
import uuid

from api.schema import (
    PromptRequest,
    PromptResponse,
    ConversationMessage,
    ConversationResponse,
)
from orchestration.coordinators.enhanced_orchestrator import EnhancedOrchestrator

# Create FastAPI app
app = FastAPI(title="Bedrock Claude API")

# Store orchestrator and config in app state
APP_STATE = {
    "orchestrator": None, 
    "business_name": "barrons",
    "config": {}
}

def setup_app(orchestrator: EnhancedOrchestrator, business_name: str = "barrons", config: Dict[str, Any] = None) -> FastAPI:
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

def get_orchestrator() -> EnhancedOrchestrator:
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


# Store for active streaming requests
STREAMING_REQUESTS = {}


async def stream_processor(request_id: str, orchestrator: EnhancedOrchestrator):
    """
    Generator function for streaming responses.
    
    Args:
        request_id: The request ID
        orchestrator: The orchestrator instance
        
    Yields:
        JSON-encoded events
    """
    # Track seen workflow updates
    seen_workflows = set()
    
    # Track if request completed
    completed = False
    
    # Keep yielding updates until completed
    while not completed:
        # Get request status
        request_status = orchestrator.get_request_status(request_id)
        
        # Check if request is not found or completed
        if request_status.get("status") == "not_found":
            yield json.dumps({
                "event": "error",
                "message": f"Request {request_id} not found"
            }) + "\n"
            break
            
        # Check for workflow completions
        if "workflows" in request_status:
            for workflow_id, workflow_result in request_status["workflows"].items():
                if workflow_id not in seen_workflows and workflow_result.get("status") == "completed":
                    # This workflow just completed
                    seen_workflows.add(workflow_id)
                    
                    # Send workflow completion event
                    yield json.dumps({
                        "event": "workflow_complete",
                        "workflow_id": workflow_id,
                        "result": workflow_result
                    }) + "\n"
        
        # Check for streaming updates
        if request_id in STREAMING_REQUESTS:
            for update in STREAMING_REQUESTS[request_id].get("updates", []):
                if not update.get("sent", False):
                    # Send this update
                    yield json.dumps(update["data"]) + "\n"
                    update["sent"] = True
        
        # Check if request is completed
        if request_status.get("status") in ["completed", "failed"]:
            completed = True
            
            # Send completion event
            yield json.dumps({
                "event": "complete",
                "request_id": request_id,
                "status": request_status.get("status"),
                "conversation_id": request_status.get("conversation_id")
            }) + "\n"
            
            # Clean up streaming request
            if request_id in STREAMING_REQUESTS:
                del STREAMING_REQUESTS[request_id]
                
            break
            
        # Wait a bit before checking again
        await asyncio.sleep(0.1)


async def workflow_update_callback(update: Dict[str, Any]):
    """
    Callback for workflow updates.
    
    Args:
        update: The update data
    """
    # Extract request ID
    request_id = update.get("request_id")
    if not request_id or request_id not in STREAMING_REQUESTS:
        return
    
    # Add update to streaming request
    STREAMING_REQUESTS[request_id]["updates"].append({
        "sent": False,
        "data": update
    })

@app.post("/feedback", response_model=PromptResponse)
async def feedback(request: PromptRequest, orchestrator: EnhancedOrchestrator = Depends(get_orchestrator)):
    """
    Process a chat message feedback with RDS support.
    Args:
        request: The prompt request
        orchestrator: The orchestrator instance
    Returns:
        The response or a streaming response
    """
    request.prompt = "User-Feedback"
    if request.parameters is None:
        request.parameters = {}
    if request.conversation_id:
        request.parameters["session_id"] = request.conversation_id
    request.stream = False
    return await chat(request, orchestrator)

@app.post("/chat", response_model=PromptResponse)
async def chat(request: PromptRequest, orchestrator: EnhancedOrchestrator = Depends(get_orchestrator)):
    """
    Process a chat message with conversation support.
    
    Args:
        request: The prompt request
        orchestrator: The orchestrator instance
        
    Returns:
        The response or a streaming response
    """
    try:
        # Add business name to parameters
        business_name = get_business_name()
        enriched_params = {
            **request.parameters, 
            "business_name": business_name
        }
        
        # Pass conversation ID if provided
        if request.conversation_id:
            enriched_params["conversation_id"] = request.conversation_id
            
        # Set streaming flag
        enriched_params["stream"] = request.stream
        
        # Handle string vs. dictionary prompt format
        prompt = request.prompt
        if isinstance(prompt, str):
            prompt = {
                "id": "raw_prompt",
                "version": "1.0",
                "text": prompt
            }
            
        # Ensure system prompt is in dictionary format
        if "system_prompt" in enriched_params and isinstance(enriched_params["system_prompt"], str):
            enriched_params["system_prompt"] = {
                "id": "raw_system_prompt",
                "version": "1.0",
                "text": enriched_params["system_prompt"]
            }
        if request.stream:
            return StreamingResponse(orchestrator.process_prompt_with_streaming(prompt=prompt, parameters=enriched_params), media_type="application/x-ndjson")
        else:
            async for result in orchestrator.process_prompt_with_streaming(prompt=prompt, parameters=enriched_params):
                if isinstance(result, dict):
                    return PromptResponse(
                        response=result.get("response", {}),
                        request_id=result.get("request_id", ""),
                        conversation_id=result.get("conversation_id"),
                        workflow=result.get("workflow"),
                        status=result.get("status"),
                        error=result.get("error"),
                        data=result.get("data")
                    )
                else:
                    return PromptResponse(
                        response=str(result),
                        request_id="unknown"
                    )
        # # If streaming is requested
        # if request.stream:
        #     # Generate request ID
        #     request_id = str(uuid.uuid4())
            
        #     # Set up streaming context
        #     STREAMING_REQUESTS[request_id] = {
        #         "status": "processing",
        #         "started_at": datetime.now().isoformat(),
        #         "updates": []
        #     }
            
        #     # Add request ID to parameters
        #     enriched_params["request_id"] = request_id
            
        #     # Process prompt in background
        #     asyncio.create_task(
        #         orchestrator.process_prompt_with_streaming(
        #             prompt=prompt,
        #             parameters=enriched_params,
        #             callback=workflow_update_callback
        #         )
        #     )
            
        #     # Return streaming response
        #     return StreamingResponse(
        #         stream_processor(request_id, orchestrator),
        #         media_type="text/event-stream"
        #     )
        # else:
        #     # Process prompt normally
        #     result = await orchestrator.process_prompt_with_streaming(
        #         prompt=prompt,
        #         parameters=enriched_params
        #     )
            # Format response
            # if isinstance(result, dict):
            #     return PromptResponse(
            #         response=result.get("response", {}),
            #         request_id=result.get("request_id", ""),
            #         conversation_id=result.get("conversation_id"),
            #         workflow=result.get("workflow"),
            #         status=result.get("status"),
            #         error=result.get("error"),
            #         data=result.get("data")
            #     )
            # else:
            #     return PromptResponse(
            #         response=str(result),
            #         request_id="unknown"
            #     )
    
    except Exception as e:
        error_msg = str(e)
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, orchestrator: EnhancedOrchestrator = Depends(get_orchestrator)):
    """
    Get a conversation by ID.
    
    Args:
        conversation_id: The conversation ID
        orchestrator: The orchestrator instance
        
    Returns:
        The conversation
    """
    conversation = orchestrator.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    
    # Convert to response model
    messages = [
        ConversationMessage(
            role=msg["role"],
            content=msg["content"],
            timestamp=msg["timestamp"],
            metadata=msg.get("metadata")
        )
        for msg in conversation["messages"]
    ]
    
    return ConversationResponse(
        conversation_id=conversation_id,
        messages=messages,
        created_at=conversation["created_at"].isoformat(),
        last_updated=conversation["last_updated"].isoformat()
    )


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, orchestrator: EnhancedOrchestrator = Depends(get_orchestrator)):
    """
    Delete a conversation.
    
    Args:
        conversation_id: The conversation ID
        orchestrator: The orchestrator instance
        
    Returns:
        Success message
    """
    result = orchestrator.conversation_store.delete_conversation(conversation_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    
    return {"status": "success", "message": f"Conversation {conversation_id} deleted"}


@app.get("/health")
async def health_check():
    """
    Check the health of the API.
    
    Returns:
        Health status
    """
    return {"status": "healthy"}


@app.get("/status/{request_id}")
async def get_request_status(request_id: str, orchestrator: EnhancedOrchestrator = Depends(get_orchestrator)):
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