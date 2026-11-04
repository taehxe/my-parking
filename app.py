
import gradio as gr
import pandas as pd
import math
import os
import unicodedata

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

target_name = unicodedata.normalize(
    "NFC", "전국주차장정보표준데이터.csv"
)

CSV_PATH = None

for filename in os.listdir(BASE_DIR):
    normalized_name = unicodedata.normalize("NFC", filename)

    if normalized_name == target_name:
        CSV_PATH = os.path.join(BASE_DIR, filename)
        break

if CSV_PATH is None:
    raise FileNotFoundError(
        f"CSV 파일을 찾을 수 없습니다. 파일 목록: {os.listdir(BASE_DIR)}"
    )

df = pd.read_csv(CSV_PATH, encoding="cp949")

columns = [
    "주차장명",
    "주차장유형",
    "소재지도로명주소",
    "주차구획수",
    "운영요일",
    "주차기본요금",
    "주차기본시간",
    "추가단위시간",
    "추가단위요금",
    "전화번호"
]

parking = df[columns].copy()

parking = parking.dropna(
    subset=["주차장명", "소재지도로명주소"]
)

parking = parking.drop_duplicates(
    subset=["주차장명", "소재지도로명주소"]
)

numeric_columns = [
    "주차구획수",
    "주차기본요금",
    "주차기본시간",
    "추가단위시간",
    "추가단위요금"
]

for col in numeric_columns:
    parking[col] = pd.to_numeric(
        parking[col], errors="coerce"
    )

parking["주차장유형"] = parking["주차장유형"].fillna("정보 없음")
parking["운영요일"] = parking["운영요일"].fillna("정보 없음")
parking["전화번호"] = parking["전화번호"].fillna("정보 없음")


def calculate_fee(row, use_time):
    basic_fee = row["주차기본요금"]
    basic_time = row["주차기본시간"]
    add_time = row["추가단위시간"]
    add_fee = row["추가단위요금"]

    if pd.isna(basic_fee) or pd.isna(basic_time):
        return None

    if use_time <= basic_time:
        return int(basic_fee)

    if pd.isna(add_time) or pd.isna(add_fee) or add_time <= 0:
        return None

    extra_count = math.ceil(
        (use_time - basic_time) / add_time
    )

    return int(basic_fee + extra_count * add_fee)


def search_parking(
    region,
    max_fee,
    min_spaces,
    parking_type,
    day,
    use_time
):
    result = parking.copy()

    if region and region.strip():
        result = result[
            result["소재지도로명주소"].str.contains(
                region.strip(), na=False
            )
        ]

    if max_fee is not None:
        result = result[
            result["주차기본요금"].isna()
            | (result["주차기본요금"] <= max_fee)
        ]

    if min_spaces is not None:
        result = result[
            result["주차구획수"] >= min_spaces
        ]

    if parking_type != "전체":
        result = result[
            result["주차장유형"] == parking_type
        ]

    if day != "전체":
        result = result[
            result["운영요일"].str.contains(day, na=False)
        ]

    if result.empty:
        return result

    result = result.copy()

    result["예상주차요금"] = result.apply(
        lambda row: calculate_fee(row, use_time),
        axis=1
    )

    result = result.sort_values(
        by="예상주차요금",
        ascending=True,
        na_position="last"
    )

    result["예상주차요금"] = result["예상주차요금"].apply(
        lambda x: f"{int(x):,}원" if pd.notna(x) else "요금 정보 부족"
    )

    return result


def run_search(
    region,
    max_fee,
    min_spaces,
    parking_type,
    day,
    use_time
):
    result = search_parking(
        region,
        max_fee,
        min_spaces,
        parking_type,
        day,
        use_time
    )

    if result.empty:
        return result, None

    download_path = os.path.join(
        BASE_DIR, "parking_search_result.csv"
    )

    result.to_csv(
        download_path,
        index=False,
        encoding="utf-8-sig"
    )

    return result, download_path


type_values = sorted(
    parking["주차장유형"].dropna().unique().tolist()
)

type_choices = ["전체"] + type_values


with gr.Blocks(
    theme=gr.themes.Soft(
        primary_hue="blue",
        neutral_hue="slate"
    ),
    title="MY PARKING"
) as demo:

    gr.Markdown(
        """
        # MY PARKING
        ### 내 조건에 맞는 주차장을 쉽고 빠르게 찾아보세요.
        """
    )

    with gr.Row():
        region = gr.Textbox(
            label="검색 지역",
            placeholder="",
            value=""
        )

        max_fee = gr.Number(
            label="최대 기본요금 (원)",
            value=None
        )

    with gr.Row():
        min_spaces = gr.Number(
            label="최소 주차 가능 대수",
            value=None,
            minimum=0,
        precision=0
        )

        parking_type = gr.Dropdown(
            choices=type_choices,
            label="주차장 유형",
            value="전체"
        )

    with gr.Row():
        day = gr.Dropdown(
            choices=["전체", "평일", "토요일", "공휴일"],
            label="이용 요일",
            value="전체"
        )

        use_time = gr.Number(
            label="예상 주차 시간 (분)",
            value=60,
            minimum=10,
            step=10,
        precision=0
        )

    search_button = gr.Button(
        "주차장 검색하기",
        variant="primary"
    )

    output = gr.Dataframe(
        label="검색 결과",
        interactive=False
    )

    download_file = gr.File(
        label="검색 결과 CSV 다운로드"
    )

    search_button.click(
        fn=run_search,
        inputs=[
            region,
            max_fee,
            min_spaces,
            parking_type,
            day,
            use_time
        ],
        outputs=[
            output,
            download_file
        ]
    )


demo.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("PORT", 10000))
)
