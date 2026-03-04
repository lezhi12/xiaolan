from PIL import Image

def convert_bbox_to_real_coords(x_min: int, y_min: int, x_max: int, y_max: int, image_width: int, image_height: int) -> dict:
    x_min_real = int(x_min * image_width / 1000)
    y_min_real = int(y_min * image_height / 1000)
    x_max_real = int(x_max * image_width / 1000)
    y_max_real = int(y_max * image_height / 1000)
    
    return {
        "x_min": x_min_real,
        "y_min": y_min_real,
        "x_max": x_max_real,
        "y_max": y_max_real
    }

def get_center_point(x_min: int, y_min: int, x_max: int, y_max: int) -> dict:
    center_x = (x_min + x_max) // 2
    center_y = (y_min + y_max) // 2
    
    return {
        "x": center_x,
        "y": center_y
    }

def get_image_dimensions(image_path: str) -> dict:
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            return {
                "success": True,
                "width": width,
                "height": height
            }
    except Exception as e:
        return {"success": False, "error": f"Cannot read image: {image_path}, {str(e)}"}

def parse_bbox_from_response(response: str) -> dict:
    bbox_tag_start = "<bbox>"
    bbox_tag_end = "</bbox>"
    
    start_idx = response.find(bbox_tag_start)
    end_idx = response.find(bbox_tag_end)
    
    if start_idx == -1 or end_idx == -1:
        return {"success": False, "error": "No bbox tag found in response"}
    
    coords_str = response[start_idx + len(bbox_tag_start):end_idx].strip()
    
    try:
        coords = list(map(int, coords_str.split()))
        if len(coords) != 4:
            return {"success": False, "error": f"Expected 4 coordinates, got {len(coords)}"}
        
        return {
            "success": True,
            "x_min": coords[0],
            "y_min": coords[1],
            "x_max": coords[2],
            "y_max": coords[3]
        }
    except ValueError as e:
        return {"success": False, "error": f"Failed to parse coordinates: {str(e)}"}

def process_grounding_result(response: str, image_path: str) -> dict:
    parse_result = parse_bbox_from_response(response)
    if not parse_result["success"]:
        return parse_result
    
    dim_result = get_image_dimensions(image_path)
    if not dim_result["success"]:
        return dim_result
    
    real_coords = convert_bbox_to_real_coords(
        parse_result["x_min"],
        parse_result["y_min"],
        parse_result["x_max"],
        parse_result["y_max"],
        dim_result["width"],
        dim_result["height"]
    )
    
    center = get_center_point(
        real_coords["x_min"],
        real_coords["y_min"],
        real_coords["x_max"],
        real_coords["y_max"]
    )
    
    return {
        "success": True,
        "normalized_bbox": {
            "x_min": parse_result["x_min"],
            "y_min": parse_result["y_min"],
            "x_max": parse_result["x_max"],
            "y_max": parse_result["y_max"]
        },
        "real_bbox": real_coords,
        "center_point": center,
        "image_dimensions": {
            "width": dim_result["width"],
            "height": dim_result["height"]
        }
    }
