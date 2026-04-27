ScoutMind — AI Meeting Planner for the Lebanese Scouts Association
==================================================================

SETUP INSTRUCTIONS
------------------

1. Clone or extract the project folder.

2. Create and activate a virtual environment:
   python3 -m venv venv
   source venv/bin/activate        # Linux / macOS
   venv\Scripts\activate           # Windows

3. Install dependencies:
   pip install -r requirements.txt

4. Configure environment variables:
   cp .env.example .env
   # Edit .env and fill in your API keys

5. Initialize the database:
   python3 init_db.py

6. Run the application:
   streamlit run ui/app.py

------------------------------------------------------------------

PROJECT STRUCTURE
-----------------
scoutmind/
├── agents/             Multi-agent pipeline (LangGraph)
├── auth/               Authentication logic (register, login)
├── database/           SQLAlchemy models and DB setup
├── memory/             Chat session and message storage
├── rag/                Knowledge base, embeddings, retriever
├── tools/              Custom and external tools
├── ui/                 Streamlit application
├── outputs/            Generated PDF meeting plans
├── .env.example        Environment variable template
├── requirements.txt    Python dependencies
└── README.txt          This file

------------------------------------------------------------------

NOTES
-----
- Never commit your .env file to version control.
- In development (no SMTP configured), email verification is
  automatically bypassed and accounts are verified on creation.
- The SQLite database file (scoutmind.db) is created automatically
  on first run in the project root directory.