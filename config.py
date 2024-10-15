import os

DEFAULT_CONFIG = {
    'API_BASE_URL': 'http://localhost:11434',
    'DEFAULT_MODEL': 'qwen2.5:7b',
    'LOG_LEVEL': 'INFO',
}

CONFIG = {
    key: os.environ.get(key, DEFAULT_CONFIG[key])
    for key in DEFAULT_CONFIG
}

API_BASE_URL = CONFIG['API_BASE_URL']
DEFAULT_MODEL = CONFIG['DEFAULT_MODEL']
LOG_LEVEL = CONFIG['LOG_LEVEL']
