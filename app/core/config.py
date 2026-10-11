import os
from dotenv import load_dotenv

load_dotenv()  # reads .env file and loads it into environment variables

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
APP_ENV = os.getenv("APP_ENV", "development")