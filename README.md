# Shopify Product Quantity Manager

A FastAPI web app for bulk-updating product inventory quantities and locations in Shopify stores via Excel/CSV file upload.

## What it does

- Upload an Excel file containing SKUs or barcodes with quantity and location data
- The app matches each row against Shopify product variants (via SKU or barcode, auto-detected)
- Supports two sync modes:
  - **Adjust** — adds/subtracts quantity relative to current stock
  - **Fixed** — sets an absolute quantity value
- Optionally activates inventory tracking at a specific Shopify location and adds products to sale channels
- Outputs a detailed CSV log of every change made, including missing and duplicate SKUs

## Requirements

- Python 3.12+
- Docker & Docker Compose (for containerised deployment)

## Local Development

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the development server
uvicorn app.main:app --reload --port 9999
```

Open `http://localhost:9999` in your browser.

## Configuration

Store credentials are **never written by hand**. `config_stores.toml` is auto-generated from `.env.*` files by running:

```bash
python generate_config.py
```

Create one `.env` file per store, named `.env.<store_id>` (e.g. `.env.mystore`):

```env
STORE_NAME=my-store-handle
API_VERSION=2025-10
ACCESS_TOKEN=shpat_...
```

`generate_config.py` scans all `.env.*` files in the project root and produces `config_stores.toml`. Neither the `.env.*` files nor `config_stores.toml` are committed to the repository.

## Docker

Build and run:

```bash
docker compose up --build -d
```

App will be available at `http://localhost:9999`.

To run without Compose:

```bash
docker build -t shopify-quantity-manager .
docker run -p 9999:9999 -v $(pwd)/resources:/app/resources shopify-quantity-manager
```

For development with auto-reload:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Troubleshooting

**Port already in use:**
```bash
docker-compose down
```

**Permission issues with volumes:**
```bash
sudo chown -R $USER:$USER resources/ logs/
```

**View logs:**
```bash
docker-compose logs -f app
```

**Check health status:**
```bash
docker-compose ps
```

## Project Structure

```
app/
  main.py                        # FastAPI app entry point
  routes/api/v1/add_locations/   # Core sync logic
  utilities/
    shopify.py                   # Shopify API client helpers
    logger.py                    # CSV change logger
  views/
    templates/                   # Jinja2 HTML templates
    static/                      # CSS and JS
.env.<store_id>                  # Per-store credentials (not in repo, one file per store)
generate_config.py               # Generates config_stores.toml from .env.* files
config_stores.toml               # Auto-generated, not in repo
requirements.txt
Dockerfile
docker-compose.yml
```

## Logs

Each sync run produces a CSV file under `logs/<store_name>/` recording every quantity change, missing SKU, and duplicate entry.
