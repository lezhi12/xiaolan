import os
import json
import shutil
from datetime import datetime
from typing import Optional

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

class SessionManager:
    def __init__(self):
        self.session_id: Optional[str] = None
        self.session_dir: Optional[str] = None
        self.agent_log_file: Optional[str] = None
        self.llm_output_dir: Optional[str] = None
        self.screenshot_dir: Optional[str] = None
        self.step_count: int = 0
        self.token_usage: dict = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
    def create_session(self) -> str:
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(LOGS_DIR, self.session_id)
        
        os.makedirs(self.session_dir, exist_ok=True)
        
        self.agent_log_file = os.path.join(self.session_dir, "agent.log")
        self.llm_output_dir = os.path.join(self.session_dir, "llm_outputs")
        self.screenshot_dir = os.path.join(self.session_dir, "screenshots")
        
        os.makedirs(self.llm_output_dir, exist_ok=True)
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        self._write_session_info()
        self.step_count = 0
        
        return self.session_id
    
    def _write_session_info(self):
        info = {
            "session_id": self.session_id,
            "created_at": datetime.now().isoformat(),
            "status": "running"
        }
        info_file = os.path.join(self.session_dir, "session_info.json")
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    
    def log_agent(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] [{level}] {message}\n"
        
        with open(self.agent_log_file, 'a', encoding='utf-8') as f:
            f.write(log_line)
    
    def save_llm_output(self, step: int, prompt: str, response: str, action_type: str = "decision", usage: dict = None):
        self.step_count = step
        
        # 累计 token 消耗
        if usage:
            self.token_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
            self.token_usage["completion_tokens"] += usage.get("completion_tokens", 0)
            self.token_usage["total_tokens"] += usage.get("total_tokens", 0)
        
        output = {
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "action_type": action_type,
            "prompt": prompt,
            "response": response,
            "usage": usage or {}
        }
        
        filename = f"step_{step:03d}_{action_type}.json"
        output_file = os.path.join(self.llm_output_dir, filename)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        return output_file
    
    def save_screenshot(self, source_path: str, step: int, description: str = "") -> str:
        if not os.path.exists(source_path):
            return ""
        
        ext = os.path.splitext(source_path)[1]
        filename = f"step_{step:03d}{ext}"
        dest_path = os.path.join(self.screenshot_dir, filename)
        
        shutil.copy2(source_path, dest_path)
        
        meta_file = os.path.join(self.screenshot_dir, f"step_{step:03d}_meta.json")
        meta = {
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "description": description,
            "original_path": source_path
        }
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        return dest_path
    
    def save_grounding_result(self, step: int, element_description: str, 
                               bbox_normalized: dict, bbox_real: dict, 
                               center_point: dict, success: bool, usage: dict = None):
        result = {
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "element_description": element_description,
            "success": success,
            "bbox_normalized": bbox_normalized,
            "bbox_real": bbox_real,
            "center_point": center_point,
            "usage": usage or {}
        }
        
        filename = f"step_{step:03d}_grounding.json"
        output_file = os.path.join(self.llm_output_dir, filename)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    def finish_session(self, status: str = "completed", task: str = ""):
        info = {
            "session_id": self.session_id,
            "created_at": self.session_id,
            "finished_at": datetime.now().isoformat(),
            "status": status,
            "total_steps": self.step_count,
            "task": task,
            "token_usage": self.token_usage
        }
        info_file = os.path.join(self.session_dir, "session_info.json")
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        
        usage_str = f"Token消耗统计: 输入={self.token_usage['prompt_tokens']}, 输出={self.token_usage['completion_tokens']}, 总计={self.token_usage['total_tokens']}"
        self.log_agent(usage_str)
        self.log_agent(f"Session finished with status: {status}")
    
    def get_session_summary(self) -> dict:
        return {
            "session_id": self.session_id,
            "session_dir": self.session_dir,
            "step_count": self.step_count
        }
