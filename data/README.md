# Data

The complete dataset contains **579,920 URLs**, with 339,074 legitimate and 240,846 phishing samples. It includes 74 engineered features: 53 lexical, 9 DNS-based, and 12 WHOIS-based features.

The dataset is not duplicated inside this repository. Download `final_dataset.csv` from the public Kaggle dataset referenced in the conference paper and place it in `data/processed/`.

Expected minimum columns for deep learning experiments:

- `url`
- `label` (`0`: legitimate, `1`: phishing)

Machine-learning experiments additionally require the engineered feature columns.
