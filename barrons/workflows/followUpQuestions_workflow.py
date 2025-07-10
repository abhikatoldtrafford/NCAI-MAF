from typing import Dict, Any, Optional
from NewsAgents.business.interfaces.workflow_interface import WorkflowInterface
from NewsAgents.infrastructure.llm.agent_manager import AgentManager
from NewsAgents.application.services.prompt_service import PromptService
from langchain_core.output_parsers import JsonOutputParser
from NewsAgents.infrastructure.llm.llm_base import LLMModel


def clean_up_generated_text(text:str) -> str:
    return text.replace("$", "$")

class FollowUpQuestionsWorkflow(WorkflowInterface[str, str]):
    def __init__(self, agent_manager: AgentManager, prompt_service: PromptService, llm: LLMModel):
        self.agent_manager = agent_manager
        self.response = {
            "follow_up_questions": []
        }
        self.status = {"state": "idle"}
        self.prompt_service = prompt_service
        self.llm = llm

    def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """
        Execute the follow-up questions workflow.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
        Returns:
            The generated response
        """
        self.status = {"state": "processing"}

        try:
            print("Executing FollowUpQuestionsWorkflow...")
            if parameters is None:
                parameters = {}
            history = parameters.get("history", None)
            sql_data = parameters.get("sql_data", {})
            news_data = parameters.get("news_data", {})
            
            # prompts
            sys_tpl, user_tpl = self.prompt_service.get_prompts(
                sys_prompt_id="QG1TF6ALFZ",
                sys_prompt_version="1",
                user_prompt_id="4Z7NC2WI9Z",
                user_prompt_version="1",
            )
            system_prompt = sys_tpl
            user_prompt = user_tpl.format(
                conversation=history, dataframe=sql_data, news_data=news_data, question=query
            )
            
            follow_ups_output = self.agent_manager.generate_response(self.llm, user_prompt, {"system_prompt": system_prompt, "parser": JsonOutputParser()})
            self.status = {"state": "completed"}
            if 'followUpQuestions' in follow_ups_output:
                self.response["follow_up_questions"] = follow_ups_output['followUpQuestions']
            else:
                self.response["follow_up_questions"] = follow_ups_output
            print(f"Follow-up questions generated: {follow_ups_output['followUpQuestions']}")
            
            return self.response
        
        except Exception as e:
            self.status = {"state": "failed", "error": str(e)}
            return f"Error processing prompt: {str(e)}"