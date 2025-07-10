import requests as r
from dotenv import load_dotenv
from typing import Dict, Any, List
from NewsAgents.infrastructure.data.plugins.plugin_interface import DataPluginInterface
from NewsAgents.infrastructure.data.plugin_manager import PluginManager
load_dotenv()

class FactivaPlugin(DataPluginInterface):
    def __init__(self, Factiva_CLIENTID: str, Factiva_USERNAME: str, Factiva_PASSWORD:str, logging: Any):
        self.Factiva_CLIENTID: str = Factiva_CLIENTID
        self.Factiva_USERNAME: str = Factiva_USERNAME
        self.Factiva_PASSWORD: str = Factiva_PASSWORD
        self.BEARER_TOKEN: str = None
        self.logging = logging
        self.API_URL = "https://api.dowjones.com/content/gen-ai/retrieve"
        self.AUTH_URL = "https://accounts.dowjones.com/oauth2/v1/token"
        self.HEADERS: Dict[str, str] = {}
        self.plugin_manager = PluginManager()


    def update_headers(self, bearer_token: str):
        return {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def get_Factiva_auth(self):
        bearer_token = None
        id_token_payload = {
            "client_id": self.Factiva_CLIENTID,
            "username": self.Factiva_USERNAME,
            "grant_type": "password",
            "connection": "service-account",
            "scope": "openid service_account_id",
            "password": self.Factiva_PASSWORD
        }

        token_id_resp = r.post(self.AUTH_URL, data=id_token_payload)

        if token_id_resp.status_code == 200:
            response_body = token_id_resp.json()
            id_token = response_body['id_token']
            access_token = response_body['access_token']

            bearer_token_payload = {
                "client_id": self.Factiva_CLIENTID,
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "connection": "service-account",
                "scope": "openid pib",
                "access_token": access_token,
                "assertion": id_token
            }

            jwt_token_resp = r.post(self.AUTH_URL, data=bearer_token_payload)

            if jwt_token_resp.status_code == 200:
                response_body = jwt_token_resp.json()
                bearer_token = response_body['access_token']

        self.HEADERS = self.update_headers(bearer_token)

        return bearer_token

    async def process_query(self, frapi_prompt: str):
        frapi_query = {
        "data": {
            "attributes": {
            "response_limit": 6,
            "query": {
                "search_filters": [
                {
                    "scope": "Source",
                    "value": "B",  
                }
                ],

                "value": frapi_prompt
            }
            },
            "id": "GenAIRetrievalExample",
            "type": "genai-content"
        }
        }
        factiva_response = r.post(self.API_URL, headers=self.HEADERS, json=frapi_query)
        responses_list = factiva_response.json()
        LLM_ready_responses = self.get_LLM_ready(responses_list["data"])

        return LLM_ready_responses
        
    def get_LLM_ready(self, article_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepares the article chunks for LLM processing.
        :param article_chunks: List of article chunks to be processed.
        :return: List of dictionaries containing the processed article chunks.
        """
        article_list = []
        for chunk in article_chunks:
            article = {
                "index": len(article_list) + 1,
                'url': f"https://dj.factiva.com/article?id=drn:archive.newsarticle.{str(chunk['meta']['original_doc_id']).strip()}",
                'source_name': str(chunk['meta']['source']['name']).strip(),
                'headline': str(chunk['attributes']['headline']['main']['text']).strip(),
                'publication_date': chunk['attributes']['publication_date'],
                'content': f"{str(chunk['attributes']['snippet']['content'][0]['text']).strip()} {str(chunk['attributes']['content'][0]['text']).strip()}"
            }
            article_list.append(article)
        return article_list
    
    def validate_query(self, query: str) -> bool:
        pass

    def get_capabilities(self) -> Dict[str, Any]:  
        return {
            "name": "Factiva Query Plugin",
            "description": "Plugin for processing Factiva queries",
            "capabilities": ["get_okta_token", "process_query", "validate_query"]
        }
