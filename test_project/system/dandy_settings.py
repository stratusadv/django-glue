import os

from pathlib import Path


ALLOW_DEBUG_RECORDING = True
BASE_PATH = Path.resolve(Path(__file__)).parent.parent
DEFAULT_LLM_PROMPT_RETRY_COUNT: int = 2


LLM_CONFIGS = {
    'DEFAULT': {
        'TYPE': 'ollama',
        'HOST': os.getenv("OLLAMA_HOST"),
        'PORT': int(os.getenv("OLLAMA_PORT", 11434)),
        'API_KEY': os.getenv("OLLAMA_API_KEY"),
        'MODEL': 'qwen2.5-coder:14b-instruct-q4_K_M',
        'TEMPERATURE': 0.0,
        'MAX_INPUT_TOKENS': 16000,
        'MAX_OUTPUT_TOKENS': 16000,
    },
    'SEEDING_LLM_BOT': {
        'TYPE': 'ollama',
        'HOST': os.getenv("OLLAMA_HOST"),
        'PORT': int(os.getenv("OLLAMA_PORT", 11434)),
        'API_KEY': os.getenv("OLLAMA_API_KEY"),
        'MODEL': 'llama3.1:8b-instruct-q4_K_M',
        'TEMPERATURE': 0.0,
        'MAX_INPUT_TOKENS': 16000,
        'MAX_OUTPUT_TOKENS': 16000,
    },
    'QWEN_2_5_CODER_14B': {
        'TYPE': 'ollama',
        'HOST': os.getenv("OLLAMA_HOST"),
        'PORT': int(os.getenv("OLLAMA_PORT", 11434)),
        'API_KEY': os.getenv("OLLAMA_API_KEY"),
        'MODEL': 'qwen2.5-coder:14b-instruct-q4_K_M',
        'TEMPERATURE': 0.0,
        'MAX_INPUT_TOKENS': 16000,
        'MAX_OUTPUT_TOKENS': 16000,
    },
    'PYTHON_MODULE': {
        'TYPE': 'ollama',
        'HOST': os.getenv("OLLAMA_HOST"),
        'PORT': int(os.getenv("OLLAMA_PORT", 11434)),
        'API_KEY': os.getenv("OLLAMA_API_KEY"),
        'MODEL': 'qwen3-coder',
        'TEMPERATURE': 0.3,
        'MAX_INPUT_TOKENS': 16000,
        'MAX_OUTPUT_TOKENS': 16000,
    },
}
