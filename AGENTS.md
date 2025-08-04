# Agent Instructions for the Gorilla Camping Project

This document provides instructions for software agents working on this project.

## Project Overview

This is a JAMstack web application for an affiliate marketing website called "Gorilla Camping".

- **Frontend:** The frontend is a static site built with HTML, CSS, and JavaScript. It is hosted on **Cloudflare Pages**. The source code is in the `static/` and `templates/` directories.
- **Backend:** The backend is a Python **Flask API** that provides data and AI-powered chat functionality. It is designed to be hosted on **Azure App Service**. The main application file is `app.py`.
- **Database:** The application uses **MongoDB** as its primary database. It can be configured via the `MONGODB_URI` environment variable. If this is not provided, the app will fall back to a temporary in-memory database for local development.
- **Caching:** The application uses **Redis** for caching AI responses to improve performance and reduce costs.
- **Monitoring:** The application is instrumented with **Datadog** for application performance monitoring (APM) and logging.

## Local Development

1.  **Install Dependencies:** It is recommended to use a Python virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
2.  **Set Environment Variables:** Create a `.env` file in the root of the project. This file is used for local development to store secrets and configuration. It is ignored by Git. See the `Environment Variables` section below for a full list of required variables. A minimal `.env` file for local development (using in-memory database and fallback AI) would be empty, but to test all features you will need to provide the relevant API keys.
3.  **Run the Application:**
    ```bash
    python app.py
    ```
    The Flask application will be running on `http://localhost:5000`. The frontend static files can be opened directly in a browser, but for the full experience, you should run a local server for the static files as well.

## Environment Variables

The application is configured using environment variables.

| Variable                               | Description                                                                                                                              | Example                                                              |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `SECRET_KEY`                           | A secret key for Flask sessions.                                                                                                         | `a-very-secret-key`                                                  |
| `MONGODB_URI`                          | The connection string for your MongoDB database.                                                                                         | `mongodb+srv://user:pass@cluster.mongodb.net/dbname`                 |
| `REDIS_URL`                            | The connection URL for your Redis cache instance.                                                                                        | `redis://:password@hostname:port`                                    |
| `AZURE_OPENAI_ENDPOINT`                | The endpoint for your Azure OpenAI service.                                                                                              | `https://your-service.openai.azure.com/`                             |
| `AZURE_OPENAI_KEY`                     | The API key for your Azure OpenAI service.                                                                                               | `your-azure-openai-key`                                              |
| `AZURE_OPENAI_DEPLOYMENT_NAME`         | The name of your deployed OpenAI model in Azure.                                                                                         | `gpt-35-turbo`                                                       |
| `DD_API_KEY`                           | Your Datadog API key.                                                                                                                    | `your-datadog-api-key`                                               |
| `DD_SITE`                              | The Datadog site to send data to.                                                                                                        | `datadoghq.com` (for US1)                                            |
| `DD_SERVICE`                           | The name of this service for Datadog.                                                                                                    | `gorilla-camping-api`                                                |
| `DD_ENV`                               | The environment name for Datadog (e.g., `production`, `development`).                                                                    | `production`                                                         |
| `DD_VERSION`                           | The version of your application for Datadog.                                                                                             | `1.0.0`                                                              |
| `ADMIN_API_KEY`                        | A secret key to access the analytics summary endpoint.                                                                                   | `a-secret-admin-key`                                                 |
| `MAILERLITE_API_KEY`                   | (Optional) API key for MailerLite integration.                                                                                           | `your-mailerlite-key`                                                |

## Leveraging the GitHub Student Developer Pack

This project is designed to be run cost-effectively using the **GitHub Student Developer Pack**. Here’s how to use it:

1.  **Azure:** Activate your Azure for Students offer to get free credits. Use these credits to provision an **Azure App Service** to host the Flask API, and an **Azure Cache for Redis** instance for caching.
2.  **Datadog:** Sign up for the Datadog offer to get a free Pro account for two years. Create an API key and use it for the `DD_API_KEY` environment variable.
3.  **MongoDB:** Use the MongoDB Atlas offer to get free credits. Create a free-tier cluster and get the connection string for the `MONGODB_URI` environment variable.
4.  **Cloudflare:** The frontend is hosted on Cloudflare Pages, which has a generous free tier that is sufficient for this project.

## CI/CD Pipeline

The project has a GitHub Actions workflow defined in `.github/workflows/main_gorillacamping.yml` to automatically deploy the backend API to Azure App Service on pushes to the `main` branch.

**Note:** There was an issue preventing automated modification of this workflow file. It currently does not have an automated testing step. This should be addressed in the future if possible.
