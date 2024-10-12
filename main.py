import argparse
from pattern_executor import execute_pattern, pipe_patterns, list_models
from workers import list_workers, get_worker
import os


def main():
    parser = argparse.ArgumentParser(description="Execute a pattern or pipe multiple patterns.")
    parser.add_argument("pattern_paths", nargs='*', help="Path(s) to the pattern file(s)")
    parser.add_argument("--input", help="Input data for the pattern or path to a file containing input data")
    parser.add_argument("--model", default="qwen2.5:7b", help="Model to use for execution")
    parser.add_argument("--list-models", action="store_true", help="List available models")
    parser.add_argument("--workers", nargs='+', help="Workers to allow")
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

    if not args.pattern_paths:
        parser.error("Pattern paths are required unless --list-models or --list-workers is specified.")

    if not args.input:
        parser.error("--input is required unless --list-models or --list-workers is specified.")

    input_data = args.input
    if os.path.isfile(args.input):
        with open(args.input, 'r') as file:
            input_data = file.read()

    # Use all workers if not specified
    allowed_workers = args.workers if args.workers else [] #list_workers(), if we want to default to all workers, else []

    try:
        if len(args.pattern_paths) == 1:
            output = execute_pattern(args.pattern_paths[0], input_data, args.model, allowed_workers)
        else:
            output = pipe_patterns(args.pattern_paths, input_data, args.model, allowed_workers)
        print(output)
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
