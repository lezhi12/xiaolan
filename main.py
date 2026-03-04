import os
import re
import time
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from tools import (
    get_connected_devices,
    start_app,
    take_screenshot,
    tap_screen,
    swipe_screen,
    input_text,
    press_key,
    KEY_CODES,
    ui_grounding,
    call_vision_model,
    process_grounding_result,
    get_image_dimensions,
    SessionManager
)

MAX_STEPS = 20
STEP_DELAY = 1.5
APP_START_DELAY = 5  # 应用启动后的等待时间（秒）

APP_PACKAGE_MAP = {
    "小红书": "com.xingin.xhs",
    "微信": "com.tencent.mm",
    "抖音": "com.ss.android.ugc.aweme",
    "淘宝": "com.taobao.taobao",
    "支付宝": "com.eg.android.AlipayGphone",
    "京东": "com.jingdong.app.mall",
    "美团": "com.sankuai.meituan",
    "拼多多": "com.xunmeng.pinduoduo",
    "bilibili": "tv.danmaku.bili",
    "b站": "tv.danmaku.bili",
    "omininotes":"it.feio.android.omninotes",
    "OmniNotes":"it.feio.android.omninotes",
    "Omni Notes":"it.feio.android.omninotes"
}

SYSTEM_PROMPT = """你是一个安卓手机自动化操作助手，使用ReAct范式工作。

你可以使用以下工具：
1. start_app[app_name] - 启动应用，例如：start_app[小红书]
2. tap_element[element_description] - 点击屏幕上的元素，例如：tap_element[首页tab]
3. swipe[direction:amplitude] - 滑动屏幕，direction可以是up/down/left/right，amplitude可以是small/normal/large，例如：swipe[up:small] 表示小幅度向上滑动
4. press_key[key_name] - 按键操作，key_name可以是HOME/BACK/MENU，例如：press_key[BACK]
5. wait[seconds] - 等待指定秒数，例如：wait[2]
6. input_text[text] - 输入文本，例如：input_text[helloworld]
7. finish - 任务完成

工作流程：
1. Thought: 分析当前任务和屏幕状态
2. Action: 选择合适的工具执行操作
3. Observation: 观察操作结果

请严格按照以下格式回复：
Thought: [你的思考过程，保持简洁，控制在2-3句话]
Action: [工具名称[参数]]

注意：
- 每次只需要输出一个Thought和一个Action
- 点击元素时，系统会自动截图并定位元素位置
- 如果找不到目标元素，可以尝试滑动屏幕或返回上一页
- 任务完成后请使用finish工具结束任务
- 请保持思考过程简洁明了，避免冗长的分析，以节省token消耗
- 直接输出明确的操作步骤，不要包含无关的思考或疑问"""

class AndroidAgent:
    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id
        self.current_screenshot = None
        self.step_count = 0
        self.task_completed = False
        self.session: Optional[SessionManager] = None
        self.current_task = ""
        self.history = []
        
    def connect_device(self) -> bool:
        devices = get_connected_devices()
        if not devices:
            msg = "错误：未检测到已连接的安卓设备"
            print(msg)
            if self.session:
                self.session.log_agent(msg, "ERROR")
            return False
        
        if self.device_id:
            if self.device_id in devices:
                msg = f"已连接设备：{self.device_id}"
                print(msg)
                if self.session:
                    self.session.log_agent(msg)
                return True
            else:
                msg = f"错误：设备 {self.device_id} 未连接"
                print(msg)
                if self.session:
                    self.session.log_agent(msg, "ERROR")
                return False
        else:
            self.device_id = devices[0]
            msg = f"已自动选择设备：{self.device_id}"
            print(msg)
            if self.session:
                self.session.log_agent(msg)
            return True
    
    def capture_screen(self) -> bool:
        result = take_screenshot(self.device_id)
        if result["success"]:
            self.current_screenshot = result["screenshot_path"]
            msg = f"截图已保存：{self.current_screenshot}"
            print(msg)
            if self.session:
                self.session.log_agent(msg)
                self.session.save_screenshot(
                    self.current_screenshot, 
                    self.step_count,
                    f"步骤{self.step_count}截图"
                )
            return True
        else:
            msg = f"截图失败：{result.get('error', '未知错误')}"
            print(msg)
            if self.session:
                self.session.log_agent(msg, "ERROR")
            return False
    
    def parse_action(self, response: str) -> dict:
        # 先尝试匹配带参数的动作
        action_pattern = r"Action:\s*(\w+)\[([^\]]*)\]"
        match = re.search(action_pattern, response)
        
        if match:
            return {
                "tool": match.group(1),
                "param": match.group(2)
            }
        
        # 再尝试匹配不带参数的动作（如 finish）
        no_param_pattern = r"Action:\s*(\w+)\s*$"
        match = re.search(no_param_pattern, response)
        
        if match:
            return {
                "tool": match.group(1),
                "param": ""
            }
        
        return None
    
    def execute_action(self, action: dict) -> str:
        tool = action["tool"]
        param = action["param"]
        
        self.session.log_agent(f"执行动作: {tool}[{param}]")
        
        if tool == "start_app":
            package_name = APP_PACKAGE_MAP.get(param, param)
            result = start_app(package_name, device_id=self.device_id)
            if result["success"]:
                time.sleep(APP_START_DELAY)
                msg = f"已启动应用：{param}"
                self.session.log_agent(msg)
                return msg
            else:
                msg = f"启动应用失败：{result.get('error', '未知错误')}"
                self.session.log_agent(msg, "ERROR")
                return msg
        
        elif tool == "tap_element":
            if not self.current_screenshot:
                self.capture_screen()
            
            grounding_result = ui_grounding(self.current_screenshot, param)
            if not grounding_result["success"]:
                msg = f"UI定位失败：{grounding_result.get('error', '未知错误')}"
                self.session.log_agent(msg, "ERROR")
                return msg
            
            usage = grounding_result.get("usage", {})
            usage_str = f"Token消耗: {usage.get('total_tokens', 0)} (提示: {usage.get('prompt_tokens', 0)}, 完成: {usage.get('completion_tokens', 0)})"
            print(f"\n{usage_str}")
            
            self.session.save_llm_output(
                self.step_count, 
                f"UI Grounding: {param}",
                grounding_result["content"],
                "grounding",
                usage
            )
            
            # 保存usage信息到日志
            self.session.log_agent(usage_str)
            
            coord_result = process_grounding_result(
                grounding_result["content"],
                self.current_screenshot
            )
            
            if not coord_result["success"]:
                msg = f"坐标转换失败：{coord_result.get('error', '未知错误')}"
                self.session.log_agent(msg, "ERROR")
                return msg
            
            center = coord_result["center_point"]
            
            self.session.save_grounding_result(
                self.step_count,
                param,
                coord_result["normalized_bbox"],
                coord_result["real_bbox"],
                center,
                True,
                usage
            )
            
            tap_result = tap_screen(center["x"], center["y"], self.device_id)
            
            if tap_result["success"]:
                time.sleep(STEP_DELAY)
                msg = f"已点击元素「{param}」，坐标：({center['x']}, {center['y']})"
                self.session.log_agent(msg)
                return msg
            else:
                msg = f"点击失败：{tap_result.get('error', '未知错误')}"
                self.session.log_agent(msg, "ERROR")
                return msg
        
        elif tool == "swipe":
            if not self.current_screenshot:
                self.capture_screen()
            
            dims = get_image_dimensions(self.current_screenshot)
            if not dims["success"]:
                return "无法获取屏幕尺寸"
            
            w, h = dims["width"], dims["height"]
            center_x, center_y = w // 2, h // 2
            
            # 解析参数，支持 swipe[方向:幅度] 格式，如 swipe[up:small]
            parts = param.split(":")
            direction = parts[0]
            amplitude = parts[1] if len(parts) > 1 else "normal"
            
            # 根据幅度设置滑动距离
            if amplitude == "small":
                offset = h // 6  # 小幅度滑动
            elif amplitude == "large":
                offset = h // 2  # 大幅度滑动
            else:
                offset = h // 3  # 正常幅度滑动
            
            directions = {
                "up": (center_x, center_y + offset, center_x, center_y - offset),
                "down": (center_x, center_y - offset, center_x, center_y + offset),
                "left": (center_x + offset, center_y, center_x - offset, center_y),
                "right": (center_x - offset, center_y, center_x + offset, center_y)
            }
            
            if direction in directions:
                sx, sy, ex, ey = directions[direction]
                result = swipe_screen(sx, sy, ex, ey, device_id=self.device_id)
                if result["success"]:
                    time.sleep(STEP_DELAY)
                    msg = f"已执行{direction}滑动（{amplitude}幅度）"
                    self.session.log_agent(msg)
                    return msg
                else:
                    msg = f"滑动失败：{result.get('error', '未知错误')}"
                    self.session.log_agent(msg, "ERROR")
                    return msg
            else:
                msg = f"未知的滑动方向：{direction}"
                self.session.log_agent(msg, "ERROR")
                return msg
        
        elif tool == "press_key":
            key_code = KEY_CODES.get(param.upper())
            if key_code:
                result = press_key(key_code, self.device_id)
                if result["success"]:
                    time.sleep(STEP_DELAY)
                    msg = f"已按下{param}键"
                    self.session.log_agent(msg)
                    return msg
                else:
                    msg = f"按键失败：{result.get('error', '未知错误')}"
                    self.session.log_agent(msg, "ERROR")
                    return msg
            else:
                msg = f"未知的按键：{param}"
                self.session.log_agent(msg, "ERROR")
                return msg
        
        elif tool == "input_text":
            result = input_text(param, device_id=self.device_id)
            if result["success"]:
                time.sleep(STEP_DELAY)
                msg = f"已输入文本：{param}"
                self.session.log_agent(msg)
                return msg
            else:
                msg = f"输入文本失败：{result.get('error', '未知错误')}"
                self.session.log_agent(msg, "ERROR")
                return msg
        
        elif tool == "wait":
            try:
                seconds = int(param)
                time.sleep(seconds)
                msg = f"已等待{seconds}秒"
                self.session.log_agent(msg)
                return msg
            except ValueError:
                msg = f"无效的等待时间：{param}"
                self.session.log_agent(msg, "ERROR")
                return msg
        
        elif tool == "finish":
            self.task_completed = True
            msg = "任务已完成"
            self.session.log_agent(msg)
            return msg
        
        else:
            msg = f"未知的工具：{tool}"
            self.session.log_agent(msg, "ERROR")
            return msg
    
    def get_llm_decision(self, task: str) -> str:
        if not self.current_screenshot:
            self.capture_screen()
        
        # 构建历史记录
        history_str = ""
        if self.history:
            history_str = "\n历史操作：\n"
            for i, (thought, action, observation) in enumerate(self.history):
                history_str += f"步骤 {i+1}:\n"
                history_str += f"  Thought: {thought}\n"
                history_str += f"  Action: {action}\n"
                history_str += f"  Observation: {observation}\n"
        
        prompt = f"""{SYSTEM_PROMPT}

当前任务：{task}
当前步骤：{self.step_count}/{MAX_STEPS}
{history_str}
请分析当前屏幕截图，决定下一步操作。"""
        
        result = call_vision_model(self.current_screenshot, prompt)
        if result["success"]:
            usage = result.get("usage", {})
            usage_str = f"Token消耗: {usage.get('total_tokens', 0)} (提示: {usage.get('prompt_tokens', 0)}, 完成: {usage.get('completion_tokens', 0)})"
            print(f"\n{usage_str}")
            
            self.session.save_llm_output(
                self.step_count,
                prompt,
                result["content"],
                "decision",
                usage
            )
            
            # 保存usage信息到日志
            self.session.log_agent(usage_str)
            
            return result["content"]
        else:
            msg = f"LLM调用失败：{result.get('error', '未知错误')}"
            self.session.log_agent(msg, "ERROR")
            return f"Thought: LLM调用失败，需要重试\nAction: wait[1]"
    
    def run(self, task: str):
        self.current_task = task
        self.session = SessionManager()
        session_id = self.session.create_session()
        
        print(f"\n{'='*60}")
        print(f"开始执行任务：{task}")
        print(f"Session ID: {session_id}")
        print(f"{'='*60}\n")
        
        self.session.log_agent(f"开始执行任务: {task}")
        self.session.log_agent(f"Session ID: {session_id}")
        
        if not self.connect_device():
            self.session.finish_session("failed", task)
            return
        
        while self.step_count < MAX_STEPS and not self.task_completed:
            self.step_count += 1
            print(f"\n--- 步骤 {self.step_count} ---")
            self.session.log_agent(f"===== 步骤 {self.step_count} =====")
            
            if not self.capture_screen():
                print("截图失败，等待重试...")
                time.sleep(1)
                continue
            
            response = self.get_llm_decision(task)
            print(f"\nLLM响应：\n{response}")
            
            action = self.parse_action(response)
            if action:
                observation = self.execute_action(action)
                print(f"\n执行结果：{observation}")
                
                # 提取Thought
                thought_pattern = r"Thought:\s*([^\n]+)"
                thought_match = re.search(thought_pattern, response)
                thought = thought_match.group(1) if thought_match else ""
                
                # 提取Action
                action_str = f"{action['tool']}[{action['param']}]"
                
                # 保存到历史记录
                self.history.append((thought, action_str, observation))
            else:
                print("\n无法解析动作，跳过当前步骤")
                self.session.log_agent("无法解析动作，跳过当前步骤", "WARN")
            
            time.sleep(0.5)
        
        if self.task_completed:
            print(f"\n{'='*60}")
            print("任务执行完成！")
            print(f"{'='*60}")
            self.session.finish_session("completed", task)
        else:
            print(f"\n已达到最大步骤数({MAX_STEPS})，任务可能未完成")
            self.session.finish_session("max_steps_reached", task)
        
        # 打印 token 消耗统计
        token_usage = self.session.token_usage
        print(f"\nToken消耗统计:")
        print(f"输入token: {token_usage['prompt_tokens']}")
        print(f"输出token: {token_usage['completion_tokens']}")
        print(f"总token: {token_usage['total_tokens']}")
        
        print(f"\n日志保存在：{self.session.session_dir}")

def main():
    print("安卓自动化助手 - 基于ReAct范式")
    print("-" * 40)
    
    task = input("请输入任务描述（例如：打开小红书，点击首页tab）：").strip()
    
    if not task:
        print("任务描述不能为空")
        return
    
    agent = AndroidAgent()
    agent.run(task)

if __name__ == "__main__":
    main()
