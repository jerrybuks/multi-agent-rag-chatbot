# Multi-Agent RAG Chatbot

A multi-agent RAG (Retrieval Augmented Generation) chatbot system for JupiterIQ that handles customer inquiries across multiple departments (HR, Tech, Finance, Legal).

## API Key Setup

1. You can run this app with either openAI key or [OpenRouter](https://openrouter.ai/) key
   - Sign up for an account at OpenRouter or OpenAI
   - Navigate to API Keys section
   - Create a new API key

   You will also need to setup [langfuse](https://cloud.langfuse.com/)
   - sign up on langfuse
   - creat a project and get your keys (secret and private key)


2. Add your API keys to the `.env` file:
   ```bash
   OPENAI_API_KEY=your_api_key_here
   LANGFUSE_PUBLIC_KEY=langfuse_public_key
   LANGFUSE_SECRET_KEY=langfuse_secret_key
   ```
   if you are using OpenRouter you will also need to add a Base url in your env
    ```bash
   OPENAI_API_BASE=https://openrouter.ai/api/v1
   ```

## Starting Local Server Setup

### 1. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install .
```

### 3. Build the Vector Index

Run the indexing script to process handbooks and generate embeddings:

```bash
python src/build_index.py
```

This will:
- Load all handbook markdown files from the `data/` folder
- Intelligently chunk each handbook using markdown header-based splitting
- Generate embeddings for each chunk
- Save chunks and embeddings to JSONL files in the `data/` folder

### Output Files

The script generates the following files in the `data/` folder:

- `{handbook_name}_chunks.jsonl` - Chunks without embeddings (one per handbook)
- `{handbook_name}_embeddings.jsonl` - Chunks with embeddings (one per handbook)
- `all_handbooks_chunks.jsonl` - Combined chunks from all handbooks
- `all_handbooks_embeddings.jsonl` - Combined chunks with embeddings

## Running the Application

```bash
fastapi dev src/main.py
```

The server will be available at `http://localhost:8000`

- **API Docs**: http://localhost:8000/docs


## Project Structure

```
.
├── data/                    # Handbook markdown files and generated indexes
│   ├── *_handbook.md       # Source handbooks
│   └── *.jsonl             # Generated chunks and embeddings
├── src/
│   ├── build_index.py      # Index building script
│   ├── main.py             # FastAPI application
│   ├── indexing/           # Indexing utilities
│   └── querying/           # Query processing
└── requirements.txt          # Python dependencies
```

