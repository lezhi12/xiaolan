import subprocess
import os
import time

SCREENSHOT_PATH = "/sdcard/screenshot.png"
LOCAL_SCREENSHOT_DIR = "./screenshots"

def ensure_screenshot_dir():
    if not os.path.exists(LOCAL_SCREENSHOT_DIR):
        os.makedirs(LOCAL_SCREENSHOT_DIR)

def execute_adb_command(command: str, device_id: str = None) -> tuple:
    adb_cmd = ["adb"]
    if device_id:
        adb_cmd.extend(["-s", device_id])
    
    # 正确处理包含空格的命令
    import shlex
    adb_cmd.extend(shlex.split(command))
    
    try:
        result = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=30)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timeout"
    except Exception as e:
        return -1, "", str(e)

def get_connected_devices() -> list:
    returncode, stdout, stderr = execute_adb_command("devices")
    if returncode != 0:
        return []
    
    devices = []
    lines = stdout.strip().split('\n')
    for line in lines[1:]:
        if '\t' in line:
            device_id, status = line.split('\t')
            if status == 'device':
                devices.append(device_id)
    return devices

def start_app(package_name: str, activity_name: str = None, device_id: str = None) -> dict:
    if activity_name:
        cmd = f"shell am start -n {package_name}/{activity_name}"
    else:
        # 确保包名被正确处理，即使包含空格
        import shlex
        safe_package = shlex.quote(package_name)
        cmd = f"shell monkey -p {safe_package} -c android.intent.category.LAUNCHER 1"
    
    returncode, stdout, stderr = execute_adb_command(cmd, device_id)
    
    return {
        "success": returncode == 0,
        "output": stdout,
        "error": stderr if returncode != 0 else None
    }

def take_screenshot(device_id: str = None) -> dict:
    ensure_screenshot_dir()
    
    returncode, stdout, stderr = execute_adb_command(f"shell screencap -p {SCREENSHOT_PATH}", device_id)
    if returncode != 0:
        return {"success": False, "error": stderr}
    
    timestamp = int(time.time() * 1000)
    local_path = os.path.join(LOCAL_SCREENSHOT_DIR, f"screenshot_{timestamp}.png")
    
    returncode, stdout, stderr = execute_adb_command(f"pull {SCREENSHOT_PATH} {local_path}", device_id)
    if returncode != 0:
        return {"success": False, "error": stderr}
    
    return {
        "success": True,
        "screenshot_path": local_path
    }

def tap_screen(x: int, y: int, device_id: str = None) -> dict:
    cmd = f"shell input tap {x} {y}"
    returncode, stdout, stderr = execute_adb_command(cmd, device_id)
    
    return {
        "success": returncode == 0,
        "x": x,
        "y": y,
        "output": stdout,
        "error": stderr if returncode != 0 else None
    }

def swipe_screen(start_x: int, start_y: int, end_x: int, end_y: int, duration: int = 300, device_id: str = None) -> dict:
    cmd = f"shell input swipe {start_x} {start_y} {end_x} {end_y} {duration}"
    returncode, stdout, stderr = execute_adb_command(cmd, device_id)
    
    return {
        "success": returncode == 0,
        "output": stdout,
        "error": stderr if returncode != 0 else None
    }

def input_text(text: str, device_id: str = None) -> dict:
    escaped_text = text.replace(' ', '%s').replace('&', '\\&')
    cmd = f"shell input text {escaped_text}"
    returncode, stdout, stderr = execute_adb_command(cmd, device_id)
    
    return {
        "success": returncode == 0,
        "output": stdout,
        "error": stderr if returncode != 0 else None
    }

def press_key(key_code: str, device_id: str = None) -> dict:
    cmd = f"shell input keyevent {key_code}"
    returncode, stdout, stderr = execute_adb_command(cmd, device_id)
    
    return {
        "success": returncode == 0,
        "output": stdout,
        "error": stderr if returncode != 0 else None
    }

def get_screen_size(device_id: str = None) -> dict:
    cmd = "shell wm size"
    returncode, stdout, stderr = execute_adb_command(cmd, device_id)
    
    if returncode != 0:
        return {"success": False, "error": stderr}
    
    try:
        size_str = stdout.strip().split(': ')[1]
        width, height = map(int, size_str.split('x'))
        return {
            "success": True,
            "width": width,
            "height": height
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

KEY_CODES = {
    "HOME": "KEYCODE_HOME",
    "BACK": "KEYCODE_BACK",
    "MENU": "KEYCODE_MENU",
    "ENTER": "KEYCODE_ENTER",
    "TAB": "KEYCODE_TAB",
    "VOLUME_UP": "KEYCODE_VOLUME_UP",
    "VOLUME_DOWN": "KEYCODE_VOLUME_DOWN",
    "POWER": "KEYCODE_POWER"
}
