import argparse
from pattern_executor import execute_pattern, pipe_patterns, list_models
from workers import list_workers, get_worker
import os
import logging
from config import LOG_LEVEL, DEFAULT_MODEL

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def resolve_pattern_path(pattern_name: str) -> str | None:
    # Check if it's a full path
    if os.path.isabs(pattern_name):
        if os.path.exists(pattern_name):
            return pattern_name
    else:
        # Check if it's a relative path
        if os.path.exists(pattern_name):
            return os.path.abspath(pattern_name)
        
        patterns_dir = os.path.join(os.path.dirname(__file__), 'patterns')
        # Check in patterns directory
        if pattern_name.endswith('.md'):
            full_path = os.path.join(patterns_dir, pattern_name)
            if os.path.exists(full_path):
                return full_path
        full_path = os.path.join(patterns_dir, f"{pattern_name}.md")
        if os.path.exists(full_path):
            return full_path
    return None


def main():
    parser = argparse.ArgumentParser(description="Execute a pattern or pipe multiple patterns.")
    parser.add_argument("--pattern", nargs='+', help="Name(s) or full path(s) of the pattern file(s)")
    parser.add_argument("--input", help="Input data for the pattern or path to a file containing input data")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to use for execution")
    parser.add_argument("--workers", nargs='+', help="Workers to allow")
    parser.add_argument("--list-models", action="store_true", help="List available models")
    parser.add_argument("--list-workers", action="store_true", help="List all available workers and their docstrings")
    args = parser.parse_args()

    if args.list_models:
        print("Available models:")
        for model in list_models():
            print(f"- {model}")
        return

    if args.list_workers:
        print("Available workers:")
        for worker_name in list_workers():
            worker = get_worker(worker_name)
            docstring = worker.__doc__ if worker.__doc__ else "No docstring available."
            print(f"\n{worker_name}:")
            print(f"{docstring}")
        return

    if not args.pattern:
        parser.error("Pattern names or paths are required unless --list-models or --list-workers is specified.")

    if not args.input:
        parser.error("--input is required unless --list-models or --list-workers is specified.")

    resolved_patterns = []
    missing_patterns = []
    for pattern_name in args.pattern:
        pattern_path = resolve_pattern_path(pattern_name)
        if pattern_path is None:
            missing_patterns.append(pattern_name)
        else:
            resolved_patterns.append(pattern_path)

    if missing_patterns:
        parser.error(f"The following pattern file(s) were not found: {', '.join(missing_patterns)}")

    input_data = args.input
    if os.path.isfile(args.input):
        if not os.path.exists(args.input):
            parser.error(f"Input file not found: {args.input}")
        with open(args.input, 'r') as file:
            input_data = file.read()

    allowed_workers = args.workers if args.workers else []

    try:
        if len(resolved_patterns) == 1:
            output = execute_pattern(resolved_patterns[0], input_data, args.model, allowed_workers)
        else:
            output = pipe_patterns(resolved_patterns, input_data, args.model, allowed_workers)
        print(output)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        print(f"An error occurred. Please check the logs for more information.")

if __name__ == "__main__":
    main()
