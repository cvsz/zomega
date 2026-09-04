import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        if "zomega" not in os.environ.get("DATABASE_URL", ""):
            return (init_settings, dotenv_settings, env_settings, file_secret_settings)
        return (init_settings, env_settings, dotenv_settings, file_secret_settings)


    zomega_env: str = "production"
    zomega_host: str = "127.0.0.1"
    zomega_port: int = 8000
    zomega_public_url: str

    database_url: str
    redis_url: str

    zomega_api_key_pepper: str
    zomega_admin_token: str
    zomega_default_plan: str = "pro"
    zomega_rate_limit_per_minute: int = 60
    zomega_max_run_credits: int = 5000

    openai_api_key: str
    openai_model: str = "gpt-5.6-sol"
    openai_store: bool = False

    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_credits_1000: str
    stripe_price_credits_5000: str
    stripe_price_credits_20000: str

    zomega_log_level: str = "INFO"

settings = Settings()
