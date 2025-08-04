# WebSocket configuration for live inferencing
WEBSOCKET_HOST = '10.3.250.181'

JWT_SECRET_KEY = "EdibleCookieDough"
JWT_ALGORITHM = "HS256"

# Pixel to centimeter conversion ratios based on calibration
# Calibration measurements: 100cm horizontal = 644 pixels, 100cm vertical = 605 pixels
PIXELS_TO_CM_HORIZONTAL = 100 / 644  # 1 pixel = ~0.1553 cm horizontally
PIXELS_TO_CM_VERTICAL = 100 / 605    # 1 pixel = ~0.1653 cm vertically

# Model configurations
MODEL_CONFIGS = {
    'cx': {
        'port': 8893,
        'model_config': './posture-x-models/td-hm_res152_8xb32-210e_coco-wholebody-256x192.py',
        'checkpoint_path': './posture-x-models/best_coco-wholebody_AP_epoch_210.pth',
        'device': 'cuda'
    },
    'gy': {
        'port': 8894,
        'model_config': './posture-x-models/td-hm_hrnet-w48_dark-8xb32-210e_coco-wholebody-384x288.py',
        'checkpoint_path': './posture-x-models/best_coco-wholebody_AP_epoch_160.pth',
        'device': 'cuda'
    }
}
