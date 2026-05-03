# ScoutMind AI

**An intelligent, multi-agent system for generating professional scout meeting plans, built for the Lebanese Scouts Association.**

ScoutMind transforms the way scout leaders plan their weekly meetings. Instead of spending hours designing activities from scratch, a leader simply describes what they need in plain language. ScoutMind's AI pipeline—six specialized agents working in sequence—handles the rest: selecting age-appropriate activities, balancing energy levels, integrating educational techniques, respecting local context (weather, Lebanese occasions), and assembling a complete, print-ready meeting plan with a single click.

---

## Table of Contents

1. [Why ScoutMind Exists](#1-why-scoutmind-exists)
2. [How It Works — Conceptual Overview](#2-how-it-works--conceptual-overview)
3. [Architecture Overview](#3-architecture-overview)
4. [The Six-Agent Pipeline](#4-the-six-agent-pipeline)
5. [Conversation Agent (Pre-Pipeline)](#5-conversation-agent-pre-pipeline)
6. [RAG — Knowledge Base & Semantic Search](#6-rag--knowledge-base--semantic-search)
7. [Tools & Utilities](#7-tools--utilities)
8. [User Interface](#8-user-interface)
9. [Authentication & Data Persistence](#9-authentication--data-persistence)
10. [Scout Unit Configuration](#10-scout-unit-configuration)
11. [Tech Stack](#11-tech-stack)
12. [Project Structure](#12-project-structure)
13. [Setup & Installation](#13-setup--installation)
14. [Environment Variables](#14-environment-variables)
15. [Running the Application](#15-running-the-application)
16. [Data Flow — End to End](#16-data-flow--end-to-end)
17. [Quality Scoring System](#17-quality-scoring-system)
18. [RAG Retrieval Evaluation](#18-rag-retrieval-evaluation)
19. [Full Pipeline Evaluation](#19-full-pipeline-evaluation)
20. [Conversation Extraction Accuracy](#20-conversation-extraction-accuracy)
21. [Future Work](#21-future-work)

---

## 1. Why ScoutMind Exists

Scout leaders in Lebanon typically plan weekly meetings manually: flipping through activity guides, estimating timing, balancing energy levels, and adapting content for different age groups. This takes significant time and domain expertise. A Beavers (ages 3–7) meeting looks nothing like a Rovers (ages 16–19) one—activity complexity, duration, energy flow, and learning objectives all differ dramatically.

ScoutMind solves this by encoding scouting pedagogy, age-specific rules, and a curated activity library into an AI pipeline. The result is a complete, structured, timestamped meeting plan that a leader can use immediately or export as a PDF.

---

## 2. How It Works — Conceptual Overview

The user experience is conversational. After logging in, a scout leader chats with ScoutMind just as they would with a knowledgeable colleague:

> *"I need a meeting plan for my Cubs unit, themed around environmental awareness. We meet this Saturday."*

ScoutMind's **Conversation Agent** extracts the key parameters (unit type, theme, optional date) through natural dialogue, asking for anything that's missing. Once it has enough information, it triggers the **Generation Pipeline** — six agents that execute in sequence, each responsible for one aspect of meeting design.

While the pipeline runs, the UI shows a live thinking panel so the leader can watch each agent work in real time. A few seconds later, the full plan appears: a structured document with a timestamped schedule, per-activity objectives and instructions, a consolidated materials list, and a quality score. A PDF download is one click away.

The entire interaction—chat history, generated plans, user profile—is saved to a database so leaders can revisit past meetings at any time.

---

## 3. Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│                         STREAMLIT UI                           │
│  (Landing Page → Auth → Chat Interface → Plan Display → PDF)   │
└───────────────────────────┬────────────────────────────────────┘
                            │
              ┌─────────────▼─────────────┐
              │    Conversation Agent      │
              │  (Claude LLM via API)      │
              │  Extract unit/theme/date   │
              └─────────────┬─────────────┘
                            │ ready_to_generate = true
              ┌─────────────▼──────────────────────────────────┐
              │          LangGraph Orchestrator                 │
              │  MeetingPlanState flows through 6 agent nodes  │
              └──────┬──────┬──────┬──────┬──────┬────────────┘
                     │      │      │      │      │
            ┌────────▼┐ ┌───▼──┐ ┌▼────┐ ┌▼───┐ ┌▼────────┐ ┌▼──────────┐
            │Context  │ │Edu.  │ │Scout│ │Act.│ │Validat. │ │Formatting │
            │Awareness│ │Design│ │Ctxt │ │Gen.│ │Agent    │ │Agent      │
            └─────────┘ └──────┘ └──┬──┘ └────┘ └─────────┘ └───────────┘
                                    │
                          ┌─────────▼──────────┐
                          │   ChromaDB (RAG)    │
                          │  sentence-transform │
                          │  scouting_activities│
                          │  edu_techniques     │
                          └────────────────────┘

Supporting layers:
  ├── SQLite + SQLAlchemy  (users, sessions, messages)
  ├── bcrypt               (password hashing)
  ├── ReportLab            (PDF export)
  ├── OpenWeatherMap API   (weather data)
  └── Lebanese Calendar    (local occasions)
```

---

## 4. The Six-Agent Pipeline

The pipeline is managed by LangGraph. All agents share a single `MeetingPlanState` TypedDict that accumulates data as it passes through each node. Agents are chained sequentially — each one builds on the outputs of those before it.

### Agent 1 — Context Awareness (`agents/context_awareness.py`)

**Role:** Gather real-world context that should influence the meeting.

This agent is purely utilitarian — no LLM is involved. It:
- Calls the **OpenWeatherMap API** to fetch current weather in Beirut (temperature, description, any precipitation)
- Queries the **Lebanese Calendar** module to find any upcoming or same-day occasion (Earth Day, Independence Day, World Scouts Day, etc.)
- Produces a set of **advisories** — short, plain-language recommendations like *"Light rain expected — plan indoor backup for outdoor activities"* or *"Upcoming occasion: Earth Day. Consider integrating environmental themes."*

These advisories are passed downstream to all subsequent agents, so the final plan is implicitly adapted to real-world conditions.

---

### Agent 2 — Educational Design (`agents/educational_design.py`)

**Role:** Design a pedagogically sound sequence of activity slots.

This agent uses **Claude (temp=0.5)** with a detailed system prompt that encodes scouting meeting structure rules:

- **Opening ceremony** (15 min, fixed) and **closing reflection** (15 min, fixed) bookend every meeting
- The **first content activity** must be high-energy (a game) to capture attention
- The **last content activity** must be high-energy (a game) to end on a positive note
- Activities must **alternate between high and low energy** — no two consecutive high-energy activities
- **No consecutive cognitive activities** (lecture + skill-building back-to-back overwhelms participants)
- Durations are **age-calibrated**: Beavers activities max at 10–15 min; Rovers can sustain 20+ min

The agent produces a sequence of **slots** — each slot specifies the activity type (game, craft, skill, lecture, etc.), energy level (high/low), target duration in minutes, and the name of an educational technique to apply. It does not yet name specific activities — that's the next agent's job.

**Educational techniques** are drawn from the RAG knowledge base and include approaches like cooperative learning, experiential learning, mindfulness integration, Socratic questioning, and others.

---

### Agent 3 — Scouting Context (`agents/scouting_context.py`)

**Role:** Select appropriate activities from the knowledge base for each slot.

This agent uses **Claude (temp=0.6)** and integrates with the RAG layer. For each slot in the sequence:
1. It queries **ChromaDB** semantically (using the theme + activity type as the search query) to retrieve candidate activities
2. It evaluates each candidate for gender appropriateness, age-appropriateness, and thematic fit
3. It selects the best match or marks the slot as **NEW** if no suitable activity exists in the knowledge base

Activities marked NEW will be fully generated from scratch by Agent 4. Activities matched from the knowledge base are used as a starting point and may be enriched.

The agent also ensures scouting values (teamwork, responsibility, citizenship, outdoor spirit) are represented across the selected activities.

---

### Agent 4 — Activity Generator (`agents/activity_generator.py`)

**Role:** Write complete, detailed descriptions for every activity in the meeting.

This is the most content-heavy agent. It uses **Claude (temp=0.7)** to generate, for each activity:

| Field | Description |
|---|---|
| **Objectives** | 2–3 learning outcomes phrased as "participants will..." |
| **Instructions** | 4–6 numbered, clear steps a leader can follow |
| **Materials** | Itemized list with quantities (e.g., "1 ball per group of 6") |
| **Educational technique** | How the chosen technique is applied in this specific activity |
| **Leader tips** | Adaptations, common pitfalls, facilitation advice |
| **Theme connection** | Explicit tie-back to the meeting's central theme |

After generating all activities individually, the agent consolidates a **master materials list** — a unified, deduplicated list of everything the leader needs to bring, organized by quantity.

If JSON parsing of the LLM output fails (malformed response), the agent automatically retries with a stricter, simpler prompt.

---

### Agent 5 — Validation (`agents/validation.py`)

**Role:** Verify the plan against a fixed set of structural rules before formatting.

This agent contains **no LLM** — it is pure deterministic logic. It checks:

1. **Total time accuracy** — does the sum of all activity durations match the target (±5 min tolerance)?
2. **Opening bookend** — is the first content activity high-energy?
3. **Closing bookend** — is the last content activity high-energy?
4. **Cognitive load** — are there any consecutive cognitive activities (lecture + skill)?
5. **Required fields** — do all activities have objectives, instructions, and materials?
6. **Age-appropriate durations** — are individual activity durations within the bounds for this unit?

The validation report distinguishes between hard **issues** (plan should be corrected) and soft **warnings** (plan is acceptable but suboptimal). The report flows into the Formatting agent and is surfaced in the quality score.

If timing is off, the **Time Validator tool** (`tools/time_validator.py`) is called to auto-adjust durations — it redistributes minutes while respecting the min/max bounds for each activity type, and never touches the fixed opening/closing bookends.

---

### Agent 6 — Formatting (`agents/formatting.py`)

**Role:** Assemble all outputs into a single, coherent meeting plan document.

This agent has **no LLM** — it is a document assembler. It:
- Builds a **timestamped schedule**: starting from the meeting's start time, it adds each activity's duration to generate clock times (e.g., 17:00 – Opening, 17:15 – Game: Nature Relay, 17:30 – Craft: Leaf Mandala...)
- Structures the full plan dict with all sections (header, context, materials, schedule, per-activity details)
- Renders a **Markdown string** for display in the UI
- Invokes the **Plan Evaluator** tool to generate a quality score (see §17)

The output of this agent is the final artifact: a `plan` dict and a `plan_text` Markdown string, both stored in the LangGraph state.

---

## 5. Conversation Agent (Pre-Pipeline)

Before the pipeline fires, the **Conversation Agent** manages the dialogue with the user. It is powered by **Claude (temp=0.7)** and maintains the full chat history.

Its responsibilities:
- Read the entire conversation history (last 20 messages, enforced alternating Human/AI structure)
- Extract **unit**, **theme**, and optionally **date** from the conversation
- Recognize unit aliases: "cubs", "boy scouts", "rovers", "beavers", etc.
- Ask for one missing piece of information at a time, in a friendly, concise way
- Return a JSON response with `ready_to_generate: true` once sufficient info is available

The agent is also hardened against **stuck loops** — repeated identical prompts or malformed history are detected and sanitized before being sent to Claude.

**Example conversation:**

```
User:    I need a meeting plan for my group.
Scout:   Sure! Which unit are you working with — Beavers, Cubs, Girl Scouts,
         Boy Scouts, Pioneers, or Rovers?
User:    Cubs.
Scout:   Got it. What theme or topic would you like to focus on?
User:    Nature and animals.
Scout:   [ready_to_generate = true → pipeline fires]
```

---

## 6. RAG — Knowledge Base & Semantic Search

ScoutMind uses **Retrieval-Augmented Generation** to ground activity suggestions in a curated, human-validated activity library rather than relying purely on the LLM's imagination.

### Knowledge Base

| File | Contents |
|---|---|
| `rag/knowledge_base/scouting_activities.json` | 50+ pre-curated scout activities with type, energy level, age suitability, materials, and brief description |
| `rag/knowledge_base/educational_techniques.json` | 10+ educational therapy techniques with descriptions and application guidance |

### Embedding & Indexing (`rag/embeddings.py`)

On first run, the knowledge base is embedded and stored in **ChromaDB** (a persistent local vector database):
- **Model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense embeddings, runs locally)
- **Collections:** `scouting_activities` and `educational_techniques`
- Metadata fields (unit, activity type, energy level, age range) are stored alongside vectors for filtering

### Retrieval (`rag/retriever.py`)

Three retrieval functions are exposed:

```python
retrieve_activities(query, unit, n_results, activity_type, energy_level)
# Semantic search + optional metadata filters

retrieve_techniques(query, unit, activity_type, n_results)
# Semantic search for educational techniques

retrieve_for_meeting(theme, unit, content_minutes)
# Comprehensive retrieval: returns both activities and techniques for a full meeting
```

Retrieval happens inside Agent 3 (Scouting Context), which combines semantic similarity with rule-based filtering (gender, age, energy level) to select the best activities for each slot.

---

## 7. Tools & Utilities

### Time Validator (`tools/time_validator.py`)

Called by the Validation agent when total meeting duration doesn't match the target. It:
- Calculates the surplus or deficit in minutes
- Distributes adjustments proportionally across activities (skipping the first and last)
- Respects per-activity-type min/max duration bounds
- Iterates until timing converges or a max-iteration limit is hit

### Plan Evaluator (`tools/plan_evaluator.py`)

Scores the final plan out of 100 across four equally-weighted dimensions (25 pts each):

| Dimension | What It Measures |
|---|---|
| **Timing** | How close the total duration is to the target (±5 min = full score) |
| **Structure** | Correct bookends, no consecutive cognitive activities, proper alternation |
| **Variety** | Number of distinct activity types used (max score at ≥5 types) |
| **Context-Awareness** | Whether weather and occasion data was incorporated into the plan |

Grade scale: **A** ≥ 90 · **B** ≥ 80 · **C** ≥ 65 · **D** ≥ 50 · **F** < 50

### Lebanese Calendar (`tools/lebanese_calendar.py`)

A hard-coded calendar of ~20 Lebanese national and international occasions mapped to MM-DD dates. Examples:
- `04-22` → Earth Day (nature/environment themes)
- `11-22` → Lebanese Independence Day (national pride, citizenship)
- `09-01` → World Scouts Day (scouting heritage)

Also exposes `get_upcoming_occasion(days=7)` to look ahead and surface occasions that are about to occur.

### PDF Exporter (`tools/pdf_exporter.py`)

Converts the plan dict into a professionally formatted A4 PDF using **ReportLab**:
- Purple accent color scheme matching the UI (`#6B44A0`)
- Structured sections: header block, timestamped schedule table, per-activity details, materials checklist
- Called when the user clicks the "Download as PDF" button in the UI
- Returns raw bytes, streamed directly through Streamlit's download button

---

## 8. User Interface

The UI is built with **Streamlit** (~1,100 lines in `ui/app.py`) and organized as a multi-page single-file application. Navigation is controlled via `st.session_state.page`.

### Pages

**Landing Page**
The entry point for unauthenticated users. Features a hero section, a three-column feature card row (Multi-Agent Intelligence / Age-Appropriate Design / Print-Ready Plans), and statistics (6 scout units, 4 districts, AI-powered). Login and Register buttons route to their respective pages.

**Register Page**
Full-name, email, password fields with a real-time password strength meter (color-coded: weak/medium/strong). District → Group → Unit cascading selectors. Validates all fields client-side before submission. Supports optional SMTP-based email verification if configured.

**Login Page**
Email and password fields. Authenticates against the database and stores the user record in session state.

**Main App — Chat Interface**
The core experience after login:
- **Sidebar:** User profile card with initials avatar, "New Meeting Plan" button, list of recent sessions (clickable to reload), delete buttons with inline confirmation, Edit Profile and Sign Out links.
- **Chat area:** Displays conversation history as styled bubbles (user messages right-aligned, assistant left-aligned). An input box at the bottom captures new messages.
- **Generation view:** When a plan is being generated, the previous chat is shown above a live `st.status()` panel listing each agent with its real-time thinking output. Once complete, the plan renders as Markdown in the chat, followed by a quality score breakdown and a PDF download button.

**Profile Page**
Editable form for full name, district, group, unit. Email is read-only. Changes are saved to the database.

### Styling

The UI uses custom CSS injected via `st.markdown()`:
- Fonts: Cormorant Garamond (headings), Crimson Pro (body) — serif, editorial feel
- Primary color: `#6B44A0` (purple)
- Custom chat bubble styling per role (user vs. assistant vs. thinking)
- Agent status blocks with color-coded state indicators (running, done, error)
- JavaScript patches to keep the sidebar always visible and disable password field reveal

---

## 9. Authentication & Data Persistence

### Authentication (`auth/auth.py`)

| Feature | Implementation |
|---|---|
| Password hashing | bcrypt (cost factor 12) |
| Email uniqueness | enforced at DB level |
| Session management | Streamlit `st.session_state` |
| Email verification | optional SMTP token flow |
| Profile updates | direct DB update with validation |

### Database (`database/models.py`)

SQLite accessed via **SQLAlchemy 2.0**. Three tables:

**`users`**
```
id, full_name, email (unique), password_hash, district, group_name, unit,
is_verified, verify_token, created_at, updated_at
```

**`chat_sessions`**
```
id, user_id (FK → users), title, unit, theme, meeting_date, created_at, updated_at
```

**`chat_messages`**
```
id, session_id (FK → chat_sessions), user_id (FK → users),
role (user | assistant | thinking | plan), content (TEXT), created_at
```

The `role` field distinguishes between visible user/assistant messages, agent thinking outputs (shown only during generation), and the final plan content (stored and reloadable).

### Session Store (`memory/session_store.py`)

Wraps all DB interactions for chat sessions:
- `create_session()` — opens a new chat session with metadata
- `get_user_sessions()` — lists all sessions for a user, newest first
- `get_session_messages()` — loads full message history for a session
- `add_message()` — appends a message and updates the session timestamp
- `update_session_title()` — renames a session
- `delete_session()` — cascade-deletes a session and all its messages

---

## 10. Scout Unit Configuration

All unit-specific configuration lives in `agents/base.py`. Six units are supported:

| Unit | Ages | Gender | Meeting Duration | Content Time | Activity Profile |
|---|---|---|---|---|---|
| **Beavers** | 3–7 | Mixed | 180 min | 150 min | Very simple, sensory, max 10–15 min per activity |
| **Cubs** | 7–11 | Mixed | 180 min | 150 min | Moderate complexity, 15–20 min per activity |
| **Girl Scouts** | 11–16 | Female | 240 min | 210 min | Complex, leadership focus, collaborative |
| **Boy Scouts** | 11–16 | Male | 240 min | 210 min | Competitive, outdoor skills, leadership |
| **Pioneers** | 16–19 | Female | 240 min | 210 min | Community service, advanced skills |
| **Rovers** | 16–19 | Male | 240 min | 210 min | Self-directed, complex topics |

All units share a fixed 30-minute bookend: 15 min opening ceremony + 15 min closing reflection.

**Activity type duration bounds:**

| Type | Min | Max |
|---|---|---|
| Game | 10 min | 15 min |
| Song/Chant | 10 min | 10 min |
| Skill | 15 min | 20 min |
| Lecture | 15 min | 20 min |
| Storytelling | 15 min | 15 min |
| Team Challenge | 15 min | 20 min |
| Craft | 15 min | 20 min |

Lebanese scout organization structure: 4 districts (Beirut, South, Mountain, Bekaa), each containing multiple named groups.

---

## 11. Tech Stack

| Layer | Technology | Version | Role |
|---|---|---|---|
| **Frontend** | Streamlit | 1.35+ | Web UI |
| **LLM** | Anthropic Claude (`claude-sonnet-4-6`) | latest | Conversation + 3 agent nodes |
| **Agent Orchestration** | LangGraph | 0.1+ | Pipeline state machine |
| **LLM Chains** | LangChain + LangChain-Anthropic | 0.2+ | Message formatting & invocation |
| **Vector DB** | ChromaDB | 1.0+ | Activity/technique semantic index |
| **Embeddings** | Sentence-Transformers (`all-MiniLM-L6-v2`) | latest | Local embedding model |
| **Database** | SQLite + SQLAlchemy | 2.0+ | User, session, message storage |
| **Auth** | bcrypt | 4.1+ | Password hashing |
| **PDF** | ReportLab | 4.2+ | PDF generation |
| **Weather** | OpenWeatherMap REST API | v2.5 | Live weather data |
| **Validation** | Pydantic | 2.0+ | Data validation |
| **Config** | python-dotenv | 1.0+ | Environment variable management |

---

## 12. Project Structure

```
scoutmind-ai/
│
├── agents/                         # Core AI pipeline
│   ├── base.py                     # Unit configs, activity types, LLM setup
│   ├── orchestrator.py             # LangGraph pipeline + conversation agent
│   ├── context_awareness.py        # Agent 1: weather + occasion data
│   ├── educational_design.py       # Agent 2: activity sequence design
│   ├── scouting_context.py         # Agent 3: RAG activity selection
│   ├── activity_generator.py       # Agent 4: full activity descriptions
│   ├── validation.py               # Agent 5: structural rule checks
│   └── formatting.py               # Agent 6: document assembly
│
├── ui/
│   └── app.py                      # Streamlit application (all pages)
│
├── database/
│   └── models.py                   # SQLAlchemy ORM models
│
├── auth/
│   └── auth.py                     # Registration, login, profile management
│
├── memory/
│   └── session_store.py            # Chat session CRUD
│
├── rag/
│   ├── embeddings.py               # ChromaDB setup + embedding generation
│   ├── retriever.py                # Semantic search functions
│   ├── generate_kb.py              # Knowledge base generation script
│   └── knowledge_base/
│       ├── scouting_activities.json
│       └── educational_techniques.json
│
├── tools/
│   ├── pdf_exporter.py             # ReportLab PDF generation
│   ├── time_validator.py           # Timing correction algorithm
│   ├── plan_evaluator.py           # Quality scoring (4 dimensions)
│   └── lebanese_calendar.py        # Lebanese/scouting occasions
│
├── .streamlit/
│   └── config.toml                 # Streamlit theme/layout config
│
├── init_db.py                      # Database initialization script
├── .env.example                    # Environment variable template
├── pyproject.toml                  # Project metadata (Python 3.10+)
├── requirements.txt                # Python dependencies
└── scoutmind.db                    # SQLite database (auto-created)
```

---

## 13. Setup & Installation

**Prerequisites:** Python 3.10+, pip

```bash
# 1. Clone the repository
git clone <repo-url>
cd scoutmind-ai

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables (see §14)
cp .env.example .env
# Edit .env and fill in your API keys

# 5. Initialize the database
python init_db.py

# 6. Build the RAG knowledge base (first-time only)
python rag/generate_kb.py
```

> **Note on sentence-transformers:** The embedding model (`all-MiniLM-L6-v2`) is downloaded automatically on first use (~80 MB). Set `USE_TF=0` and `USE_KERAS=0` in your `.env` to prevent TensorFlow conflicts if you have it installed.

---

## 14. Environment Variables

Create a `.env` file at the project root (copy from `.env.example`):

```env
# Required — Anthropic API key for Claude
ANTHROPIC_API_KEY=sk-ant-...

# Optional — OpenWeatherMap API key for live weather
# If not set, context_awareness agent skips weather data
OPENWEATHER_API_KEY=...

# Optional — Base URL for email verification links
APP_URL=http://localhost:8501

# Optional — SMTP settings for email verification emails
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=...

# Prevent conflicts with TensorFlow if installed
USE_TF=0
USE_KERAS=0
```

Only `ANTHROPIC_API_KEY` is strictly required to run the application. Without `OPENWEATHER_API_KEY`, the Context Awareness agent will skip live weather and rely on occasion data alone.

---

## 15. Running the Application

```bash
streamlit run ui/app.py
```

The app will open at `http://localhost:8501`. On first launch:
1. The ChromaDB vector index is built from the knowledge base JSONs (takes ~10–30 seconds)
2. Register a new account
3. Start chatting — describe your meeting and ScoutMind will guide you through it

---

## 16. Data Flow — End to End

```
[User opens browser]
        │
        ▼
Landing Page (unauthenticated)
        │
        ▼
Register / Login
  └─► User record created/verified in SQLite
        │
        ▼
Main Chat Interface
  User types: "I need a Cubs meeting on nature"
        │
        ▼
run_conversation_agent()
  ├─ Sends history + message to Claude
  ├─ Claude extracts: unit=Cubs, theme=nature, date=None
  ├─ ready_to_generate = false (no date yet)
  └─ Returns: "Great! Do you have a specific date in mind, or should I use this week?"
        │
User replies: "This Saturday"
        │
        ▼
run_conversation_agent()
  ├─ Extracts: unit=Cubs, theme=nature, date=2026-05-02
  ├─ ready_to_generate = true
  └─ Returns acknowledgment message
        │
        ▼
Pipeline triggered — LangGraph executes 6 nodes:
  │
  ├─ Node 1: Context Awareness
  │    ├─ OpenWeatherMap: "Partly cloudy, 22°C, no rain"
  │    ├─ Lebanese Calendar: "No occasion this week"
  │    └─ Advisory: "Good outdoor weather — consider outdoor activities"
  │
  ├─ Node 2: Educational Design
  │    ├─ LLM designs sequence for 150 min content:
  │    │   [High-Energy Game 15min] → [Storytelling 15min] →
  │    │   [Craft 20min] → [Team Challenge 20min] →
  │    │   [Skill 15min] → [High-Energy Game 15min]
  │    └─ Each slot assigned educational technique
  │
  ├─ Node 3: Scouting Context
  │    ├─ Queries ChromaDB: "nature game cubs" → top 5 candidates
  │    ├─ Selects: "Animal Kingdom Relay" (game), "The Lost Forester" (story)...
  │    └─ 1 slot marked NEW (no matching craft in KB)
  │
  ├─ Node 4: Activity Generator
  │    ├─ Generates full descriptions for all activities
  │    ├─ NEW craft: "Leaf Mandala" — generates from scratch
  │    └─ Consolidates master materials list
  │
  ├─ Node 5: Validation
  │    ├─ Total time: 180 min ✓ (matches target ±5)
  │    ├─ First activity: high-energy ✓
  │    ├─ Last activity: high-energy ✓
  │    ├─ No consecutive cognitive ✓
  │    └─ All required fields present ✓
  │
  └─ Node 6: Formatting
       ├─ Generates timestamped schedule (17:00 → 20:00)
       ├─ Assembles Markdown plan string
       └─ Plan Evaluator: Score 88/100 (B)
        │
        ▼
UI renders:
  ├─ Full plan in Markdown chat bubble
  ├─ Quality score panel (Timing: 25/25, Structure: 22/25, Variety: 23/25, Context: 18/25)
  └─ "Download as PDF" button
        │
User clicks Download
        │
        ▼
ReportLab generates PDF → browser downloads "cubs_nature_2026-05-02.pdf"
        │
        ▼
Plan + messages saved to SQLite
User can revisit in sidebar → "Cubs — Nature (May 2)"
```

---

## 17. Quality Scoring System

Every generated plan receives an automatic quality score from the **Plan Evaluator** (`tools/plan_evaluator.py`). The score is displayed in the UI immediately after plan generation.

### Scoring Dimensions (25 points each, 100 total)

**Timing (25 pts)**
- Full 25 pts if total duration is within ±5 minutes of the target
- Scaled down linearly for larger deviations
- 0 pts if deviation exceeds 30 minutes

**Structure (25 pts)**
- First content activity is high-energy: 8 pts
- Last content activity is high-energy: 8 pts
- No consecutive cognitive activities: 9 pts

**Variety (25 pts)**
- Scores based on number of distinct activity types used
- 1 type: 5 pts · 2 types: 10 pts · 3 types: 15 pts · 4 types: 20 pts · 5+ types: 25 pts

**Context-Awareness (25 pts)**
- Weather data retrieved and used: 12 pts
- Occasion data retrieved and used: 13 pts

### Grade Scale

| Score | Grade | Meaning |
|---|---|---|
| 90–100 | **A** | Excellent — well-structured, varied, context-aware |
| 80–89 | **B** | Good — minor improvements possible |
| 65–79 | **C** | Acceptable — some structural gaps |
| 50–64 | **D** | Needs work — multiple issues flagged |
| < 50 | **F** | Poor — significant structural or timing problems |

---

## 18. RAG Retrieval Evaluation

ScoutMind's retrieval layer was formally evaluated using three standard information retrieval metrics computed over a 15-query test set drawn from the full knowledge base (163 activities).

### Evaluation Setup

**Metrics:**
- **P@K (Precision at K)** — fraction of top-K retrieved activities that are relevant
- **R@K (Recall at K)** — fraction of all relevant activities that appear in the top-K
- **MRR (Mean Reciprocal Rank)** — average of 1/rank of the first relevant result; measures how high the best match ranks

**Ground truth:** for each test query, "relevant" is defined as any activity whose `theme_tags` contain at least one query-relevant tag, whose `suitable_units` includes the target unit, and whose `type` matches the expected activity type (where specified).

**Configuration comparison:**

| Axis | Option A | Option B |
|---|---|---|
| Embedding model | `all-MiniLM-L6-v2` (384-dim) | `all-mpnet-base-v2` (768-dim) |
| Retrieval depth | K = 3 | K = 5 / K = 10 |

The evaluation script is at `tools/rag_evaluator.py` and runs fully offline (no ChromaDB dependency).

### Test Queries

| ID | Description | Relevant Activities |
|---|---|---|
| Q01 | Teamwork game — Cubs | 22 |
| Q02 | Nature/environment — any type | 23 |
| Q03 | First aid skill — Boy Scouts | 12 |
| Q04 | Knot skills — Boy Scouts | 10 |
| Q05 | Friendship/values — Cubs | 30 |
| Q06 | High-energy game — Beavers | 11 |
| Q07 | Environment/responsibility — Pioneers | 45 |
| Q08 | Leadership challenge — Rovers | 32 |
| Q09 | Navigation — Boy Scouts | 21 |
| Q10 | Song/community — Cubs | 10 |
| Q11 | Scout law values — Boy Scouts | 12 |
| Q12 | Creative craft — Girl Scouts | 12 |
| Q13 | Storytelling — Cubs | 0 *(skipped — KB gap)* |
| Q14 | Mindfulness/awareness — Girl Scouts | 20 |
| Q15 | Cooperative challenge — Pioneers | 38 |

### Results

**`all-MiniLM-L6-v2` (384-dim) — production model:**

| K | P@K | R@K | MRR |
|---|---|---|---|
| 3 | 0.857 | 0.154 | 0.917 |
| 5 | 0.771 | 0.232 | 0.917 |
| 10 | 0.657 | 0.378 | 0.917 |

**`all-mpnet-base-v2` (768-dim) — comparison model:**

| K | P@K | R@K | MRR |
|---|---|---|---|
| 3 | 0.762 | 0.135 | 0.893 |
| 5 | 0.729 | 0.214 | 0.911 |
| 10 | 0.621 | 0.361 | 0.911 |

### Analysis

**`all-MiniLM-L6-v2` outperforms `all-mpnet-base-v2` across every metric and every K value.** Despite being a smaller model (384 vs 768 dimensions), MiniLM is specifically optimised for semantic similarity on short, structured texts — which matches the activity document format exactly. mpnet, while stronger on longer or more nuanced passages, does not gain an advantage here.

**MRR of 0.917** across all K values confirms that the system consistently places a relevant activity in position 1 or 2 — meaning the agent almost always sees a strong match immediately.

**K trade-off:** higher K improves recall but reduces precision. K = 5 is the optimal balance (P@5 = 0.771, R@5 = 0.232, MRR = 0.917). The production pipeline uses K = 10 for breadth, which is justified for a meeting planner that needs variety across multiple activity slots.

**Q13 (Storytelling — Cubs)** returned zero relevant activities, exposing a genuine knowledge base gap. Storytelling activities exist but none are tagged for the Cubs unit — a finding that directly informs future KB expansion.

### Chunking Strategy

Each scouting activity is embedded as a single whole document rather than split into chunks. This decision is justified by three factors:

1. **Document size** — activity descriptions are 100–250 tokens, well within the 512-token limit of both models
2. **Semantic coherence** — splitting an activity (e.g., separating materials from instructions) would fragment the meaning and degrade retrieval quality
3. **Self-contained units** — each activity is an independent, atomic entity; the entire document is relevant or irrelevant as a whole

---

## 19. Full Pipeline Evaluation

The complete 6-agent pipeline was evaluated on 5 diverse unit/theme combinations to measure end-to-end plan quality.

### Test Cases

| ID | Unit | Theme |
|---|---|---|
| P01 | Cubs | Nature and Wildlife |
| P02 | Boy Scouts | Leadership |
| P03 | Girl Scouts | Friendship |
| P04 | Rovers | Community Service |
| P05 | Beavers | Animals |

### Results

| ID | Unit | Quality Score | Grade | Timing | Validation | Time Fixes |
|---|---|---|---|---|---|---|
| P01 | Cubs | 90/100 | A | Perfect | Pass | 0 |
| P02 | Boy Scouts | 90/100 | A | Perfect | Pass | 0 |
| P03 | Girl Scouts | 90/100 | A | Perfect | Pass | 0 |
| P04 | Rovers | 87/100 | B | Perfect | Pass | 0 |
| P05 | Beavers | 87/100 | B | Perfect | Pass | 0 |

**Summary:**
- Mean quality score: **88.8 / 100**
- Score range: 87 – 90
- Timing accuracy: **100%** (all plans within ±5 min of target duration)
- Validation pass rate: **100%** (no structural rule violations)
- Plans requiring time corrections: **0%**
- Grade distribution: A × 3, B × 2

### Score Breakdown Analysis

Quality scores decompose across four dimensions (25 pts each). With no Lebanese occasion on the test date (28/04/2026), the context-awareness dimension scored 15/25 (weather data + advisories; no occasion bonus). The remaining 72–75 points were distributed across timing, structure, and variety — confirming that all plans achieved perfect timing (25/25) and full structural correctness (25/25), with variety scores of 22–25 depending on how many of the 7 activity types the LLM selected.

---

## 20. Conversation Extraction Accuracy

The conversation agent was evaluated on 15 varied natural-language inputs covering different phrasings, unit aliases, date formats, and communication styles.

### Test Inputs

| ID | Description | Expected Unit | Expected Theme |
|---|---|---|---|
| C01 | Direct: Cubs + nature + no date | Cubs | Nature |
| C02 | Direct: Boy Scouts + leadership + date | Boy Scouts | Leadership |
| C03 | Natural: Girl Scouts + friendship + today | Girl Scouts | Friendship |
| C04 | Natural: Rovers + community service + today | Rovers | Community Service |
| C05 | Lowercase unit: Beavers + animals + any date | Beavers | Animals |
| C06 | Direct: Pioneers + environment + date | Pioneers | Environment |
| C07 | Lowercase unit: Cubs + sports + no date | Cubs | Sports and Fitness |
| C08 | Alias "boy scout" → Boy Scouts + first aid | Boy Scouts | First Aid |
| C09 | Full sentence: Girl Scouts + creativity + date | Girl Scouts | Creativity and Arts |
| C10 | Direct: Rovers + adventure + no date | Rovers | Adventure and Survival |
| C11 | Natural: Pioneers + leadership + no date | Pioneers | Personal Development |
| C12 | Alias "rover scouts" → Rovers + citizenship + date | Rovers | Citizenship |
| C13 | Natural: Girl Scouts + life skills + date | Girl Scouts | Cooking and Life Skills |
| C14 | Natural: Boy Scouts + knots + any date | Boy Scouts | Knots and Camping |
| C15 | Natural: Cubs + environment + no date | Cubs | Environment and Recycling |

### Results

| Metric | Score |
|---|---|
| Ready-to-generate rate | 15 / 15 = **100%** |
| Unit extraction accuracy | 15 / 15 = **100%** |
| Theme extraction accuracy | 15 / 15 = **100%** |
| Overall accuracy | **100%** |

Every test case triggered immediate plan generation (`ready_to_generate: true`) with the correct unit and a meaningful theme — including lowercase inputs (`cubs`, `beavers`), informal aliases (`boy scout`, `rover scouts`), relative dates (`today`, `any date`), and varied sentence structures. The agent demonstrated robust parsing of natural language scout meeting requests across all tested conditions.

---

## 21. Future Work

ScoutMind AI currently focuses on generating weekly scout meeting plans. However, the same multi-agent architecture can be extended in several directions to support more complex planning tasks and even other domains.

### 1. Annual Program Generator

A future version of ScoutMind could generate a complete annual scouting program instead of only one meeting at a time. This would allow leaders to plan a full year of weekly meetings, themes, badge-related activities, seasonal events, and progression goals. The system could ensure that topics are not repeated too often and that the yearly program balances leadership, teamwork, outdoor skills, citizenship, creativity, and personal development.

### 2. Camp and Trip Generator

ScoutMind could also be extended to generate multi-day camp and trip programs. This version would require additional planning components such as meal schedules, transportation, safety checks, equipment lists, patrol responsibilities, risk assessment, and backup indoor/outdoor activities. Since camps are more complex than weekly meetings, this would be a natural extension of the current agent pipeline.

### 3. MCP Server Integration

Another future improvement is to expose ScoutMind as an MCP server. This would allow the system to be used as a tool by other AI applications or clients instead of being limited to the Streamlit interface. With MCP integration, a leader could request a meeting plan from another assistant, note-taking app, or calendar workflow while still using ScoutMind’s specialized planning pipeline in the background.

### 4. Arabic Language Support

Since many scout leaders in Lebanon work primarily in Arabic, future versions of ScoutMind should support Arabic input and Arabic output. This would include translating the user interface, adapting prompts, supporting right-to-left layout, and expanding the knowledge base with Arabic scouting activities and educational techniques. This improvement would make the system more accessible and practical for local scout leaders.

### 5. Leader Feedback Loop

A future version could include a feedback loop where leaders rate generated plans and individual activities after using them in real meetings. This feedback could be stored and used to improve future recommendations. For example, activities that leaders rate highly could be retrieved more often for similar units or themes, while activities that receive poor feedback could be revised or deprioritized.

### 6. Extension to Educational Lesson Planning

The same architecture can also be adapted to education. Instead of generating scout meetings, the system could help teachers generate lesson plans, classroom activities, worksheets, assessments, and differentiated learning materials. The RAG knowledge base would contain curriculum standards, lesson examples, teaching strategies, and classroom resources. The validation agent would check learning objectives, timing, assessment alignment, and age appropriateness.

### 7. Extension to Therapy and Mental Wellness Planning

The same architecture can also be adapted to therapy or mental wellness support. In this setting, the system could help professionals prepare structured session plans, organize activities, define session goals, and document progress-oriented outlines. The RAG knowledge base would contain therapy techniques, session templates, psychoeducational activities, and professional guidelines. The validation layer would be especially important to ensure that generated outputs remain structured, safe, and appropriate for professional review.

Overall, these directions show that ScoutMind is not only a scout meeting planner, but also a reusable multi-agent planning architecture. By changing the knowledge base, validation rules, and output format, the same design can support other domains that require structured, context-aware, and human-centered planning.

*ScoutMind is built as a university LLM project demonstrating multi-agent AI systems in a real-world domain application.*
