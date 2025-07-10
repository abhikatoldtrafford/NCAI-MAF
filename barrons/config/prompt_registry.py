"""
Business-level registry for prompts.

Each prompt obj must contain an id and version for both its user and system prompts.
"""


class BasePrompts:
    system_prompt_id: str
    system_prompt_version: str
    user_prompt_id: str
    user_prompt_version: str

    @classmethod
    def get_system_prompt_info(cls):
        return cls.system_prompt_id, cls.system_prompt_version

    @classmethod
    def get_user_prompt_info(cls):
        return cls.user_prompt_id, cls.user_prompt_version

    @classmethod
    def get_all_prompt_info(cls):
        return (cls.system_prompt_id, cls.system_prompt_version, cls.user_prompt_id, cls.user_prompt_version)


class StockDBQueryPrompts(BasePrompts):
    system_prompt_id = "RT94K576N5"
    system_prompt_version = "3"
    user_prompt_id = "MRUK3G8TQW"
    user_prompt_version = "2"


class StockDataExplainerPrompts(BasePrompts):
    system_prompt_id = "BDCFG0GF45"
    system_prompt_version = "5"
    user_prompt_id = "2SX9C1PLOK"
    user_prompt_version = "1"


class NewsQuerySearchTermsPrompts(BasePrompts):
    system_prompt_id = "0BU3YTAH0T"
    system_prompt_version = "1"
    user_prompt_id = "UR0U33XL3K"
    user_prompt_version = "2"


class NewsQueryAnalysisPrompts(BasePrompts):
    system_prompt_id = "6P1SQR1VJU"
    system_prompt_version = "13"
    user_prompt_id = "N48XNMPJCG"
    user_prompt_version = "2"


class FollowUpQuestionsPrompts(BasePrompts):
    system_prompt_id = "QG1TF6ALFZ"
    system_prompt_version = "1"
    user_prompt_id = "4Z7NC2WI9Z"
    user_prompt_version = "2"
