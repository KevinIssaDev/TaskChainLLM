# TaskChainLLM 

## Overview

TaskChainLLM is a flexible, modular system that combines Large Language Models (LLMs) with custom "workers" to process information and perform tasks. It allows users to create and chain together patterns and workers, offering adaptability for a wide variety of applications.

## Key Concepts

1. **Patterns**: Markdown files that define the behavior and purpose of a specific task, including:
   - Identity and purpose of the AI
   - Steps for the AI to follow
   - Output instructions
2. **Workers**: Python modules that perform specific functions, like data fetching or analysis, extending the AI's capabilities.
3. **Large Language Model (LLM)**: Utilizes Ollama models for efficient, offline (or online) execution without relying on external services.
4. **Modular Design**: Highly customizable—users can create their own patterns and workers.
5. **Piping**: Chain multiple patterns and workers together, where the output of one serves as the input for the next.

## Installation

1. **Install Requirements**:
   - Ensure Python is installed.
   - Install dependencies using pip:
     ```
     git clone https://github.com/KevinIssaDev/TaskChainLLM.git
     cd TaskChainLLM
     pip install -r requirements.txt
     ```

## Usage

### How to Use

1. **Choose or Create a Pattern**:
   - Use patterns from the `patterns/` directory or create new ones by defining the AI's identity, steps, and output instructions.

2. **Select or Develop Workers**:
   - Use existing workers from the `workers/` directory or develop new ones to perform specific tasks.

3. **Run the Tool**:
   ```bash
   python main.py --pattern pattern1.md pattern2.md --input "Your input data" --workers worker1 worker2
   ```


### Command-line Arguments

TaskChainLLM supports the following command-line arguments:

- `--pattern`: Path(s) to the pattern file(s) *
- `--input`: Input data for the pattern or path to a file containing input data *
- `--model`: Model to use for execution (default: "qwen2.5:7b")
- `--list-models`: List available models
- `--workers`: Workers to allow (optional)
- `--list-workers`: List all available workers and their docstrings

*Required unless `--list-models` or `--list-workers` is specified.



## Example Time of Day Greeting: Pattern & Worker

### Pattern
```markdown
# IDENTITY and PURPOSE
You are a friendly greeter. Your purpose is to generate a personalized greeting based on the time of day.

# STEPS
- Use the time_of_day worker to determine the current time of day.
- Generate an appropriate greeting based on the time of day.

# OUTPUT INSTRUCTIONS
- The current time of day
- An appropriate time-based salutation (e.g., "Good morning", "Good afternoon", "Good evening")

# INPUT
INPUT:
```

### Worker

```python
import requests

def time_of_day() -> str:
    """
    Fetches the current time of day from an API.

    Returns:
        str: A string containing the current time of day.

    Example Usage:
        [[WORKER: {"name": "time_of_day"}]]
    """
    response = requests.get('http://example.com/api/time') # PLACEHOLDER
    data = response.json()
    return data['time']

worker = time_of_day
```

See `\patterns` and `\workers` for more examples.

## Contributing

Contributions to TaskChainLLM are welcome! Please feel free to submit pull requests, report bugs, or suggest new features.