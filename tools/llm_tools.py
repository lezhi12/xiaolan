import os
import base64
from openai import OpenAI

MODEL_NAME = "doubao-seed-1-6-vision-250815"

def get_client() -> OpenAI:
    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        raise ValueError("ARK_API_KEY environment variable not set")
    
    return OpenAI(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=api_key,
    )

def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def call_vision_model(image_path: str, prompt: str) -> dict:
    try:
        client = get_client()
        base64_image = encode_image_to_base64(image_path)
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]
        )
        
        usage_info = {}
        if hasattr(response, 'usage') and response.usage:
            usage_info = {
                "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0),
                "completion_tokens": getattr(response.usage, 'completion_tokens', 0),
                "total_tokens": getattr(response.usage, 'total_tokens', 0)
            }
        
        return {
            "success": True,
            "content": response.choices[0].message.content,
            "usage": usage_info
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "usage": {}
        }

def ui_grounding(image_path: str, element_description: str) -> dict:
    prompt = f"请框出图片中「{element_description}」的位置，输出bounding box的坐标，格式为<bbox>x_min y_min x_max y_max</bbox>"
    
    return call_vision_model(image_path, prompt)

def analyze_task(image_path: str, task_description: str) -> dict:
    prompt = f"""你是一个安卓手机操作助手。请分析当前屏幕截图，根据任务描述判断下一步操作。

任务描述：{task_description}

请分析当前屏幕状态，判断：
1. 任务是否已经完成？
2. 如果未完成，下一步应该执行什么操作？需要点击哪个UI元素？

请用中文回答，格式如下：
任务状态：[已完成/未完成]
下一步操作：[具体操作描述]
目标元素：[需要点击的元素描述，如果需要点击的话]"""

    return call_vision_model(image_path, prompt)
