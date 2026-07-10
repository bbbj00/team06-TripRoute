from app.rag.vector_store import ingest_city

# 숙박(32)/쇼핑(38) 데이터가 아예 없던 7개 도시
LODGING_SHOPPING_ONLY = ["속초", "경주", "여수", "서울"]

# 숙박/쇼핑도 없고 음식점(39)도 얇았던 도시
LODGING_SHOPPING_AND_FOOD = ["춘천", "전주", "인천"]


def main():
    for city in LODGING_SHOPPING_ONLY:
        print(f"=== {city}: 숙박/쇼핑 추가 수집 ===", flush=True)
        saved = ingest_city(city, num_of_rows=20, content_type_ids=["32", "38"])
        print(f"{city}: {len(saved)}건 신규 저장", flush=True)

    for city in LODGING_SHOPPING_AND_FOOD:
        print(f"=== {city}: 숙박/쇼핑/음식점 추가 수집 ===", flush=True)
        saved = ingest_city(city, num_of_rows=20, content_type_ids=["32", "38", "39"])
        print(f"{city}: {len(saved)}건 신규 저장", flush=True)


if __name__ == "__main__":
    main()
