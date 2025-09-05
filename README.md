# Gorilla Camping
A Flask site for off-grid nomads with Azure cloud integration.

## Features
- 🏕️ Camping gear reviews and recommendations
- 📝 Blog posts and guides  
- 🤖 AI-powered camping assistant
- 📊 Analytics and affiliate tracking
- ☁️ Azure cloud services integration

## Azure Integration
This application supports Azure services for enhanced scalability and reliability:
- **Azure Cosmos DB** - Primary database option
- **Azure Blob Storage** - File storage and static content
- **Azure Key Vault** - Secrets management
- **Azure Application Insights** - Monitoring and analytics

See [AZURE_SETUP.md](AZURE_SETUP.md) for detailed Azure configuration guide.

## Running with Docker

This project includes a Docker setup for easy local development and deployment.

- **Python version:** 3.11 (as specified in the Dockerfile)
- **Exposed port:** 5000 (Flask default)
- **Environment variables:** Configure Azure services or use fallback options

### Build and Run

```sh
docker compose up --build
```

The Flask app will be available at [http://localhost:5000](http://localhost:5000).

### Configuration Options

1. **Full Azure Integration** - Use Azure services for production
2. **Hybrid Mode** - Mix Azure and traditional services  
3. **Development Mode** - Use local/demo services for development

Create a `.env` file from `azure.env.template` to configure your environment.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment (optional)
cp azure.env.template .env
# Edit .env with your service credentials

# Run the application
python app.py
```

## Deployment

The app is configured for Azure App Service deployment via GitHub Actions.
See `.github/workflows/python-app.yml` for the deployment pipeline.

## Features

- Responsive design optimized for mobile camping scenarios
- AI-powered camping assistant using Google Gemini
- Affiliate link tracking and analytics
- Email subscription management
- Social media integration
- SEO optimization
- Azure cloud services support
