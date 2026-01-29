# Code Review Assistant

An AI-powered code review tool that combines static analysis with LLM-based insights to provide comprehensive code reviews for Python and JavaScript projects.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-blue.svg)

## Features

- 🔍 **Static Analysis**: Flake8 + Radon for Python, ESLint for JavaScript
- 🤖 **LLM Review**: Groq-powered AI analysis for deeper insights
- 📁 **Multiple Input Sources**: Upload ZIP files or clone Git repositories
- 📋 **Configurable Rulesets**: PEP8, OWASP Top 10, React Hooks, and more
- 🎯 **Smart Deduplication**: Merges overlapping findings from different sources
- 📊 **Impact Ranking**: Prioritizes issues by severity and reach
- 🌐 **Modern Web UI**: Clean, responsive interface for easy interaction

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 16+ (for ESLint)
- Git (for repository cloning)
- Groq API key (for LLM features)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/RavikantiAkshay/code-review-assistant.git
   cd code-review-assistant
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   .\venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Node.js dependencies** (for ESLint)
   ```bash
   npm install
   ```

5. **Configure environment**
   ```bash
   # Create .env file
   echo "GROQ_API_KEY=your_groq_api_key_here" > .env
   ```
   
   Get your Groq API key from: https://console.groq.com/keys

### Running the Application

1. **Start the backend server**
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```

2. **Open the frontend**
   
   Open `frontend/index.html` in your browser, or access:
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## Usage

### Web Interface

1. Navigate to `frontend/index.html`
2. Choose upload method:
   - **ZIP Upload**: Drag & drop or click to upload a ZIP file
   - **Git URL**: Enter a GitHub/GitLab repository URL
3. (Optional) Select a specific ruleset
4. Click "Start Review" and wait for results
5. Filter results by severity, file, or category

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/rulesets` | GET | List available rulesets |
| `/upload-zip/` | POST | Upload ZIP for analysis |
| `/clone-repo/` | POST | Clone Git repository |
| `/review` | POST | Run full code review |

### Example API Usage

```python
import requests

# Upload and review a ZIP file
with open("my_code.zip", "rb") as f:
    upload_response = requests.post(
        "http://localhost:8000/upload-zip/",
        files={"file": f}
    )

data = upload_response.json()

# Run the review
review_response = requests.post(
    "http://localhost:8000/review",
    json={
        "temp_dir": data["temp_dir"],
        "files": data["files"],
        "ruleset": "pep8"  # optional
    }
)

results = review_response.json()
print(f"Found {len(results['ranked_issues'])} issues")
```

## Project Structure

```
code-review-assistant/
├── backend/
│   ├── main.py              # FastAPI app & endpoints
│   ├── analysis/
│   │   ├── python_static.py # Flake8 + Radon integration
│   │   └── javascript_static.py  # ESLint integration
│   ├── llm/
│   │   ├── reviewer.py      # Groq LLM integration
│   │   └── prompts/         # Prompt templates
│   ├── reviews/
│   │   ├── deduplicator.py  # Issue deduplication
│   │   └── ranking.py       # Impact scoring
│   ├── rulesets/
│   │   └── registry.py      # Ruleset definitions
│   └── ingestion/
│       └── git_ingestion.py # Git repository cloning
├── frontend/
│   ├── index.html           # Main UI
│   ├── styles.css           # Styling
│   └── app.js               # Frontend logic
├── evaluation/
│   ├── seed_repo/           # Test repository
│   ├── ground_truth.json    # Expected issues
│   ├── evaluate.py          # Evaluation script
│   └── evaluation_report.md # Performance metrics
├── docs/
│   ├── prompts.md           # Prompt documentation
│   └── sample_outputs/      # Example outputs
├── requirements.txt
├── package.json
└── README.md
```

## Available Rulesets

| Ruleset | Language | Description |
|---------|----------|-------------|
| `pep8` | Python | PEP 8 style guide compliance |
| `owasp_top_10` | All | Security vulnerabilities |
| `react_hooks` | JavaScript | React Hooks best practices |

## Evaluation Results

The system has been evaluated against a seed repository with 39 known issues:

| Metric | Score |
|--------|-------|
| **Precision** | 58.7% |
| **Recall** | 67.5% |
| **F1-Score** | 62.8% |

### Performance by Category

| Category | F1-Score |
|----------|----------|
| Security | 84.2% |
| Complexity | 72.7% |
| Readability | 58.8% |
| Correctness | 45.5% |

## 📚 Documentation & Deliverables

| Document | Location | Description |
|----------|----------|-------------|
| **Prompt Templates** | [`docs/prompts.md`](docs/prompts.md) | LLM prompts, JSON schema, customization guide |
| **Sample Outputs** | [`docs/sample_outputs/`](docs/sample_outputs/) | Example Python & JavaScript review outputs |
| **Evaluation Metrics** | [`docs/evaluation_metrics.md`](docs/evaluation_metrics.md) | Precision/Recall breakdown by category |
| **Evaluation Report** | [`evaluation/evaluation_report.md`](evaluation/evaluation_report.md) | Detailed analysis with TP/FP/FN |
| **Ground Truth** | [`evaluation/ground_truth.json`](evaluation/ground_truth.json) | 39 annotated issues for testing |
| **Test Repository** | [`evaluation/seed_repo/`](evaluation/seed_repo/) | Code files with intentional issues |

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes* | Groq API key for LLM reviews |

*LLM reviews are disabled if not set; static analysis still works.

### Customization

- **Add rulesets**: Edit `backend/rulesets/registry.py`
- **Modify prompts**: Edit files in `backend/llm/prompts/`
- **Adjust thresholds**: Edit `backend/reviews/ranking.py`

## Development

### Running Tests

```bash
# Run evaluation
python evaluation/evaluate.py

# Test static analysis
python -c "from backend.analysis.python_static import analyze_python_file_normalized; print(analyze_python_file_normalized('test.py'))"
```

### Adding New Languages

1. Create analyzer in `backend/analysis/`
2. Add language extensions in `backend/main.py`
3. Update frontend file filtering in `frontend/app.js`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the evaluation to ensure quality
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [Groq](https://groq.com/) for LLM API
- [FastAPI](https://fastapi.tiangolo.com/) for the backend framework
- [Flake8](https://flake8.pycqa.org/) and [ESLint](https://eslint.org/) for static analysis