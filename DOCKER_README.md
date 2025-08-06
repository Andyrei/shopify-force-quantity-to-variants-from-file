# Shopify Quantity Manager - Docker Setup

## Quick Start

### Option 1: Using Docker Compose (Recommended)

1. **Build and run the application:**
   ```bash
   docker compose up --build
   ```

2. **Access the application:**
   - Open your browser and go to `http://localhost:9999`
   - API documentation: `http://localhost:9999/docs`

3. **Stop the application:**
   ```bash
   docker compose down
   ```

### Option 2: Using Docker directly

1. **Build the Docker image:**
   ```bash
   docker build -t shopify-quantity-manager .
   ```

2. **Run the container:**
   ```bash
   docker run -p 9999:9999 -v $(pwd)/resources:/app/resources shopify-quantity-manager
   ```

## Production Deployment

For production deployment with nginx reverse proxy:

```bash
docker-compose --profile production up --build -d
```

This will:
- Run the FastAPI app on port 9999 (internal)
- Run nginx on port 80 (external access)
- Provide load balancing and static file serving

## Environment Variables

You can create a `.env` file to configure environment variables:

```env
ENVIRONMENT=production
LOG_LEVEL=info
# Add your Shopify API credentials here
SHOPIFY_API_KEY=your_api_key
SHOPIFY_API_SECRET=your_api_secret
```

## File Volumes

The Docker setup mounts the following directories:
- `./resources` - For Excel files and data processing
- `./logs` - For application logs (optional)

## Development

For development with auto-reload:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## Troubleshooting

1. **Port already in use:**
   ```bash
   docker-compose down
   # Or change the port in docker-compose.yml
   ```

2. **Permission issues with volumes:**
   ```bash
   sudo chown -R $USER:$USER resources/ logs/
   ```

3. **View logs:**
   ```bash
   docker-compose logs -f app
   ```

## Health Check

The container includes a health check that verifies the application is responding correctly. You can check the health status with:

```bash
docker-compose ps
```
