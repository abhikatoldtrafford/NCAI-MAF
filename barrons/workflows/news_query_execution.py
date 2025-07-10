from typing import Dict, Any, Optional
from NewsAgents.business.interfaces.workflow_interface import WorkflowInterface
from NewsAgents.infrastructure.llm.agent_manager import AgentManager
from NewsAgents.application.services.prompt_service import PromptService
from NewsAgents.infrastructure.data.plugins.SDL_plugin import SDLQueryPlugin
from NewsAgents.services.aws_credentials import AWSCredentialsProvider
from NewsAgents.infrastructure.llm.llm_base import LLMModel

from langchain_core.output_parsers import JsonOutputParser

import os
import json
import re
import pprint


class NewsQueryWorkflow(WorkflowInterface[str, str]):
    """
    A workflow that queries news articles based on LLM-generated search terms.
    """

    def __init__(self, agent_manager: AgentManager, prompt_service: PromptService, llm: LLMModel, aws_creds: Dict[str, Any]):
        """
        Initialize the news query workflow.

        Args:
            agent_manager: Manager for LLM agent interactions
        """
        self.agent_manager = agent_manager
        self.prompt_service = prompt_service
        if aws_creds is None or len(aws_creds.keys()) == 0:
            aws_credential_provider = AWSCredentialsProvider()
            aws_creds = aws_credential_provider.get_credentials()
        self.aws_creds = aws_creds
        self.response = {"search_terms": "", "article_ids": [], "query_result": []}
        self.llm = llm
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
            # Synchronous part: LLM query generation
            search_terms = self._generate_search_terms(query, sql_data, history)
            self.response["search_terms"] = search_terms

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

    def analyze_news_data(self, query:str, articles:list, history:list):
        system_prompt, user_prompt = self.prompt_service.get_prompts(
            sys_prompt_id="6P1SQR1VJU",
            sys_prompt_version="8",
            user_prompt_id="N48XNMPJCG",
            user_prompt_version="1",
        )
        user_prompt = user_prompt.format(articles=articles, conversation=history, question=query)

        # Generate response using the agent manager (synchronous)
        response = self.agent_manager.generate_response(self.llm, user_prompt, {"system_prompt": system_prompt, "parser": JsonOutputParser()})
        # Try to extract search terms from the response
        search_terms = response["insights"]
        # pprint.pp(f"Generated search terms: {search_terms}")
        return search_terms

    def _generate_search_terms(self, query: str, sql_data, history: list) -> str:
        """
        Generate search terms using the LLM (synchronous operation).

        Args:
            prompt_in: The user prompt
            system_prompt: Optional system prompt

        Returns:
            Generated search terms
        """
        # Create LLM prompt for search term generation
        system_prompt, user_prompt = self.prompt_service.get_prompts(
            sys_prompt_id="0BU3YTAH0T",
            sys_prompt_version="1",
            user_prompt_id="UR0U33XL3K",
            user_prompt_version="1",
        )
        user_prompt = user_prompt.format(question=query, conversation=history, curr_table=sql_data)

        # Generate response using the agent manager (synchronous)
        response = self.agent_manager.generate_response(self.llm, user_prompt, {"system_prompt": system_prompt, "parser": JsonOutputParser()})
        # Try to extract search terms from the response
        search_terms = response["news_topic"]
        # pprint.pp(f"Generated search terms: {search_terms}")
        return search_terms

    async def _fetch_articles(self, search_terms: str) -> list:
        """
        Fetch articles using the SDL GraphQL API (asynchronous operation).

        Args:
            search_terms: Search terms to use for the query

        Returns:
            List of article data
        """
        SDL_endpoint = self.aws_creds["SDL_URL"]
        SDL_okta_issuer = self.aws_creds["OKTA_SDL_AUTH_ISSUER"]
        SDL_okta_client_secret = self.aws_creds["OKTA_SDL_AUTH_CLIENT_SECRET"]
        SDL_okta_client_ID = self.aws_creds["OKTA_SDL_AUTH_CLIENT_ID"]
        logging = None

        # Initialize SDL plugin
        SDL = SDLQueryPlugin(
            SDL_endpoint=SDL_endpoint,
            SDL_okta_issuer=SDL_okta_issuer,
            SDL_okta_client_ID=SDL_okta_client_ID,
            SDL_okta_client_secret=SDL_okta_client_secret,
            logging=logging,
        )

        # Authenticate with Okta
        SDL.get_okta_token()

        # First GraphQL query to get article IDs
        first_GQL_query = """
            query Query($keyword: String!, $publication: String, $count: Int) {
                articlesByKeyword(keyword: $keyword, publication: $publication, count: $count) {
                    ... on Article {
                        upstreamOriginId
                    }
                }
            }
            """
        first_gql_variables = {"keyword": search_terms, "publication": "Barrons", "count": 5}

        # Execute first query
        articleids_unparsed = await SDL.process_query(first_GQL_query, variables=first_gql_variables)
        # pprint.pp(f"First query response - Articles Unparsed: {articleids_unparsed}")

        # Check if we got valid results
        if (
            not articleids_unparsed
            or not articleids_unparsed.get("articlesByKeyword")
            or len(articleids_unparsed["articlesByKeyword"]) == 0
        ):
            return []

        # Extract article IDs
        if "upstreamOriginId" in articleids_unparsed["articlesByKeyword"][0]:
            ids = [article["upstreamOriginId"] for article in articleids_unparsed["articlesByKeyword"]]
        else:
            return []

        pprint.pp(f"Found article IDs: {ids}\n")
        self.response["article_ids"] = ids

        # Second GraphQL query to get article details
        second_gql_query = """ 
            query ArticlesByIds($ids: [String!]!) {
            articlesByIds(ids: $ids) {
                ... on Article {
                __typename
                id
                sourceUrl
                seoId
                originId
                publishedDateTimeUtc
                authors {
                    id
                    text
                }
                sectionName
                sectionType
                flattenedSummary {
                    image {
                    id
                    altImages {
                        height
                        name
                        sizeCode
                        url
                        width
                    }
                    caption
                    credit
                    height
                    width
                    mediaType
                    name
                    properties {
                        responsive {
                        layout
                        }
                        scope {
                        scope
                        }
                        location
                        imPhotoId
                        softCrop
                    }
                    reuseType
                    sizeCode
                    slug
                    src {
                        imageId
                        path
                        baseUrl
                        size
                    }
                    type
                    combinedCompactUrl
                    combinedRegularUrl
                    }
                    video {
                    id
                    mediaType
                    caption
                    name
                    properties {
                        suppressHeadline
                    }
                    slug
                    api
                    type
                    videoContent {
                        atmo
                        description
                        numericDuration
                        format
                        formattedDuration
                        gptCustParams
                        guid
                        hlsCaptions
                        hlsNoCaptions
                        iso8601CreationDate
                        linkShortUrl
                        name
                        sectionName
                        thumbnailUrl
                        videoAspectRatio
                    }
                    }
                    inset {
                    type
                    insetType
                    properties {
                        bigTopHeroId
                        imageCaption
                        imageCredit
                        dataType
                        flashline
                        headlinePlacement
                        headlineIsWhite
                        url
                        urlSmall
                        urlLarge
                        newsletterName
                        newsletterId
                    }
                    slideshowInsetContent {
                        paragraph {
                        type
                        hasDropCap
                        }
                    }
                    }
                    flashline {
                    text
                    context {
                        type
                        start
                        length
                    }
                    }
                    headline {
                    text
                    }
                    description {
                    type
                    hasDropCap
                    content {
                        text
                    }
                    }
                    list {
                    type
                    ordered
                    items {
                        type
                        text
                    }
                    }
                    variant
                }
                articleBody {
                    type
                    ... on ParagraphArticleBody {
                    textAndDecorations {
                        flattened {
                        text
                        }
                    }
                    }
                }
                }
                ... on ArticleNotFoundError {
                __typename
                message
                id
                }
                ... on ArticleInternalError {
                __typename
                message
                }
            }
            }   
            """
        second_gql_vars = {"ids": ids}

        # Execute second query
        articles_unparsed = await SDL.process_query(second_gql_query, variables=second_gql_vars)
        # pprint.pp(f"\n***Second query response - Articles Unparsed: {articles_unparsed.get("articlesByIds")}\n")
        # self.response["articles_unparsed"] = articles_unparsed

        # Check if we got valid results
        if not articles_unparsed or not articles_unparsed.get("articlesByIds"):
            return []

        # Process articles
        articles = articles_unparsed["articlesByIds"]
        cleaned_articles = []
        for article in articles:
            url = article.get("sourceUrl", "")
            paragraphs = []
            for section in article["articleBody"]:
                if section["type"] == "paragraph" and section.get("textAndDecorations"):
                    flattened = section["textAndDecorations"].get("flattened", {})
                    text = flattened.get("text", "")
                    paragraphs.append(text)
            article_text = " ".join(paragraphs)
            cleaned_articles.append({"url": url, "content": article_text})

        pprint.pp("Second qeury Execution Complete")
        return cleaned_articles

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the workflow.

        Returns:
            The workflow status
        """
        return self.status