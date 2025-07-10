from enum import Enum
from typing import Union

class LLMModelTypes(Enum):
    ANTHROPIC_BEDROCK: str = "Anthropic Bedrock"
    ANTHROPIC: str = "Anthropic"
    GPT4O: str = "GPT4o"
    GEMINI: str = "Gemini"

class SpeechModelTypes(Enum):
    ANTHROPIC_BEDROCK: str = "Anthropic Bedrock"

class VisionModelTypes(Enum):
    ANTHROPIC_BEDROCK: str = "Anthropic Bedrock"

class VisionModelActions(Enum):
    GENERATION: str = "Generation"
    CLASSIFICATION: str = "Classification"
    SUMMARIZATION: str = "Image Summarization"
    DETECTION: str = "Object Detection/Instance Segmentation"

class SpeechModelActions(Enum):
    GENERATION: str = "Generation"
    DETECTION: str = "Detection"
    SUMMARIZATION: str = "Speech Summarization"


class LLMConfig:
    def __init__(self, model_type: LLMModelTypes = LLMModelTypes.ANTHROPIC_BEDROCK, temperature: float = 0.7, max_tokens: int = 2048, top_p: float = 0.1, top_k: int = 250) -> None:
        # model name
        self.model_type: LLMModelTypes = model_type
        # temperature
        self.temperature: float = temperature
        # max token
        self.max_tokens: int = max_tokens
        # top p
        self.top_p: float = top_p
        # top k
        self.top_k: int = top_k

class VisionConfig:
    def __init__(self, img_size: tuple = (256, 256, 256), model_type: VisionModelTypes = VisionModelTypes.ANTHROPIC_BEDROCK, task: VisionModelActions = VisionModelActions.GENERATION, threshold: float = 0.5, model_size: Union[int, str] = "small", validation_method: Union[str, callable] = "iou") -> None:
        self.img_size: tuple = img_size
        # model name
        self.model_type: VisionModelTypes = model_type
        self.task = task
        # threshold
        self.threshold: float = threshold
        # model_size
        self.model_size: Union[int, str] = model_size
        # top p
        self.validation_method: Union[str, callable] = validation_method

class SpeechConfig:
    def __init__(self, model_type: SpeechModelTypes = SpeechModelTypes.ANTHROPIC_BEDROCK, task: SpeechModelActions = SpeechModelActions.GENERATION, threshold: float = 0.5, model_size: Union[int, str] = "small", validation_method: Union[str, callable] = "cross_entropy") -> None:
        # model name
        self.model_type: SpeechModelTypes = model_type
        self.task = task
        # threshold
        self.threshold: float = threshold
        # model_size
        self.model_size: Union[int, str] = model_size
        # top p
        self.validation_method: Union[str, callable] = validation_method