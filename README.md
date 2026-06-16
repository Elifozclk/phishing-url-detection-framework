# Explainable Phishing URL Detection Framework

An end-to-end research repository for constructing a realistic large-scale phishing URL dataset and evaluating feature-based machine learning, ensemble learning, explainable AI, and character-level deep learning models.

## Project scope

The dataset contains **579,920 URLs**: 339,074 legitimate URLs (58.5%) and 240,846 phishing URLs (41.5%). The feature-based pipeline uses **74 engineered features**: 53 lexical, 9 DNS-based, and 12 WHOIS-based features. Deep-learning models operate directly on raw URL character sequences and do not use engineered features.

The conference paper covers dataset construction, machine learning, ensemble learning, and explainability. The deep-learning experiments were added later as an extension of the final project.

## Main results

| Category | Best model | Accuracy | F1-score | ROC-AUC |
|---|---|---:|---:|---:|
| Base ML | LightGBM | 0.9868 | 0.9840 | 0.9985 |
| Ensemble | Stacking AllBase | 0.9885 | 0.9861 | 0.9985 |
| Raw URL deep learning | CNN-BiLSTM Seed Ensemble | 0.9841 | 0.9807 | 0.9986 |

Global SHAP and permutation importance rankings reached a Spearman correlation of **0.916**. SHAP rankings became highly stable after 500 samples, reaching approximately **0.997–0.998** correlation with the full test-set ranking.

## Repository structure

```text
phishing-url-detection-framework/
├── notebooks/
│   ├── data_collection/
│   ├── machine_learning/
│   └── deep_learning/
├── src/
│   ├── data/
│   ├── features/
│   ├── models/
│   ├── explainability/
│   └── evaluation/
├── configs/
├── data/
├── results/
├── artifacts/deep_learning/
├── docs/
└── archive/
```

See [`docs/repository_map.md`](docs/repository_map.md) for the full experiment order.

## Installation

```bash
git clone <repository-url>
cd phishing-url-detection-framework
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

## Dataset

Download the public dataset referenced in the paper and place it at:

```text
data/processed/final_dataset.csv
```

The deep-learning notebooks require `url` and `label`. The ML/XAI notebooks require the engineered lexical, DNS, and WHOIS features. See [`data/README.md`](data/README.md).

## Running the pipeline

### Resolve legitimate domains

```bash
python -m src.data.resolve_domains \
  --input data/raw/domains.csv \
  --output data/interim/domain_scan_results.csv
```

### Crawl internal URLs

```bash
python -m src.data.crawl_internal_urls \
  --input data/interim/domain_scan_results.csv \
  --output data/interim/internal_urls.csv
```

### Experiments

Run the numbered notebooks in order. The canonical notebooks preserve the original experimental code and outputs. Because the original work was performed across Windows and Kaggle environments, update dataset paths where necessary.

## Models

### Machine learning

- Logistic Regression
- Decision Tree
- Random Forest
- XGBoost
- LightGBM
- CatBoost
- Hard voting, soft voting, and stacking ensembles

### Explainability

- Global SHAP
- Local SHAP
- Permutation importance
- LIME
- SHAP sample-size stability analysis

### Deep learning

- Character CNN Seed Ensemble
- Stacked Character BiLSTM Seed Ensemble
- CNN-BiLSTM Seed Ensemble

The seed ensembles average probabilities from models trained with seeds `42`, `2024`, and `3407`.

## Model artifacts

Packaged trained models, tokenizers, histories, thresholds, and prediction outputs are stored in `artifacts/deep_learning/`. For a public GitHub repository, consider moving these archives to GitHub Releases or Git LFS.

## Citation

Use the metadata in [`CITATION.cff`](CITATION.cff). The associated conference paper is included in `docs/conference_paper.pdf`.

## License and responsible use

Code is released under the MIT License. Dataset and third-party source terms may differ. Crawling code must be used responsibly: respect robots.txt, source terms, rate limits, privacy requirements, and applicable law.
