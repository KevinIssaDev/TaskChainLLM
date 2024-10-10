import logging
import markdown
import re
from typing import Dict, List, Tuple
import requests
import json
from workers import get_worker, list_workers

logging.basicConfig(level=logging.DEBUG)  # logging.INFO to reduce verbosity, logging.DEBUG to increase verbosity
logger = logging.getLogger(__name__)


def list_models() -> List[str]:
    response = requests.get('http://localhost:11434/api/tags')
    if response.status_code == 200:
        models = response.json()
        return [model['name'] for model in models['models']]
    else:
        raise Exception(f"Error fetching models: {response.text}")


def execute_pattern(pattern_path: str, input_data: str, model: str, allowed_workers: List[str]) -> str:
    with open(pattern_path, 'r') as file:
        pattern_content = file.read()

    sections = extract_sections_from_markdown(pattern_content)
    system_prompt = f"{sections['IDENTITY and PURPOSE']}\n\n"
    system_prompt += "Follow these steps:\n"
    steps_list = [step.strip()[2:] for step in sections['STEPS'].split(
        '\n') if step.strip().startswith('- ')]
    system_prompt += "\n".join(f"{i+1}. {step}" for i,
                               step in enumerate(steps_list))

    # Filter available workers
    available_workers = [worker for worker in list_workers() if worker in allowed_workers]
    if available_workers:
        system_prompt += f"\n\nAvailable workers: {', '.join(available_workers)}"
        system_prompt += "\nTo use a worker, include [[WORKER:worker_name]] in your response."
        worker_docstrings = "\n".join([f"{worker}:\n{get_worker_docstring(worker)}" for worker in available_workers])
        system_prompt += f"\n\nWorker Details:\n{worker_docstrings}"

    logger.debug(f"Available workers: {available_workers}")

    output = execute_steps_and_format(
        input_data, system_prompt, model, sections, allowed_workers)

    return output


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


def execute_steps_and_format(input_data: str, system_prompt: str, model: str, sections: Dict[str, str], allowed_workers: List[str]) -> str:
    logger.debug(f"Initial system prompt:\n{system_prompt}\n")
    logger.debug(f"Input data:\n{input_data}\n")

    conversation_history = []
    
    def generate_with_history(prompt: str, system: str):
        messages = [{"role": "system", "content": system}] + conversation_history + [{"role": "user", "content": prompt}]
        response = requests.post('http://localhost:11434/api/chat',
                                 json={
                                     "model": model,
                                     "messages": messages
                                 },
                                 stream=True)
        if response.status_code == 200:
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
        else:
            raise Exception(f"Error in LLM API call: {response.text}")

    output = generate_with_history(input_data, system_prompt)
    conversation_history.append({"role": "assistant", "content": output})
    logger.debug(f"Initial output: {output}")

    if allowed_workers:
        while "[[WORKER:" in output:
            start = output.index("[[WORKER:")
            end = output.index("]]", start) + 2
            worker_call = output[start:end]
            worker_name, args = parse_worker_call(worker_call)
            logger.debug(f"Detected worker call: {worker_call}")
            logger.debug(f"Worker name: {worker_name}")
            logger.debug(f"Worker args: {args}")

            worker = get_worker(worker_name)
            if worker:
                logger.debug(f"Executing worker: {worker_name} with args: {args}")
                worker_output = worker(**args)
                logger.debug(f"Worker output: {json.dumps(worker_output)}")

                # Replace the worker call with its output
                output = output[:start] + f"[[WORKER_OUTPUT:{worker_name}, args={json.dumps(args)}]] " + json.dumps(worker_output) + " [[/WORKER_OUTPUT]]" + output[end:]
                logger.debug(f"Updated output after worker replacement: {output}")
            else:
                logger.error(f"Error: Worker '{worker_name}' not found")
                output = output.replace(worker_call, f"Error: Worker '{worker_name}' not found")

        # Remove worker information from system prompt
        clean_system_prompt = remove_worker_info(system_prompt)
    
        # After all worker calls have been replaced, send the updated output back to the LLM
        enriched_prompt = f"Process the following data and continue the task:\n\nDATA:\n{output}"
        output = generate_with_history(enriched_prompt, clean_system_prompt)
        conversation_history.append({"role": "assistant", "content": output})
        logger.debug(f"Final output: {output}")

    # Always refine the output before returning
    refined_output = refine_output(output, sections, model, conversation_history)
    logger.debug("Refined output:")
    logger.debug(refined_output)

    return refined_output


def refine_output(output: str, sections: Dict[str, str], model: str, conversation_history: List[Dict[str, str]]) -> str:
    messages = [{"role": "system", "content": sections['OUTPUT INSTRUCTIONS']}] + conversation_history + [{"role": "user", "content": output}]
    response = requests.post('http://localhost:11434/api/chat',
                             json={
                                 "model": model,
                                 "messages": messages
                             },
                             stream=True)
    if response.status_code == 200:
        refined_content = ""
        for line in response.iter_lines():
            if line:
                try:
                    json_response = json.loads(line)
                    if 'message' in json_response and 'content' in json_response['message']:
                        refined_content += json_response['message']['content']
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON in refine_output: {e}")
                    logger.error(f"Problematic line: {line}")
        return refined_content
    else:
        raise Exception(f"Error in refine output API call: {response.text}")


def get_worker_docstring(worker_name: str) -> str:
    worker = get_worker(worker_name)
    if worker:
        return worker.__doc__
    return f"No docstring available for worker '{worker_name}'."


def parse_worker_call(worker_call: str) -> Tuple[str, dict]:
    # Example: [[WORKER:weather_api, location="London"]]
    match = re.match(r"\[\[WORKER:(\w+),\s*(.*)\]\]", worker_call)
    if match:
        worker_name = match.group(1)
        args_str = match.group(2)
        args = dict(re.findall(r'(\w+)="([^"]+)"', args_str))
        return worker_name, args  # ("weather_api", {"location": "London"})
    return "", {}


def pipe_patterns(pattern_paths: List[str], initial_input: str, model: str) -> str:
    current_output = initial_input
    for pattern_path in pattern_paths:
        current_output = execute_pattern(pattern_path, current_output, model)
    return current_output


def remove_worker_info(system_prompt: str) -> str:
    # Remove everything from "Available workers" onwards
    index = system_prompt.find("Available workers:")
    if index != -1:
        return system_prompt[:index].strip()
    return system_prompt  # Return the original prompt if "Available workers:" is not found
