install:
	python -m pip install -r requirements.txt
	playwright install chromium

resolve-domains:
	python -m src.data.resolve_domains --input data/raw/domains.csv --output data/interim/domain_scan_results.csv

crawl:
	python -m src.data.crawl_internal_urls --input data/interim/domain_scan_results.csv --output data/interim/internal_urls.csv
