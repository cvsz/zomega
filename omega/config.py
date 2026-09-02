from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    omega_env: str = "production"
    omega_host: str = "0.0.0.0"
    omega_port: int = 8000
    omega_public_url: str

    database_url: str
    redis_url: str

    omega_api_key_pepper: str
    omega_admin_token: str
    omega_default_plan: str = "pro"
    omega_rate_limit_per_minute: int = 60
    omega_max_run_credits: int = 5000

    openai_api_key: str
    openai_model: str = "gpt-5.6-sol"
    openai_store: bool = False

    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_currency: str = "usd"
    stripe_credit_unit_amount: int = 10

    omega_log_level: str = "INFO"

settings = Settings()
