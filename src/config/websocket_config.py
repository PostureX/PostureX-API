# WebSocket configuration for live inferencing
WEBSOCKET_HOST = '10.3.250.181'

JWT_SECRET_KEY = "EdibleCookieDough"
JWT_ALGORITHM = "HS256"

# Model configurations
MODEL_CONFIGS = {
    'cx': {
        'port': 8895,
        'model_config': './posture-x-models/td-hm_res152_8xb32-210e_coco-wholebody-256x192.py',
        'checkpoint_path': './posture-x-models/best_coco-wholebody_AP_epoch_210.pth',
        'device': 'cuda'
    },
    'gy': {
        'port': 8896,
        'model_config': None,
        'checkpoint_path': None,
        'device': None
    }
}
