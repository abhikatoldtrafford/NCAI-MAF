from typing import Dict, Any, List
import logging
from NewsAgents.infrastructure import SDLQueryPlugin
from agent_workflow.providers import FunctionTool, Tool


class FetchArticles(Tool):
    """
    Fetch articles using the SDL GraphQL API.
    """

    # GraphQL queries
    _FIRST_QUERY = """
    query Query($keyword: String!, $publication: String, $count: Int) {
        articlesByKeyword(keyword: $keyword, publication: $publication, count: $count) {
            ... on Article {
                upstreamOriginId
            }
        }
    }
    """
    _SECOND_QUERY = """ 
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

    def __init__(self, aws_creds: Dict[str, Any]):
        """
        Args:
            aws_creds: AWS credentials.
        """
        self.logger = logging.getLogger(__name__)
        creds = aws_creds
        self.sdl = SDLQueryPlugin(
            SDL_endpoint=creds["SDL_URL"],
            SDL_okta_issuer=creds["OKTA_SDL_AUTH_ISSUER"],
            SDL_okta_client_ID=creds["OKTA_SDL_AUTH_CLIENT_ID"],
            SDL_okta_client_secret=creds["OKTA_SDL_AUTH_CLIENT_SECRET"],
            logging=self.logger,
        )
        self.sdl.get_okta_token()

    async def execute(self, search_terms: str) -> Dict[str, List]:
        # First GraphQL query to get article IDs
        first_gql_variables = {"keyword": search_terms, "publication": "Barrons", "count": 5}
        articleids_unparsed = await self.sdl.process_query(self._FIRST_QUERY, variables=first_gql_variables)

        # Check if we got valid results
        if (
            not articleids_unparsed
            or not articleids_unparsed.get("articlesByKeyword")
            or len(articleids_unparsed["articlesByKeyword"]) == 0
        ):
            return {"articles": []}

        # Extract article IDs
        if "upstreamOriginId" in articleids_unparsed["articlesByKeyword"][0]:
            ids = [article["upstreamOriginId"] for article in articleids_unparsed["articlesByKeyword"]]
        else:
            return {"articles": []}
        self.logger.info(f"Found article IDs: {ids}")

        # Second GraphQL query to get article details
        second_gql_vars = {"ids": ids}
        articles_unparsed = await self.sdl.process_query(self._SECOND_QUERY, variables=second_gql_vars)

        # Check if we got valid results
        if not articles_unparsed or not articles_unparsed.get("articlesByIds"):
            return {"articles": []}
        self.logger.info("Second qeury execution Complete")

        # Process articles
        articles = articles_unparsed["articlesByIds"]
        urls, texts = [], []
        for art in articles:
            urls.append(art.get("sourceUrl", ""))
            paragraphs = [
                sec["textAndDecorations"]["flattened"]["text"]
                for sec in art.get("articleBody", [])
                if sec.get("type") == "paragraph" and sec.get("textAndDecorations")
            ]
            texts.append(" ".join(paragraphs))

        return {"url": urls, "content": texts}

    # All properties must align with the corresponding tool in YAML
    @property
    def name(self) -> str:
        return "fetch_articles"

    @property
    def description(self) -> str:
        return "Uses news search terms to generate a GraphQL query for the SDL."

    @property
    def type(self) -> str:
        return "function"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"search_terms": {"type": "string"}},
            "required": ["search_terms"],
        }

    @property
    def asFunctionalTool(self) -> FunctionTool:
        return FunctionTool(name=self.name, description=self.description, func=self.execute)
