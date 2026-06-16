# Reproducibility Notes

1. Create a Python environment and install `requirements.txt`.
2. Run `playwright install chromium` before the crawling stage.
3. Place the downloaded dataset in `data/processed/final_dataset.csv`.
4. Update the dataset path cells in notebooks if running outside Kaggle.
5. The canonical experiment order is 01 through 08.
6. The ML split uses a fixed random seed of 42. DL models use split seed 42 and ensemble seeds 42, 2024, and 3407.
7. The conference paper covers dataset construction, ML, ensemble learning, and XAI. Deep-learning experiments are a later extension included in the final project report.

## Known legacy issues

The original notebooks contain Windows/Kaggle-specific paths and some exploratory cells. They are preserved for provenance. The main repository structure, configuration files, and reusable crawler scripts provide portable entry points, but some notebook paths must still be adjusted before a full rerun.
