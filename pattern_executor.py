import os
import logging
import re
from typing import Dict, List, Tuple
import requests
import json
from workers import get_worker, list_workers
import traceback

# set to logging.DEBUG for more verbose logging
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

    conversation_history = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": input_data}
    ]
    output = generate_with_history(input_data, system_prompt, model, conversation_history)
    conversation_history.append({"role": "assistant", "content": output})
    logger.debug(f"Initial output: {output}")

    if allowed_workers:
        worker_responses = process_worker_calls(output, allowed_workers)
        if worker_responses:  # Only process if there are worker responses
            system_prompt = remove_worker_info(system_prompt)
            enriched_prompt = f"Here are the worker responses to your previous requests:\n{worker_responses}\nPlease incorporate this information into your workflow and provide an updated response."
            logger.debug(f"Enriched prompt: {enriched_prompt}")
            conversation_history.append({"role": "user", "content": enriched_prompt})
            output = generate_with_history(enriched_prompt, system_prompt, model, conversation_history)
            conversation_history.append({"role": "assistant", "content": output})
            logger.debug(f"Updated output with worker information: {output}")
        else:
            logger.debug("No worker responses to process")

    if "OUTPUT INSTRUCTIONS" in sections:
        refinement_prompt = sections['OUTPUT INSTRUCTIONS']
        conversation_history.append({"role": "user", "content": refinement_prompt})
        output = generate_with_history(refinement_prompt, system_prompt, model, conversation_history)
        conversation_history.append({"role": "assistant", "content": output})
        logger.debug("Refined output:")
        logger.debug(output)
    else:
        logger.debug("No output refinement instructions found.")
    logger.debug("Full conversation history:")
    logger.debug(json.dumps(conversation_history, indent=2))
    logger.debug(f"Final output:\n{output}")
    return output

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
    
    logger.debug(f"Found {len(worker_calls)} worker call(s) in the output")
    
    if not worker_calls:
        logger.debug("No worker calls found in the output")
        return ""

    worker_responses = []
    for match in worker_calls:
        worker_call = match.group(1)
        logger.debug(f"Processing worker call: {worker_call}")
        try:
            # Use a custom JSON decoder to handle the nested quotes
            worker_data = json.loads(worker_call, strict=False)
            worker_name = worker_data.get('name')
            args = worker_data.get('args', {})
            
            logger.debug(f"Parsed worker call - Name: {worker_name}, Args: {args}")

            if worker_name not in allowed_workers:
                logger.warning(f"Worker '{worker_name}' is not in the list of allowed workers")
                continue

            worker = get_worker(worker_name)
            if worker:
                logger.debug(f"Executing worker: {worker_name} with args: {args}")
                try:
                    worker_output = worker(**args) if args else worker()
                    logger.debug(f"Worker output: {json.dumps(worker_output)}")
                    reply = (
                        f"[[WORKER_RESPONSE]]\n"
                        f"Worker: {worker_name}\n"
                        f"Arguments: {json.dumps(args)}\n"
                        f"Output: {json.dumps(worker_output)}\n"
                        f"[[/WORKER_RESPONSE]]"
                    )
                    worker_responses.append(reply)
                except Exception as e:
                    logger.error(f"Error executing worker '{worker_name}': {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    error_message = f"Error executing worker '{worker_name}': {str(e)}"
                    reply = (
                        f"[[WORKER_ERROR]]\n"
                        f"Worker: {worker_name}\n"
                        f"Error: {error_message}\n"
                        f"Traceback: {traceback.format_exc()}\n"
                        f"[[/WORKER_ERROR]]"
                    )
                    worker_responses.append(reply)
            else:
                logger.error(f"Worker '{worker_name}' not found")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing worker call JSON: {str(e)}")
            logger.error(f"Problematic worker call: {worker_call}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    logger.debug(f"Processed {len(worker_responses)} worker response(s)")
    return "\n".join(worker_responses)

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
