"""Entry point for running the cleaning pipeline via ``python -m src.data_cleaning``."""

from src.data_cleaning.pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline()
