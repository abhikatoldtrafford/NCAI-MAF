from typing import Dict, Any, Optional
from NewsAgents.business.interfaces.workflow_interface import WorkflowInterface
from NewsAgents.infrastructure.llm.agent_manager import AgentManager
from NewsAgents.application import PromptService
from NewsAgents.infrastructure import FactivaPlugin
from NewsAgents.infrastructure import LLMModel
from langchain_core.output_parsers import JsonOutputParser
from NewsAgents.services.aws_credentials import AWSCredentialsProvider
import datetime


class NewsQueryWorkflowFactiva(WorkflowInterface[str, str]):
    """
    A workflow that queries news articles based on LLM-generated search terms.
    """

    def __init__(self, agent_manager: AgentManager, prompt_service: PromptService, llm: LLMModel):
        """
        Initialize the news query workflow.

        Args:
            agent_manager: Manager for LLM agent interactions
        """
        self.agent_manager = agent_manager
        self.prompt_service = prompt_service
        self.aws_credential_provider = AWSCredentialsProvider()
        aws_creds = self.aws_credential_provider.get_credentials()
        self.FACTIVA_CLIENTID = aws_creds["FACTIVA_CLIENTID"]
        self.FACTIVA_USERNAME = aws_creds["FACTIVA_USERNAME"]
        self.FACTIVA_PASSWORD = aws_creds["FACTIVA_PASSWORD"]
        self.response = {"search_terms": "", "article_ids": [], "query_result": []}
        self.llm = llm
        self.logging=None
        self.status = {"state": "idle"}

    async def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """
        Execute the news query workflow.

        Args:
            prompt_in: The user prompt
            system_prompt: Optional system prompt

        Returns:
            The generated response
        """
        self.status = {"state": "processing"}

        try:
            if parameters is None:
                parameters = {}
            history = parameters.get("history", None)
            sql_data = parameters.get("sql_data", {})
            sql_data_explanation = parameters.get("sql_data_explanation", {})
            # Synchronous part: LLM query generation
            search_terms = self._generate_search_terms(query=query, sql_data=sql_data, sql_data_explanation=sql_data_explanation, history=history)
            self.response["search_terms"] = search_terms
            print(f"Generated search terms: {search_terms}")
            search_terms = str(search_terms)
            # Early return if we couldn't generate search terms
            if not search_terms:
                self.status = {"state": "failed", "error": "Could not generate search terms"}
                return f"Error: Could not generate search terms from the prompt: {query}"
            
            articles = await self._fetch_articles(search_terms)
            response = self.analyze_news_data(query, articles, history)
            self.status = {"state": "completed"}
            return {"news_data_analysis": response}
        except Exception as e:
            self.status = {"state": "failed", "error": str(e)}
            return f"Error processing prompt: {str(e)}" 
    
    def _generate_search_terms(self, query: str, sql_data, sql_data_explanation:str, history: list) -> str:
        """
        Generate search terms using the LLM (synchronous operation).

        Args:
            prompt_in: The user prompt
            system_prompt: Optional system prompt

        Returns:
            Generated search terms
        """
        system_prompt, user_prompt = self.prompt_service.get_prompts(
            sys_prompt_id="C9U9L3NAAU",
            sys_prompt_version="5",
            user_prompt_id="0MW2OKHO3M",
            user_prompt_version="3",
        )
        user_prompt = str(user_prompt)
        system_prompt = str(system_prompt)
        print("THIS IS THE EXPLANATION OF STOCK DATA", sql_data_explanation)
        system_prompt = system_prompt.format(date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) 
        user_prompt = user_prompt.format(question=query, conversation=history, curr_table=sql_data, sql_data_explanation=sql_data_explanation)
        response = self.agent_manager.generate_response(self.llm, user_prompt, {"system_prompt": system_prompt, "parser": JsonOutputParser()})
        search_terms = response["news_topic"]
        return search_terms
    

    async def _fetch_articles(self, search_terms: str) -> list:
        """
        Fetch articles based on search terms.
        Args:
            search_terms: The generated search terms
            
        Returns:
            A list of fetched articles
        """
        # Initialize SDL plugin
        FACTIVA = FactivaPlugin(
            Factiva_CLIENTID= self.FACTIVA_CLIENTID,
            Factiva_USERNAME= self.FACTIVA_USERNAME,
            Factiva_PASSWORD= self.FACTIVA_PASSWORD,
            logging=self.logging,
        )
        FACTIVA.get_Factiva_auth()
        articles_unparsed = await FACTIVA.process_query(search_terms)
        return articles_unparsed

    def analyze_news_data(self, query:str, articles:list, history:list):
        system_prompt, user_prompt = self.prompt_service.get_prompts(
            sys_prompt_id="6P1SQR1VJU",
            sys_prompt_version="10",
            user_prompt_id="N48XNMPJCG",
            user_prompt_version="1",
        )
        user_prompt = user_prompt.format(articles=articles, conversation=history, question=query)
        system_prompt = system_prompt.format(date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        response = self.agent_manager.generate_response(self.llm, user_prompt, {"system_prompt": system_prompt, "parser": JsonOutputParser()})
        article_analysis = response["insights"]
        return article_analysis
    