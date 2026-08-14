# Cross-border Catalog Cowork

Foundation for a cross-border womenswear catalog governance workspace. The first release exports listing packages for Shopify and eBay US; it does not publish products automatically.

## Development

Install the Python package and start the API with one command:

```powershell
python -m pip install -e ".[dev]"
python -m crossborder_cowork.app
```

The API listens on `http://127.0.0.1:8000`. In a second terminal, run the minimal desktop shell:

```powershell
cd desktop
npm install
npm run dev
```

The desktop shell expects the API at `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`).

Model settings are compatible with the legacy desktop payload (`source`, `model_platform`, `model_type`, `api_key`, `api_url`, `extra_params`). Persisted desktop settings take precedence over environment variables. Environment fallback order is role-specific (`COWORK_PLANNER_*`, `COWORK_WORKER_*`, or `COWORK_REVIEWER_*`), then `COWORK_LLM_*`, then `LLM_*`; `OPENAI_API_KEY` is the final API-key fallback. API responses expose only `has_api_key`.
