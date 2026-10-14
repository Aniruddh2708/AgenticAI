PYTHON ?= .venv/bin/python
UV_CACHE_DIR ?= $(CURDIR)/.runtime/uv-cache
UV_PYTHON_INSTALL_DIR ?= $(CURDIR)/.runtime/python
export UV_CACHE_DIR UV_PYTHON_INSTALL_DIR

.PHONY: setup demo api dashboard test evaluate smoke benchmark policies
setup:
	uv python install 3.11 --no-bin
	uv venv --python 3.11 --allow-existing .venv
	uv pip sync --python $(PYTHON) --require-hashes requirements.lock

demo:
	$(PYTHON) -m vibefinance.demo

api:
	$(PYTHON) -m uvicorn vibefinance.api:app --host 127.0.0.1 --port 8000

dashboard:
	PYTHONPATH=$(CURDIR) $(PYTHON) -m streamlit run vibefinance/dashboard.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false

test:
	$(PYTHON) -m pytest -q

evaluate:
	$(PYTHON) scripts/evaluate.py

policies:
	$(PYTHON) scripts/benchmark.py --policy-evaluation

benchmark:
	$(PYTHON) scripts/benchmark.py --repeats 9

smoke:
	$(PYTHON) scripts/smoke.py
