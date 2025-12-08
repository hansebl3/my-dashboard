import requests
import logging
import json
import os
import subprocess
from modules.metrics_manager import DataUsageTracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMManager:
    def __init__(self, ollama_host="http://2080ti:11434"):
        self.ollama_host = ollama_host
        self.ssh_key_path = '/home/ross/.ssh/id_ed25519'
        self.ssh_host = 'ross@2080ti'

    def check_connection(self):
        try:
            resp = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
            if resp.status_code == 200:
                return True, "Connected"
            return False, f"Status Code: {resp.status_code}"
        except Exception as e:
            return False, str(e)

    def get_models(self):
        try:
            resp = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m['name'] for m in resp.json().get('models', [])]
                return models
            return []
        except Exception as e:
            logger.error(f"Error fetching models: {e}")
            return []

    def generate_response(self, prompt, model, stream=False):
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": stream
            }
            logger.info(f"Sending request to Ollama: {model}")
            response = requests.post(f"{self.ollama_host}/api/generate", json=payload, stream=stream, timeout=120)
            response.raise_for_status()

            # Track TX (Approximate payload size)
            tracker = DataUsageTracker()
            tracker.add_tx(len(json.dumps(payload)))

            if not stream:
                resp_json = response.json()
                res_text = resp_json.get("response", "")
                
                # Track RX
                tracker.add_rx(len(response.content))
                
                return res_text
            else:
                # Streaming not fully implemented/used yet, but if used:
                # We'd need to count bytes of chunks.
                # For now assume mostly non-stream for summary.
                # The original code would return the full response after consuming the stream.
                # For now, we'll return a placeholder or handle it as non-stream for tracking purposes.
                # If actual streaming is implemented, this part needs to be revised to process chunks.
                result = response.json() # Assuming the stream is consumed and a final JSON is available
                res_text = result.get("response", "No response generated.")
                tracker.add_rx(len(response.content)) # Track RX for the full response
                return res_text
        except Exception as e:
            logger.error(f"Ollama Error for {model}: {e}")
            return f"Error generating response: {e}"

    def get_gpu_info(self):
        """Fetch GPU info (count/names) from 2080ti via SSH"""
        try:
            cmd = [
                'ssh', 
                '-o', 'StrictHostKeyChecking=no', 
                '-o', 'UserKnownHostsFile=/dev/null',
                '-o', 'ConnectTimeout=2',
                '-i', self.ssh_key_path,
                self.ssh_host, 
                'nvidia-smi --query-gpu=name --format=csv,noheader'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                # Output: "GeForce RTX 2080 Ti\nGeForce RTX 2080 Ti"
                gpus = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                return gpus
            return []
        except Exception as e:
            logger.error(f"GPU Info Error: {e}")
            return []

    def get_config(self):
        config_path = "llm_config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        return {}

    def update_config(self, key, value):
        config_path = "llm_config.json"
        try:
            data = self.get_config()
            data[key] = value
            with open(config_path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
