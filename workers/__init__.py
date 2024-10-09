import os
import importlib
from typing import Dict, Callable
# Dictionary to store dynamically loaded workers
workers: Dict[str, Callable] = {}

def load_workers():
    """Dynamically load worker modules from the workers directory."""
    for filename in os.listdir(os.path.dirname(__file__)):
        if filename.endswith('.py') and not filename.startswith('__'):
            module_name = filename[:-3]  # Remove .py extension
            module = importlib.import_module(f'workers.{module_name}')
            if hasattr(module, 'worker'):
                workers[module_name] = module.worker

def get_worker(worker_name: str) -> Callable:
    """Get a worker function by name."""
    if not workers:
        load_workers()
    return workers.get(worker_name)

def list_workers() -> list:
    """List all available workers."""
    if not workers:
        load_workers()
    return list(workers.keys())

def call_worker(worker_name: str, *args, **kwargs):
    """Call a worker function by name."""
    worker = get_worker(worker_name)
    if worker:
        return worker(*args, **kwargs)
    else:
        raise ValueError(f"Worker '{worker_name}' not found")