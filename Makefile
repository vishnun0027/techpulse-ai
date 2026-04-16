PYTHONPATH=src

.PHONY: collect summarize deliver pipeline monitor dashboard test reset

## Run individual services
collect:
	PYTHONPATH=$(PYTHONPATH) uv run python -m services.collector.main

summarize:
	PYTHONPATH=$(PYTHONPATH) uv run python -m services.summarizer.main

deliver:
	PYTHONPATH=$(PYTHONPATH) uv run python -m services.delivery.main

## Run the full pipeline
pipeline: collect summarize deliver

## Monitoring
monitor:
	PYTHONPATH=$(PYTHONPATH) uv run python -m shared.monitor --live

dashboard:
	PYTHONPATH=$(PYTHONPATH) uv run streamlit run src/services/monitor/app.py

## Testing
test:
	PYTHONPATH=$(PYTHONPATH) uv run pytest

## Maintenance
reset:
	PYTHONPATH=$(PYTHONPATH) uv run python -m shared.maintenance reset --confirm

## Populate default configuration from migration script
migrate-config:
	PYTHONPATH=$(PYTHONPATH) uv run python scratch/migrate_config.py
