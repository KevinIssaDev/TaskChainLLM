import os
import logging
import re
from typing import Dict, List, Tuple
import requests
import json
from workers import get_worker, list_workers

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

API_BASE_URL = os.environ.get('OLLAMA_API_BASE_URL', 'http://localhost:11434')

def list_models() -> List[str]:
    response = requests.get(f'{API_BASE_URL}/api/tags')
    if response.status_code == 200:
        models = response.json()
        return [model['name'] for model in models['models']]
    else:
        raise Exception(f"Error fetching models: {response.text}")

def execute_pattern(pattern_path: str, input_data: str, model: str, allowed_workers: List[str]) -> str:
    pattern_content = read_file(pattern_path)
    sections = extract_sections_from_markdown(pattern_content)
    system_prompt = create_system_prompt(sections, allowed_workers)
    output = execute_steps_and_format(input_data, system_prompt, model, sections, allowed_workers)
    return output

def read_file(file_path: str) -> str:
    with open(file_path, 'r') as file:
        return file.read()

def extract_sections_from_markdown(markdown_content: str) -> Dict[str, str]:
    sections = {}
    current_section = None
    for line in markdown_content.split('\n'):
        if line.startswith('# '):
            current_section = line[2:].strip()
            sections[current_section] = ""
        elif current_section:
            sections[current_section] += line + "\n"
    return sections

def create_system_prompt(sections: Dict[str, str], allowed_workers: List[str]) -> str:
    system_prompt = f"{sections['IDENTITY and PURPOSE']}\n\n"
    system_prompt += "Follow these steps:\n"
    steps_list = [step.strip()[2:] for step in sections['STEPS'].split('\n') if step.strip().startswith('- ')]
    system_prompt += "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps_list))

    available_workers = [worker for worker in list_workers() if worker in allowed_workers]
    if available_workers:
        system_prompt += f"\n\nAvailable workers: {', '.join(available_workers)}"
        system_prompt += "\nTo use a worker, include [[WORKER: {\"name\": \"worker_name\", \"args\": {\"arg1\": \"value1\", \"arg2\": \"value2\"}}]] in your response."
        worker_docstrings = "\n".join([f"{worker}:\n{get_worker_docstring(worker)}" for worker in available_workers])
        system_prompt += f"\n\nWorker Details:\n{worker_docstrings}"

    return system_prompt

def execute_steps_and_format(input_data: str, system_prompt: str, model: str, sections: Dict[str, str], allowed_workers: List[str]) -> str:
    logger.debug(f"Initial system prompt:\n{system_prompt}\n")
    logger.debug(f"Input data:\n{input_data}\n")

    conversation_history = []
    output = generate_with_history(input_data, system_prompt, model, conversation_history)
    conversation_history.append({"role": "assistant", "content": output})
    logger.debug(f"Initial output: {output}")

    if allowed_workers:
        output = process_worker_calls(output, allowed_workers)
        clean_system_prompt = remove_worker_info(system_prompt)
        enriched_prompt = f"Process the following data and continue the task:\n\nDATA:\n{output}"
        output = generate_with_history(enriched_prompt, clean_system_prompt, model, conversation_history)
        conversation_history.append({"role": "assistant", "content": output})
        logger.debug(f"Final output: {output}")

    refined_output = refine_output(output, sections, model, conversation_history)
    logger.debug("Refined output:")
    logger.debug(refined_output)

    return refined_output

def generate_with_history(prompt: str, system: str, model: str, conversation_history: List[Dict[str, str]]) -> str:
    messages = [{"role": "system", "content": system}] + conversation_history + [{"role": "user", "content": prompt}]
    response = requests.post(f'{API_BASE_URL}/api/chat',
                             json={
                                 "model": model,
                                 "messages": messages
                             },
                             stream=True)
    if response.status_code == 200:
        return process_streaming_response(response)
    else:
        raise Exception(f"Error in LLM API call: {response.text}")

def process_streaming_response(response) -> str:
    full_content = ""
    for line in response.iter_lines():
        if line:
            try:
                json_response = json.loads(line)
                if 'message' in json_response and 'content' in json_response['message']:
                    full_content += json_response['message']['content']
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON: {e}")
                logger.error(f"Problematic line: {line}")
    return full_content

def process_worker_calls(output: str, allowed_workers: List[str]) -> str:
    worker_calls = list(re.finditer(r"\[\[WORKER:\s*(\{.*?\})\s*\]\]", output))
    
    if not worker_calls:
        return output

    replacements = []
    for match in worker_calls:
        worker_call = match.group(1)
        try:
            worker_data = json.loads(worker_call)
            worker_name = worker_data.get('name')
            args = worker_data.get('args', {})
            
            logger.debug(f"Detected worker call: {worker_call}")
            logger.debug(f"Worker name: {worker_name}")
            logger.debug(f"Worker args: {args}")

            worker = get_worker(worker_name)
            if worker and worker_name in allowed_workers:
                logger.debug(f"Executing worker: {worker_name} with args: {args}")
                try:
                    worker_output = worker(**args) if args else worker()
                    logger.debug(f"Worker output: {json.dumps(worker_output)}")
                    replacement = f"[[WORKER_OUTPUT:{worker_name}, args={json.dumps(args)}]] {json.dumps(worker_output)} [[/WORKER_OUTPUT]]"
                except Exception as e:
                    logger.error(f"Error executing worker '{worker_name}': {str(e)}")
                    error_message = f"Error executing worker '{worker_name}': {str(e)}"
                    replacement = f"[[WORKER_ERROR:{worker_name}]] {error_message} [[/WORKER_ERROR]]"
            else:
                logger.error(f"Error: Worker '{worker_name}' not found or not allowed")
                error_message = f"Worker '{worker_name}' not found or not allowed"
                replacement = f"[[WORKER_ERROR:{worker_name}]] {error_message} [[/WORKER_ERROR]]"
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing worker call JSON: {str(e)}")
            error_message = f"Invalid worker call format: {str(e)}"
            replacement = f"[[WORKER_ERROR:JSON_PARSE]] {error_message} [[/WORKER_ERROR]]"
        
        replacements.append((match.start(), match.end(), replacement))
    
    for start, end, replacement in reversed(replacements):
        output = output[:start] + replacement + output[end:]
    
    logger.debug(f"Updated output after all worker replacements: {output}")
    return output

def refine_output(output: str, sections: Dict[str, str], model: str, conversation_history: List[Dict[str, str]]) -> str:
    messages = [{"role": "system", "content": sections['OUTPUT INSTRUCTIONS']}] + conversation_history + [{"role": "user", "content": output}]
    response = requests.post(f'{API_BASE_URL}/api/chat',
                             json={
                                 "model": model,
                                 "messages": messages
                             },
                             stream=True)
    if response.status_code == 200:
        return process_streaming_response(response)
    else:
        raise Exception(f"Error in refine output API call: {response.text}")

def get_worker_docstring(worker_name: str) -> str:
    worker = get_worker(worker_name)
    if worker:
        return worker.__doc__
    return f"No docstring available for worker '{worker_name}'."

def pipe_patterns(pattern_paths: List[str], initial_input: str, model: str, allowed_workers: List[str]) -> str:
    current_output = initial_input
    for pattern_path in pattern_paths:
        current_output = execute_pattern(pattern_path, current_output, model, allowed_workers)
    return current_output

def remove_worker_info(system_prompt: str) -> str:
    index = system_prompt.find("Available workers:")
    if index != -1:
        return system_prompt[:index].strip()
    return system_prompt