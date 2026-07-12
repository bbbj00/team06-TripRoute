import os
from dotenv import load_dotenv


load_dotenv()


class Settings:
    UPSTAGE_API_KEY: str | None = os.getenv("UPSTAGE_API_KEY")

    # data.go.kr 계정당 인증키가 1개라 TourAPI(15101578)와 연관 관광지 API(15128560)가 같은 키를 씀
    TOUR_API_KEY: str | None = os.getenv("TOUR_API_KEY")
    KAKAO_MOBILITY_API_KEY: str | None = os.getenv("KAKAO_MOBILITY_API_KEY")
    GOOGLE_PLACES_API_KEY: str | None = os.getenv("GOOGLE_PLACES_API_KEY")

    SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: str | None = os.getenv("SUPABASE_KEY")

    LANGFUSE_PUBLIC_KEY: str | None = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY: str | None = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST: str | None = os.getenv(
        "LANGFUSE_HOST",
        "https://cloud.langfuse.com",
    )


settings = Settings()