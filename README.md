# AutoDeploIA Agent API

This project implements a ReAct agent using FastAPI, LangGraph, and PostgreSQL for an AI-powered deployment assistant.

## Features

- FastAPI backend exposing chat and history endpoints.
- LangGraph ReAct agent for multi-step task execution.
- Tools for:
    - Repository Analysis (Placeholder)
    - Docker Image Building (Placeholder)
    - Kubernetes Deployment (Placeholder)
- PostgreSQL for persistent chat history.
- Alembic for database migrations.
- Dockerized setup for easy development and deployment.

## Project Structure

```
.
├── alembic/                   # Alembic migration scripts
├── app/
│   ├── __init__.py
│   ├── agents/                  # LangGraph agent logic
│   │   ├── __init__.py
│   │   ├── react_agent.py       # Core ReAct agent implementation
│   │   └── tools/               # Agent tools
│   │       ├── __init__.py
│   │       ├── docker_tool.py
│   │       ├── kubernetes_tool.py
│   │       └── repo_analyzer.py
│   ├── api/                     # FastAPI routers and endpoints
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── api.py           # Main v1 router
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           └── chat.py      # Chat related endpoints
│   ├── config.py                # Pydantic settings management
│   ├── database/                # Database models and session management
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── models.py
│   ├── main.py                  # FastAPI application entry point
│   ├── middlewares/             # Custom middlewares (if any)
│   ├── schemas/                 # Pydantic schemas for API I/O
│   │   ├── __init__.py
│   │   └── chat.py
│   └── services/                # Business logic for database interactions
│       ├── __init__.py
│       └── history_service.py
├── tests/                     # Unit and integration tests
├── .env                       # Environment variables (GIT IGNORED)
├── .gitignore
├── alembic.ini                # Alembic configuration
├── Dockerfile
├── docker-compose.yml
├── README.md
└── requirements.txt
```

## Prerequisites

- Docker and Docker Compose
- Python 3.10+
- An OpenAI API Key (or your chosen LLM provider's key)

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd <repository-name>
    ```

2.  **Configure Environment Variables:**
    Copy the `.env.example` (if provided) or create a `.env` file and fill in your details:
    ```env
    DATABASE_URL=postgresql+asyncpg://user:password@db:5432/autodeploia_db
    OPENAI_API_KEY=your_openai_api_key
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=your_langsmith_api_key
    ```
    Replace `user`, `password`, `your_openai_api_key`, and `your_langsmith_api_key` with your actual credentials. The `DATABASE_URL` is set up for the Docker Compose network.

3.  **Build and Run with Docker Compose:**
    ```bash
    docker-compose up --build -d
    ```
    This will build the Docker images and start the FastAPI application and PostgreSQL database.

4.  **Database Migrations (First time setup or model changes):**
    After the services are up, you might need to run database migrations if this is the first time or if database models have changed.

    *   Ensure `alembic` is installed locally (`pip install alembic psycopg2-binary sqlalchemy`) or run commands inside the running `app` container.
    *   **Set `DATABASE_URL` for local Alembic commands:**
        If running alembic locally, ensure your `DATABASE_URL` in `.env` or as an environment variable points to `postgresql+asyncpg://user:password@localhost:5433/autodeploia_db` (note the port `5433` as defined in `docker-compose.yml` for host access).
        ```bash
        export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5433/autodeploia_db"
        ```
    *   **Initialize Alembic (if not done):**
        ```bash
        alembic init alembic 
        ```
        Then configure `alembic/env.py` and `alembic.ini` as described in development logs or project setup steps.
    *   **Create a new migration revision (if models changed):**
        ```bash
        alembic revision -m "create_initial_tables" # Or a descriptive name for your changes
        ```
        Inspect the generated script in `alembic/versions/`.
    *   **Apply migrations:**
        ```bash
        alembic upgrade head
        ```
        Alternatively, to run migrations from within the Docker container (once it's running):
        ```bash
        docker-compose exec app alembic upgrade head
        ```

## API Endpoints

-   **POST** `/api/v1/chat/chat`
    -   Interact with the agent.
    -   Body:
        ```json
        {
          "session_id": "some-unique-session-id",
          "message": "Hello, I want to deploy a project.",
          "repo_url": "https://github.com/user/project.git" // Optional
        }
        ```
-   **GET** `/api/v1/chat/chat/history/{session_id}`
    -   Retrieve chat history for a session.

-   **GET** `/docs`
    -   Access Swagger UI for API documentation.
-   **GET** `/redoc`
    -   Access ReDoc for API documentation.

## Usage

1.  Ensure the application is running (via `docker-compose up`).
2.  Use an API client (like Postman, Insomnia, or `curl`) or the Swagger UI (`http://localhost:8000/docs`) to interact with the endpoints.

    Example `curl` for chatting:
    ```bash
    curl -X 'POST' \
      'http://localhost:8000/api/v1/chat/chat' \
      -H 'accept: application/json' \
      -H 'Content-Type: application/json' \
      -d '{ 
        "session_id": "my-test-session-001",
        "message": "Hi agent, I want to deploy the project at https://github.com/tiangolo/fastapi.git",
        "repo_url": "https://github.com/tiangolo/fastapi.git"
      }'
    ```

    Example `curl` for history:
    ```bash
    curl -X 'GET' \
      'http://localhost:8000/api/v1/chat/chat/history/my-test-session-001' \
      -H 'accept: application/json'
    ```

## Development

-   The application uses `uvicorn` with `--reload` in the Dockerfile, so changes to the code should automatically reload the server during development.
-   To install new Python dependencies:
    1.  Add them to `requirements.txt`.
    2.  Rebuild the Docker image: `docker-compose build app` or `docker-compose up --build -d app`.

## Future Enhancements

-   Implement actual client-side logic to communicate with the specified MCP servers (Docker, Kubernetes, Terraform) instead of the current placeholder tool invocations.
-   Develop more sophisticated collaboration patterns between agents beyond simple supervisor delegation.
-   Expand agent capabilities and tools.
-   Add comprehensive unit and integration tests. 

## Architecture

This project uses a **multi-agent collaboration** architecture powered by LangGraph. A central **Supervisor Agent** coordinates tasks among specialized sub-agents. These sub-agents are implemented as Langchain Tools and conceptually represent interactions with various **Multi-Control Point (MCP) servers**:

-   **Repository Analysis Agent (Tool):** Analyzes code repositories.
-   **Docker Agent (Tool):** Represents an MCP for Docker operations (e.g., `mcp-server-docker`). Handles building Docker images.
-   **Kubernetes Agent (Tool):** Represents an MCP for Kubernetes operations (e.g., `mcp-server-kubernetes`). Handles deploying to Kubernetes.
-   **Terraform Agent (Tool):** Represents an MCP for Terraform operations (e.g., `tfmcp`). Handles infrastructure provisioning and planning.

The Supervisor LLM determines the sequence of actions, deciding which sub-agent (MCP tool) to invoke based on the user's request and the ongoing conversation. The system maintains a persistent chat history in a PostgreSQL database. 