import os

from pathlib import Path


ALLOW_DEBUG_RECORDING = True
BASE_PATH = Path.resolve(Path(__file__)).parent.parent
DEFAULT_LLM_PROMPT_RETRY_COUNT: int = 2


LLM_CONFIGS = {
    'DEFAULT': {
        'TYPE': 'openai',
        'HOST': os.getenv('AI_API_HOST'),
        'PORT': 443,
        'API_KEY': os.getenv('AI_API_KEY'),
        'MODEL': 'stratus.smart',
        'TEMPERATURE': 0.1,
        'MAX_INPUT_TOKENS': 32000,
        'MAX_OUTPUT_TOKENS': 32000,
    },
    'BASIC': {
        'MODEL': 'stratus.smart',
        'MAX_INPUT_TOKENS': 16000,
        'MAX_OUTPUT_TOKENS': 16000,
    },
    'ADVANCED': {
        'MODEL': 'stratus.smart',
        'TEMPERATURE': 0.3,
        'MAX_INPUT_TOKENS': 16000,
        'MAX_OUTPUT_TOKENS': 16000,
    },
    'COMPLEX': {
        'MODEL': 'stratus.smart',
        'MAX_INPUT_TOKENS': 16000,
        'MAX_OUTPUT_TOKENS': 16000,
    },
    'SEEDING_LLM_BOT': {
        'MODEL': 'stratus.smart',
        'TEMPERATURE': 0.0,
        'MAX_INPUT_TOKENS': 16000,
        'MAX_OUTPUT_TOKENS': 16000,
    },
    'PYTHON_MODULE': {
        'MODEL': 'stratus.smart',
        'TEMPERATURE': 0.3,
        'MAX_INPUT_TOKENS': 16000,
        'MAX_OUTPUT_TOKENS': 16000,
    },
    'QWEN_2_5_CODER_14B': {
        'MODEL': 'stratus.smart',
        'TEMPERATURE': 0.0,
        'MAX_INPUT_TOKENS': 16000,
        'MAX_OUTPUT_TOKENS': 16000,
    },
    'KNOWLEDGE_LLM_BOT': {
        'MODEL': 'stratus.smart',
        'TEMPERATURE': 0.3,
        'MAX_INPUT_TOKENS': 16000,
        'MAX_OUTPUT_TOKENS': 32000,
    },
}