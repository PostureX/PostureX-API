import asyncio
import websockets
import json
import itertools
import numpy as np
import math
import cv2
import base64
from flask_jwt_extended import decode_token
import jwt
from jwt.exceptions import InvalidTokenError
from mmpose.apis import MMPoseInferencer
from websocket_config import (
    WEBSOCKET_HOST,
    MODEL_CONFIGS,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    PIXELS_TO_CM_HORIZONTAL,
    PIXELS_TO_CM_VERTICAL,
)

# Load model per gpu at startup for multiple models
NUM_GPUS = 4
model_names = list(MODEL_CONFIGS.keys())
inferencers = {
    model_name: (
        [
            MMPoseInferencer(
                MODEL_CONFIGS[model_name]["model_config"],
                pose2d_weights=MODEL_CONFIGS[model_name]["checkpoint_path"],
                device=f"cuda:{i}",
            )
            for i in range(NUM_GPUS)
        ]
        if MODEL_CONFIGS[model_name]["model_config"] is not None
        else None
    )
    for model_name in model_names
}

gpu_cycle = itertools.cycle(range(NUM_GPUS))


async def authenticate_websocket(websocket):
    """Authenticate WebSocket connection using JWT token from query parameters"""
    try:
        # Extract token from query parameters
        token = None

        path = websocket.request.path

        if path and "?" in path:
            from urllib.parse import parse_qs, urlparse

            parsed_url = urlparse(path)
            query_params = parse_qs(parsed_url.query)
            if "token" in query_params:
                token = query_params["token"][0]
        else:
            return {"error": "No query parameters found in path"}

        if not token:
            error_msg = f"No JWT token found in query parameters. Please provide token as ?token=your_ws_token. Path was: {path}"
            await websocket.send(json.dumps({"error": error_msg}))
            return False

        # Validate JWT token
        try:
            decoded_token = jwt.decode(
                token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
            )
            user_id = decoded_token.get("sub")  # 'sub' is the subject (user_id)

            if not user_id:
                await websocket.send(json.dumps({"error": "Invalid token: no user ID"}))
                return False

            ws_auth = decoded_token.get("ws_auth", False)
            one_time = decoded_token.get("one_time", False)

            if ws_auth and one_time:
                await websocket.send(
                    json.dumps({"status": "authenticated", "user_id": user_id})
                )
                return True
            else:
                await websocket.send(
                    json.dumps({"status": "unauthenticated", "user_id": user_id})
                )
                return False

        except InvalidTokenError as e:
            await websocket.send(json.dumps({"error": f"Invalid JWT token: {str(e)}"}))
            return False

    except Exception as e:
        await websocket.send(json.dumps({"error": f"Authentication failed: {str(e)}"}))
        return False


def decode_image_from_base64(img_b64):
    """Decode base64 image string to opencv/numpy image format"""
    try:
        # Decode base64 string to bytes
        img_bytes = base64.b64decode(img_b64)

        # Convert bytes to numpy array
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)

        # Decode image using OpenCV
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        return img
    except Exception:
        return None


def convert_pixels_to_cm(pixel_distance, direction="horizontal"):
    """
    Convert pixel distance to centimeters based on calibration
    
    Args:
        pixel_distance: Distance in pixels
        direction: "horizontal" or "vertical" - determines which conversion ratio to use
    
    Returns:
        Distance in centimeters
    """
    if direction == "horizontal":
        return pixel_distance * PIXELS_TO_CM_HORIZONTAL
    elif direction == "vertical":
        return pixel_distance * PIXELS_TO_CM_VERTICAL
    else:
        # Default to horizontal if direction is unclear
        return pixel_distance * PIXELS_TO_CM_HORIZONTAL


def calculate_vector_magnitude(point1, point2):
    """
    Calculate the magnitude of the vector between two points.
    point1 and point2 should be like (x, y, confidence_score).
    """
    return np.linalg.norm(np.array(point1[:2]) - np.array(point2[:2]))


def calculate_angle(a, b, c):
    """
    Calculate angle b between three points a, b, c using cosine rule.
    a, b, c should be like (x, y, confidence_score).
    """
    mag_a = calculate_vector_magnitude(b, c)
    mag_b = calculate_vector_magnitude(a, c)
    mag_c = calculate_vector_magnitude(a, b)
    cos_b = ((mag_b**2) - (mag_a**2) - (mag_c**2)) / ((-2) * mag_a * mag_c)
    cos_b = max(-1.0, min(1.0, cos_b))
    angle_b = math.degrees(math.acos(cos_b))
    return angle_b


def calculate_knee_angle(keypoints, side):
    """
    Calculate knee angle.
    side: 'right', 'left', or 'both' (The side you want to calculate the knee angle for).
    """
    # hip, knee, ankle(COCO Wholebody)
    left_leg = [11, 13, 15]
    right_leg = [12, 14, 16]

    if side == "right":
        right_knee_angle = calculate_angle(
            keypoints[right_leg[0]], keypoints[right_leg[1]], keypoints[right_leg[2]]
        )
        return right_knee_angle
    elif side == "left":
        left_knee_angle = calculate_angle(
            keypoints[left_leg[0]], keypoints[left_leg[1]], keypoints[left_leg[2]]
        )
        return left_knee_angle
    else:
        right_knee_angle = calculate_angle(
            keypoints[right_leg[0]], keypoints[right_leg[1]], keypoints[right_leg[2]]
        )
        left_knee_angle = calculate_angle(
            keypoints[left_leg[0]], keypoints[left_leg[1]], keypoints[left_leg[2]]
        )
        return right_knee_angle, left_knee_angle


def determine_head_tilt(keypoints, side_facing):
    """
    Calculate how much the head is tilted up or down.
    side_facing: 'left' or 'right' (The side you want to calculate the head tilt for).
    """

    # Nose, Eye, Ear(COCO Wholebody)
    keypoint_index_both_side = {"left": [0, 1, 3], "right": [0, 2, 4]}
    keypoint_index = keypoint_index_both_side[side_facing]

    eye = keypoints[keypoint_index[1]]
    ear = keypoints[keypoint_index[2]]
    root = [keypoints[keypoint_index[1]][0], 0]

    tilt_angle = -(90 - calculate_angle(ear, eye, root))

    return tilt_angle


def calculate_arm_angle_from_vertical(keypoints, side="both"):
    """
    Calculates the angle between the arm (shoulder to wrist) and a vertical line (perpendicular to the ground at the shoulder).
    90 degrees means the arm is extended perfectly forward.
    side: 'left', 'right', or 'both' (The side you want to calculate the arm angle for).
    """
    # Shoulder, Elbow, Wrist (COCO Wholebody)
    keypoint_index_both_side = {"left": [5, 7, 9], "right": [6, 8, 10]}
    if side == "both":
        left_root_point = [keypoints[keypoint_index_both_side["left"][0]][0], 0]
        right_root_point = [keypoints[keypoint_index_both_side["right"][0]][0], 0]
        left_arm_angle = calculate_angle(
            left_root_point,
            keypoints[keypoint_index_both_side["left"][0]],
            keypoints[keypoint_index_both_side["left"][2]],
        )
        right_arm_angle = calculate_angle(
            right_root_point,
            keypoints[keypoint_index_both_side["right"][0]],
            keypoints[keypoint_index_both_side["right"][2]],
        )
        return left_arm_angle, right_arm_angle
    elif side in ["left", "right"]:
        root_point = [keypoints[keypoint_index_both_side[side][0]][0], 0]
        arm_angle = calculate_angle(
            root_point,
            keypoints[keypoint_index_both_side[side][0]],
            keypoints[keypoint_index_both_side[side][2]],
        )
        return arm_angle


def calculate_back_angle(keypoints, side_facing):
    # COCO WholeBody indices
    keypoint_index_both_side = {"left": [5, 11], "right": [6, 12]}
    # Use a vertical reference directly above the hip
    left_hip = keypoints[keypoint_index_both_side["left"][1]]
    right_hip = keypoints[keypoint_index_both_side["right"][1]]
    left_top_point = [left_hip[0], left_hip[1] - 10]
    right_top_point = [right_hip[0], right_hip[1] - 10]

    left_back_angle = calculate_angle(
        left_top_point, left_hip, keypoints[keypoint_index_both_side["left"][0]]
    )
    right_back_angle = calculate_angle(
        right_top_point, right_hip, keypoints[keypoint_index_both_side["right"][0]]
    )

    if (
        keypoints[keypoint_index_both_side["left"][0]][0] < left_hip[0]
    ) and side_facing == "right":
        left_back_angle = -left_back_angle
    elif (
        keypoints[keypoint_index_both_side["left"][0]][0] > left_hip[0]
    ) and side_facing == "left":
        left_back_angle = -left_back_angle

    if (
        keypoints[keypoint_index_both_side["right"][0]][0] < right_hip[0]
    ) and side_facing == "right":
        right_back_angle = -right_back_angle
    elif (
        keypoints[keypoint_index_both_side["right"][0]][0] > right_hip[0]
    ) and side_facing == "left":
        right_back_angle = -right_back_angle

    return np.mean([left_back_angle, right_back_angle])


def determine_nose_offset_from_knee(keypoints, side_facing):
    """
    Only used when user side is facing the camera.
    Calculate the offset of the nose from the knee furthest to the front on the x-axis.
    This is used to determine if the user is leaning forward enough.
    Returns a positive value if the nose is further away from the knee, negative if before the knee on the x-axis.
    Side facing is used to determine which side to calculate the nose offset for.
    side_facing: 'left' or 'right'
    Returns offset in centimeters.
    """
    # nose(COCO Wholebody)
    nose_idx = 0
    # left knee, right knee(COCO Wholebody)
    keypoint_indices = [13, 14]
    knees_x = [keypoints[i][0] for i in keypoint_indices]
    nose_x = keypoints[nose_idx][0]
    
    if side_facing == "left":
        # Furthest in front = largest x
        front_knee_x = max(knees_x)
        nose_offset_pixels = nose_x - front_knee_x
    else:
        # Furthest in front = smallest x
        front_knee_x = min(knees_x)
        nose_offset_pixels = front_knee_x - nose_x
    
    # Convert to centimeters (horizontal distance)
    nose_offset_cm = convert_pixels_to_cm(nose_offset_pixels, "horizontal")
    
    return nose_offset_cm


def determine_leg_spread(keypoints):
    """
    Only used when user side is facing the camera.
    Calculate the distance between the left and right ankle on the x-axis.
    This is used to determine if the user is standing with their feet too close together or too far apart.
    Returns the distance between the left and right ankle on the x-axis in centimeters.
    """
    # Ankle (COCO Wholebody)
    keypoint_index_both_side = {"left": [15], "right": [16]}

    leg_spread_pixels = abs(
        keypoints[keypoint_index_both_side["right"][0]][0]
        - keypoints[keypoint_index_both_side["left"][0]][0]
    )

    # Convert to centimeters (horizontal distance)
    leg_spread_cm = convert_pixels_to_cm(leg_spread_pixels, "horizontal")

    return leg_spread_cm


def calculate_arm_bent_angle(keypoints, side="both"):
    """
    Calculates the angle on the elbow(between shoulder and wrist) to determine the elbow bent angle.
    side: 'left', 'right', or 'both' (The side you want to calculate the arm bent angle for).
    """

    # Shoulder, Elbow, Wrist (COCO Wholebody)
    keypoint_index_both_side = {"left": [5, 7, 9], "right": [6, 8, 10]}
    if side == "both":
        left_arm_bent_angle = calculate_angle(
            keypoints[keypoint_index_both_side["left"][0]],
            keypoints[keypoint_index_both_side["left"][1]],
            keypoints[keypoint_index_both_side["left"][2]],
        )
        right_arm_bent_angle = calculate_angle(
            keypoints[keypoint_index_both_side["right"][0]],
            keypoints[keypoint_index_both_side["right"][1]],
            keypoints[keypoint_index_both_side["right"][2]],
        )
        return left_arm_bent_angle, right_arm_bent_angle
    elif side in ["left", "right"]:
        arm_bent_angle = calculate_angle(
            keypoints[keypoint_index_both_side[side][0]],
            keypoints[keypoint_index_both_side[side][1]],
            keypoints[keypoint_index_both_side[side][2]],
        )
        return arm_bent_angle


def calculate_foot_to_shoulder_offset(keypoints):
    """
    This function is to be used when the user's front side is facing the camera.
    Calculates the distance between the foot and the shoulder on the x axis.
    Returns the distance offset for both left and right foot in centimeters.
    + Positive value means the foot further away from each other.
    - Negative value means the foot closer to each other.
    """
    # Ankle, Shoulder (COCO Wholebody)
    keypoint_index_both_side = {"left": [15, 5], "right": [16, 6]}

    left_offset_pixels = (
        keypoints[keypoint_index_both_side["left"][0]][0]
        - keypoints[keypoint_index_both_side["left"][1]][0]
    )
    right_offset_pixels = (
        keypoints[keypoint_index_both_side["right"][1]][0]
        - keypoints[keypoint_index_both_side["right"][0]][0]
    )

    # Convert to centimeters (horizontal distance)
    left_offset_cm = convert_pixels_to_cm(left_offset_pixels, "horizontal")
    right_offset_cm = convert_pixels_to_cm(right_offset_pixels, "horizontal")

    return left_offset_cm, right_offset_cm


def determine_user_side(keypoints, head_tilt_angle=None):
    """
    Determine the side of the user based on the nose, eye, and ear positions.
    """
    # Nose, Eye, Ear (COCO Wholebody)
    keypoint_index_both_side = {"left": [0, 1, 3], "right": [0, 2, 4]}

    # If nose<left eye<left ear, user and nose>right eye>right ear, user facing front
    if (
        keypoints[keypoint_index_both_side["left"][0]][0]
        < keypoints[keypoint_index_both_side["left"][1]][0]
        < keypoints[keypoint_index_both_side["left"][2]][0]
    ) and (
        keypoints[keypoint_index_both_side["right"][0]][0]
        > keypoints[keypoint_index_both_side["right"][1]][0]
        > keypoints[keypoint_index_both_side["right"][2]][0]
    ):
        return "front"
    # If nose<left eye<left ear, user facing left
    elif (
        keypoints[keypoint_index_both_side["left"][0]][0]
        < keypoints[keypoint_index_both_side["left"][1]][0]
        < keypoints[keypoint_index_both_side["left"][2]][0]
    ):
        return "left"
    # If nose>right eye>right ear, user facing right
    elif (
        keypoints[keypoint_index_both_side["right"][0]][0]
        > keypoints[keypoint_index_both_side["right"][1]][0]
        > keypoints[keypoint_index_both_side["right"][2]][0]
    ):
        return "right"
    else:
        return "front"


def posture_score_from_keypoints(keypoints):
    """Calculate posture score from keypoints"""

    def linear_score(value, optimal, tolerance, limit):
        deviation = abs(value - optimal)
        if deviation <= tolerance:
            return 1.0
        elif deviation >= limit:
            return 0.0
        else:
            return 1.0 - ((deviation - tolerance) / (limit - tolerance))

    weights_side = {
        "knee_angle": 0.25,
        "head_tilt": 0.1,
        "arm_angle": 0.15,
        "arm_bent_angle": 0.1,
        "leg_spread": 0.15,
        "back_angle": 0.25,
    }

    weights_front = {"foot_to_shoulder_offset": 1.0}

    # Determine user side
    user_side = determine_user_side(keypoints)

    if user_side == "front":
        posture_score = {
            "side": user_side,
            "foot_to_shoulder_offset": 0.0,
        }

        raw_scores_percent = {}

        # Calculate the leg offset from the shoulder
        offset_optimal = 0  # cm - ideal is directly under shoulder
        tolerance = 3.1  # cm - acceptable deviation (was 2 pixels ≈ 0.31cm, increased for realism)
        limit = 15.5  # cm - maximum acceptable deviation (was 20 pixels ≈ 3.1cm, increased for realism)
        left_offset, right_offset = calculate_foot_to_shoulder_offset(keypoints)

        left_score = linear_score(left_offset, offset_optimal, tolerance, limit)
        right_score = linear_score(right_offset, offset_optimal, tolerance, limit)
        average_score = (left_score + right_score) / 2

        posture_score["foot_to_shoulder_offset"] = (
            weights_front["foot_to_shoulder_offset"] * average_score
        )

        raw_scores_percent["foot_to_shoulder_offset"] = round(average_score * 100, 2)

        measurements = {
            "foot_to_shoulder_offset_left": round(left_offset, 2),  # cm
            "foot_to_shoulder_offset_right": round(right_offset, 2),  # cm
        }

        return posture_score, measurements, raw_scores_percent

    elif user_side in ["left", "right"]:
        posture_score = {
            "side": user_side,
            "knee_angle": 0.0,
            "head_tilt": 0.0,
            "arm_angle": 0.0,
            "arm_bent_angle": 0.0,
            "leg_spread": 0.0,
            "back_angle": 0.0,
        }

        raw_scores_percent = {}

        # Knee angle
        knee_angle_range = (10, 30)
        knee_angle = calculate_knee_angle(keypoints, user_side)
        knee_bent_angle = 180 - knee_angle
        if knee_bent_angle < knee_angle_range[0]:
            score = linear_score(
                knee_bent_angle, knee_angle_range[0], 0, knee_angle_range[0]
            )
        elif knee_bent_angle > knee_angle_range[1]:
            score = linear_score(
                knee_bent_angle, knee_angle_range[1], 0, knee_angle_range[1]
            )
        else:
            score = 1.0
        posture_score["knee_angle"] = weights_side["knee_angle"] * score
        raw_scores_percent["knee_angle"] = round(score * 100, 2)

        # Head tilt
        head_tilt_optimal = 0
        head_tilt_tolerance = 10
        head_tilt_limit = 30
        head_tilt = determine_head_tilt(keypoints, user_side)
        head_tilt_score = linear_score(
            head_tilt, head_tilt_optimal, head_tilt_tolerance, head_tilt_limit
        )
        posture_score["head_tilt"] = weights_side["head_tilt"] * head_tilt_score
        raw_scores_percent["head_tilt"] = round(head_tilt_score * 100, 2)

        # Arm angle from vertical
        arm_tilt_optimal = 90
        arm_tilt_tolerance = 10
        arm_tilt_limit = 60
        arm_angle = calculate_arm_angle_from_vertical(keypoints, user_side)
        arm_angle_score = linear_score(
            arm_angle, arm_tilt_optimal, arm_tilt_tolerance, arm_tilt_limit
        )
        posture_score["arm_angle"] = weights_side["arm_angle"] * arm_angle_score
        raw_scores_percent["arm_angle"] = round(arm_angle_score * 100, 2)

        # Arm bent angle
        arm_bent_range = (10, 40)
        arm_bent_angle = 180 - calculate_arm_bent_angle(keypoints, user_side)
        if arm_bent_angle < arm_bent_range[0]:
            arm_bent_score = linear_score(
                arm_bent_angle, arm_bent_range[0], 0, arm_bent_range[0]
            )
        elif arm_bent_angle > arm_bent_range[1]:
            arm_bent_score = linear_score(
                arm_bent_angle, arm_bent_range[1], 0, arm_bent_range[1]
            )
        else:
            arm_bent_score = 1.0
        posture_score["arm_bent_angle"] = weights_side["arm_bent_angle"] * arm_bent_score
        raw_scores_percent["arm_bent_angle"] = round(arm_bent_score * 100, 2)

        # Leg spread
        leg_spread_optimal = 46.6  # cm - optimal leg spread (was 30 pixels ≈ 4.66cm, increased to realistic 46.6cm)
        leg_spread_tolerance = 15.5  # cm - acceptable deviation (was 10 pixels ≈ 1.55cm, increased to 15.5cm)
        leg_spread_limit = 93.2  # cm - maximum acceptable deviation (was 60 pixels ≈ 9.32cm, increased to 93.2cm)
        leg_spread = determine_leg_spread(keypoints)
        leg_spread_score = linear_score(
            leg_spread, leg_spread_optimal, leg_spread_tolerance, leg_spread_limit
        )
        posture_score["leg_spread"] = weights_side["leg_spread"] * leg_spread_score
        raw_scores_percent["leg_spread"] = round(leg_spread_score * 100, 2)

        # Back angle
        back_angle_optimal = 0
        back_angle_tolerance = 30
        back_angle_limit = 45
        back_angle = calculate_back_angle(keypoints, user_side)
        back_angle_score = linear_score(
            back_angle, back_angle_optimal, back_angle_tolerance, back_angle_limit
        )
        posture_score["back_angle"] = weights_side["back_angle"] * back_angle_score
        raw_scores_percent["back_angle"] = round(back_angle_score * 100, 2)

        measurements = {
            "knee_angle": round(knee_angle, 2),  # degrees
            "head_tilt": round(head_tilt, 2),  # degrees  
            "arm_angle": round(arm_angle, 2),  # degrees
            "arm_bent_angle": round(arm_bent_angle, 2),  # degrees
            "leg_spread": round(leg_spread, 2),  # cm
            "back_angle": round(back_angle, 2),  # degrees
        }

        return posture_score, measurements, raw_scores_percent


async def handle_inference(websocket, model_name: str):
    """Handle WebSocket connection with JWT authentication and inference"""
    # Perform authentication handshake (path will be extracted from websocket object)
    if not await authenticate_websocket(websocket):
        await websocket.close()
        return

    async for message in websocket:
        try:
            data = json.loads(message)
            img_b64 = data.get("image")
            if img_b64 is None:
                await websocket.send(json.dumps({"error": "No image provided"}))
                continue

            img = decode_image_from_base64(img_b64)
            if img is None:
                await websocket.send(json.dumps({"error": "Invalid image data"}))
                continue

            # Select next GPU inferencer for the specific model
            gpu_index = next(gpu_cycle)
            inferencer = inferencers[model_name][gpu_index]

            # Run inference
            result_generator = inferencer(img, return_vis=False)
            result = next(result_generator)

            preds = result.get("predictions", None)
            if not preds or not isinstance(preds, list) or len(preds[0]) == 0:
                await websocket.send(json.dumps({"error": "No person detected"}))
                continue

            keypoints = preds[0][0]["keypoints"]
            posture_score, measurement, raw_scores_percent = posture_score_from_keypoints(keypoints)

            await websocket.send(
                json.dumps(
                    {
                        "keypoints": keypoints,
                        "posture_score": posture_score,
                        "raw_scores_percent": raw_scores_percent,
                        "measurements": measurement,
                    }
                )
            )

        except Exception as e:
            await websocket.send(json.dumps({"error": str(e)}))


async def start_model_server(model_name: str):
    port = MODEL_CONFIGS[model_name]["port"]
    print(
        f"Starting WebSocket server for model '{model_name}' at ws://{WEBSOCKET_HOST}:{port}"
    )

    async def handler(websocket):
        await handle_inference(websocket, model_name)

    server = await websockets.serve(handler, WEBSOCKET_HOST, port)
    print(f"WebSocket server for model '{model_name}' started on port {port}")
    await server.wait_closed()


async def main():
    print("Starting WebSocket servers for all models...")
    # Start a server for each model in MODEL_CONFIGS
    try:
        await asyncio.gather(
            *[start_model_server(model_name) for model_name in MODEL_CONFIGS]
        )
    except KeyboardInterrupt:
        print("Shutting down servers...")
    except Exception as e:
        print(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
