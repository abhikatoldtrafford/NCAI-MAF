from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from gql.transport.aiohttp import AIOHTTPTransport
from gql import Client, gql
from infrastructure.data.plugins.plugin_interface import DataPluginInterface
from infrastructure.data.plugin_manager import PluginManager
from graphql import (
    build_schema,
    build_client_schema,
    parse,
    validate,
    graphql_sync,
)

###
### This plugin is used to process SDL queries. A user is required to have proper authentication permissions for the SDL. 
### Keys required: SDL OKTA AUTH ISSUER LINK, SDL OKTA AUTH CLIENT ID, SDL OKTA AUTH CLIENT SECRET
### These keys can be aquired by reaching out to the SDL team and requesting access to the SDL prod API.
### The Tanager Key service is for experimental use, and will not work with this plugin.
###

### DELETE LATER: For Barron's team, this plugin is going to be used after the keywords are extracted from the prompt in an outer layer. 

class SDLQueryPlugin(DataPluginInterface):
    def __init__(self, SDL_endpoint: str, SDL_okta_issuer:str, SDL_okta_client_ID: str, SDL_okta_client_secret:str, logging: Any):
        self.logging = logging
        self.SDL_endpoint = SDL_endpoint
        self.okta_auth_token = Optional[str]
        self.SDL_okta_client_ID = SDL_okta_client_ID
        self.SDL_okta_client_secret = SDL_okta_client_secret
        self.SDL_okta_issuer_url = f"{SDL_okta_issuer}/v1/token"
        self.SDL_headers = Dict[str, str]
        self.plugin_manager = PluginManager()
        

    def update_headers(self):
        if not self.okta_auth_token:
            raise ValueError("Okta Token wasn't able to be retrieved from the authentication process. Please check your credentials.")
        self.sdl_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15',
            "apollographql-client-name": "studio-explorer",
            "Authorization": f"Bearer {self.okta_auth_token}",
            "Content-Type": "application/json",
        }

    def get_okta_token(self):
        """
        Retrieves an Okta token using the client credentials grant.
        Updates the internal token and headers.
        """
        import base64
        import requests
        print(self.SDL_okta_client_ID, self.SDL_okta_client_secret, self.SDL_okta_issuer_url)

        encoded_creds = base64.b64encode(f"{self.SDL_okta_client_ID}:{self.SDL_okta_client_secret}".encode("utf-8")).decode("utf-8")
        SDL_okta_data = {
                "grant_type": "client_credentials",
                "scope": "microservice"
            }
        SDL_okta_headers = {
                "Authorization": f"Basic {encoded_creds}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        response = requests.post(self.SDL_okta_issuer_url, headers=SDL_okta_headers, data=SDL_okta_data)
        response.raise_for_status()
        token_data = response.json()
        token = token_data["access_token"]
        self.okta_auth_token = token
        self.update_headers()
        return token


    async def process_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes the given GraphQL query using the current authentication token and endpoint.
        :param query: A string representing the GraphQL query.
        :param variables: A dictionary of variables for the query (optional).
        :return: A dictionary containing the response from the SDL endpoint.
        """
        if not self.okta_auth_token:
            raise ValueError("Okta token is not set. Please call get_okta_token() first.")
        async with Client(
            transport=AIOHTTPTransport(url=self.SDL_endpoint, headers=self.sdl_headers),
            fetch_schema_from_transport=False,
        ) as session:
            gql_query = gql(query)
            response =  await session.execute(gql_query, variable_values=variables)
        return response



    def validate_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validates the given GraphQL query.
        :param query: A string representing the GraphQL query.
        :param variables: A dictionary of variables for the query (optional).
        :return: True if the query is valid, False otherwise.
        """
        def load_schema_from_graphql_file():
            with open("infrastructure/data/plugins/DJ_Shared_Data_Schema.graphql", "r") as schema_file:
                schema = schema_file.read()
            return build_schema(schema)
        schema = load_schema_from_graphql_file()

        try:
            query_ast = parse(query) #Checking the query
        except Exception as parse_err: 
            self.logging.error(f"Error parsing query: {parse_err}")
            return False
        validation_errors = validate(schema, query_ast) #checking the query
        result = graphql_sync(schema, query_ast, variable_values=variables) #checking the query and variables
        if result.errors:
            for error in result.errors:
                print("Error: ", error)
            return False
        if validation_errors:
            for error in validation_errors:
                print("Error: ", error)
            return False
        
        return True

    def get_capabilities(self) -> Dict[str, Any]:  
        return {
            "name": "SDL Query Plugin",
            "description": "Plugin for processing SDL queries",
            "capabilities": ["get_okta_token", "process_query", "validate_query"]
        }


# Usage Example:
# if __name__ == "__main__":
#     # These would be in env vars
#     SDL_endpoint = "https://sdl.example.com/graphql"
#     SDL_okta_issuer = "https://okta.example.com/oauth2/default"
#     SDL_okta_client_ID = "YOUR_CLIENT_ID"
#     SDL_okta_client_secret = "YOUR_CLIENT_SECRET"
#     logging = None  

#     #Initializing the SDL plugin
#     SDL = SDLQueryPlugin(
#         SDL_endpoint=SDL_endpoint,
#         SDL_okta_issuer=SDL_okta_issuer,
#         SDL_okta_client_ID=SDL_okta_client_ID,
#         SDL_okta_client_secret=SDL_okta_client_secret,
#         logging=logging
#     )

#     # Retrieve a fresh Okta token and update headers
#     okta_token = SDL.get_okta_token()
#     print("Okta Token:", okta_token)

#     # Defining the first GraphQL query and its variables in Barron's formatting
#     first_GQL_query = """
#     query GetArticleIDs {
#       articles {
#         id
#       }
#     }
#     """
#.    first_gql_variables = {
#            "keyword": keyword_phrase,   #Derived from a LLM step prior to this. The LLM step would take in the user query, the table and the chat history.
#            "publication": "Barrons",
#            "count": 5
#            }
#     articleids_unparsed = SDL.process_query(first_GQL_query, variables=first_gql_variables) #I'm leaving it to the business logic to decide how to handle the parse returned data.

#     # Define a second GraphQL query and variables (if needed)
#     secondGQLquery = """
#     query GetArticles($ids: [ID!]!) {
#       articles(ids: $ids) {
#         id
#         title
#         content
#       }
#     }
#     """
#      second_gql_variables = {
#              "ids": ids_list
#           }
#     # Example: using the IDs from the first query as variables for the second
#     articles = SDL.process_query(secondGQLquery, variables=second_gql_variables)
#     print("Articles:", articles) #Again to clean up the data I'm leaving it to the business logic. 
