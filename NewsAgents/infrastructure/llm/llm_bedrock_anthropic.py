# define a class for the Anthropic Bedrock LLM mode
import boto3
from langchain_core.prompts import ChatPromptTemplate
from langchain_aws.chat_models.bedrock import ChatBedrock

from NewsAgents.application.models.model_configs import LLMConfig
from NewsAgents.infrastructure.llm.llm_base import LLMModel
from typing import Optional

class AnthropicBedrockModel(LLMModel):

    """
    An implementation of the LLLModel interface for the Anthropic Bedrock LLM.
    """

    def __init__(self, project_name: str, langfuse_public_key: str, langfuse_secret_key: str, langfuse_host: str, aws_access_key: str, aws_secret_key: str, aws_region:str, model_configs: LLMConfig, model_id: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0", logging_session: Optional[str] = None, user_id: Optional[str] = None, trace_name: str = None):
        """
        Initialize the Anthropic Bedrock LLM model.

        Args:
            aws_access_key (str): The API key for accessing the Anthropic Bedrock API.
        """
        super().__init__(project_name, langfuse_public_key, langfuse_secret_key, langfuse_host, logging_session=logging_session, user_id=user_id, trace_name=trace_name)
        
        if not aws_access_key or not aws_secret_key or not aws_region:
            raise ValueError("AWS credentials not found, cannot initialize Anthropic Bedrock model")

        bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        if model_configs is None:
            max_tokens: int = 2048
            temperature: float = 0.0
            top_p: float = 0.9
            top_k: float = 250
        else:
            max_tokens: int = model_configs.max_tokens
            temperature: float = model_configs.temperature
            top_p: float = model_configs.top_p
            top_k: float = model_configs.top_k

        model_kwargs =  { 
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_k": top_k,
            "top_p": top_p,
            "stop_sequences": ["<EOR>"],
        }

        self.model = ChatBedrock(
            client=bedrock_runtime,
            model_id=model_id,
            model_kwargs=model_kwargs,
        )
        
    def generate(self, system_prompt: str, user_prompt: str, parser) -> str:
        """
        Generate text based on the given prompt.

        Args:
            system_prompt (str): The input prompt for text generation.
            user_prompt (str): The input prompt for text generation.
        Returns:
            str: The generated text.
        """
        #print(prompt_in)

        messages = [
            ("system", "{system_prompt}"),
            ("human", "{user_prompt}"),
        ]

        prompt = ChatPromptTemplate.from_messages(messages)
        
        if parser is not None:
            chain = prompt | self.model | parser
        else :
            chain = prompt | self.model 
        
        response = chain.invoke({"system_prompt": system_prompt,
                                 "user_prompt": user_prompt},
                                config={"callbacks": [self.langfuse_handler]})
        
        return response