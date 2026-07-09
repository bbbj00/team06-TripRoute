import os
from dotenv import load_dotenv


load_dotenv()


class Settings:
    UPSTAGE_API_KEY: str | None = os.getenv("UPSTAGE_API_KEY")

    TOUR_API_KEY: str | None = os.getenv("TOUR_API_KEY")
    RELATED_PLACE_API_KEY: str | None = os.getenv("RELATED_PLACE_API_KEY")
    KAKAO_MOBILITY_API_KEY: str | None = os.getenv("KAKAO_MOBILITY_API_KEY")

    SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: str | None = os.getenv("SUPABASE_KEY")

    LANGFUSE_PUBLIC_KEY: str | None = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY: str | None = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST: str | None = os.getenv(
        "LANGFUSE_HOST",
        "https://cloud.langfuse.com",
    )


settings = Settings()