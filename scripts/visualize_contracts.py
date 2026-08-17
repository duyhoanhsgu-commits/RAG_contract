"""Interactive Streamlit dashboard for data/processed/contracts.jsonl.

Run from the project root:
    streamlit run scripts/visualize_contracts.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "contracts.jsonl"


@st.cache_data(show_spinner="Đang đọc dữ liệu hợp đồng...")
def load_contracts(path_string: str, modified_time: float) -> pd.DataFrame:
    """Load and validate the JSONL file into a DataFrame."""
    del modified_time  # Used only to invalidate Streamlit's cache after file changes.
    records: list[dict[str, object]] = []
    path = Path(path_string)

    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"JSON không hợp lệ tại dòng {line_number}: {error}") from error

    required_columns = {
        "contract_id",
        "filename",
        "contract_type",
        "part",
        "source_txt",
        "source_pdf",
        "text",
        "char_count",
    }
    missing_columns = required_columns.difference(records[0] if records else {})
    if missing_columns:
        raise ValueError(f"Thiếu các trường bắt buộc: {sorted(missing_columns)}")

    dataframe = pd.DataFrame.from_records(records)
    dataframe["char_count"] = pd.to_numeric(dataframe["char_count"], errors="coerce").fillna(0).astype(int)
    dataframe["word_count"] = dataframe["text"].fillna("").map(lambda text: len(str(text).split()))
    return dataframe


def filter_contracts(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Render sidebar filters and return matching contracts."""
    st.sidebar.header("Bộ lọc")
    selected_parts = st.sidebar.multiselect(
        "Part",
        sorted(dataframe["part"].dropna().unique()),
    )
    selected_types = st.sidebar.multiselect(
        "Loại hợp đồng",
        sorted(dataframe["contract_type"].dropna().unique()),
    )
    search_text = st.sidebar.text_input("Tìm theo tên hoặc nội dung").strip()

    filtered = dataframe
    if selected_parts:
        filtered = filtered[filtered["part"].isin(selected_parts)]
    if selected_types:
        filtered = filtered[filtered["contract_type"].isin(selected_types)]
    if search_text:
        search_mask = (
            filtered["filename"].str.contains(search_text, case=False, na=False, regex=False)
            | filtered["text"].str.contains(search_text, case=False, na=False, regex=False)
        )
        filtered = filtered[search_mask]

    return filtered


def render_overview(dataframe: pd.DataFrame) -> None:
    """Render headline metrics and aggregate charts."""
    total_characters = int(dataframe["char_count"].sum())
    average_characters = int(dataframe["char_count"].mean()) if not dataframe.empty else 0

    metric_columns = st.columns(4)
    metric_columns[0].metric("Hợp đồng", f"{len(dataframe):,}")
    metric_columns[1].metric("Loại hợp đồng", dataframe["contract_type"].nunique())
    metric_columns[2].metric("Tổng ký tự", f"{total_characters:,}")
    metric_columns[3].metric("Ký tự trung bình", f"{average_characters:,}")

    chart_columns = st.columns(2)
    with chart_columns[0]:
        st.subheader("Theo Part")
        part_counts = dataframe["part"].value_counts().rename_axis("Part").to_frame("Số hợp đồng")
        st.bar_chart(part_counts)

    with chart_columns[1]:
        st.subheader("Theo loại hợp đồng")
        type_counts = (
            dataframe["contract_type"]
            .value_counts()
            .rename_axis("Loại hợp đồng")
            .to_frame("Số hợp đồng")
        )
        st.bar_chart(type_counts)


def render_word_statistics(dataframe: pd.DataFrame) -> None:
    """Render word-count statistics, distribution, and length rankings."""
    st.subheader("Thống kê độ dài theo số từ")
    if dataframe.empty:
        st.info("Không có dữ liệu để tính thống kê số từ.")
        return

    word_counts = dataframe["word_count"]
    statistics = [
        ("Ít nhất", int(word_counts.min())),
        ("Nhiều nhất", int(word_counts.max())),
        ("Trung bình", float(word_counts.mean())),
        ("Median", float(word_counts.median())),
        ("P90", float(word_counts.quantile(0.90))),
        ("P95", float(word_counts.quantile(0.95))),
    ]
    metric_columns = st.columns(6)
    for column, (label, value) in zip(metric_columns, statistics, strict=True):
        column.metric(label, f"{value:,.0f} từ")

    st.markdown("#### Phân bố số từ")
    bin_count = min(30, max(1, len(dataframe)))
    bins = pd.cut(word_counts, bins=bin_count, duplicates="drop")
    distribution = (
        bins.value_counts(sort=False)
        .rename_axis("Khoảng số từ")
        .to_frame("Số hợp đồng")
    )
    distribution.index = distribution.index.map(str)
    st.bar_chart(distribution)

    ranking_columns = st.columns(2)
    ranking_fields = ["contract_id", "filename", "contract_type", "part", "word_count"]
    column_config = {
        "contract_id": "ID",
        "filename": "Tên file",
        "contract_type": "Loại",
        "part": "Part",
        "word_count": st.column_config.NumberColumn("Số từ", format="%d"),
    }

    with ranking_columns[0]:
        st.markdown("#### 10 file ngắn nhất")
        shortest = dataframe.nsmallest(10, "word_count")[ranking_fields]
        st.dataframe(
            shortest,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
        )

    with ranking_columns[1]:
        st.markdown("#### 10 file dài nhất")
        longest = dataframe.nlargest(10, "word_count")[ranking_fields]
        st.dataframe(
            longest,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
        )


def render_contract_browser(dataframe: pd.DataFrame) -> None:
    """Render a compact table and selected contract details."""
    st.subheader("Danh sách hợp đồng")
    display_columns = [
        "contract_id",
        "filename",
        "contract_type",
        "part",
        "word_count",
        "char_count",
    ]
    st.dataframe(
        dataframe[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "word_count": st.column_config.NumberColumn("Số từ", format="%d"),
            "char_count": st.column_config.NumberColumn("Số ký tự", format="%d"),
        },
    )

    if dataframe.empty:
        st.info("Không có hợp đồng phù hợp với bộ lọc.")
        return

    selected_id = st.selectbox("Xem chi tiết", dataframe["contract_id"].tolist())
    contract = dataframe.loc[dataframe["contract_id"] == selected_id].iloc[0]

    st.markdown(f"### {contract['filename']}")
    detail_columns = st.columns(3)
    detail_columns[0].write(f"**ID:** `{contract['contract_id']}`")
    detail_columns[1].write(f"**Loại:** {contract['contract_type']}")
    detail_columns[2].write(f"**Part:** {contract['part']}")
    st.write(f"**TXT:** `{contract['source_txt']}`")
    st.write(f"**PDF:** `{contract['source_pdf']}`")
    st.text_area("Nội dung", contract["text"], height=500, disabled=True)


def main() -> None:
    st.set_page_config(page_title="Contract Dataset Explorer", page_icon="📄", layout="wide")
    st.title("Contract Dataset Explorer")
    st.caption("Khám phá dữ liệu trong data/processed/contracts.jsonl")

    input_path = Path(
        st.sidebar.text_input("File JSONL", str(DEFAULT_INPUT))
    ).expanduser().resolve()
    if not input_path.is_file():
        st.error(f"Không tìm thấy file: {input_path}")
        st.stop()

    try:
        contracts = load_contracts(str(input_path), input_path.stat().st_mtime)
    except (OSError, ValueError) as error:
        st.error(str(error))
        st.stop()

    filtered_contracts = filter_contracts(contracts)
    render_overview(filtered_contracts)
    render_word_statistics(filtered_contracts)
    render_contract_browser(filtered_contracts)


if __name__ == "__main__":
    main()
