# template.py

import os
from pathlib import Path 

PROJECT_NAME = "src"

LIST_FILES = [
    "Dockerfile",
    ".env",
    ".gitignore",
    "app.py",
    "init_setup.py",
    "README.md",
    "requirements.txt",
    "src/__init__.py",

    # config folder
    "src/config/__init__.py",
    "src/config/app_config.py",
    "src/config/database.py",
    "src/config/dev_config.py",
    "src/config/production_config.py",
    "src/config/websocket_config.py",

    # controllers
    "src/controllers/__init__.py",
    "src/controllers/analysis_controller.py",
    "src/controllers/auth_controller.py",

    # models
    "src/models/__init__.py",
    "src/models/analysis.py",
    "src/models/user.py",

    # services
    "src/services/__init__.py",
    "src/services/websocket_models.py",

    # utils
    "src/utils/__init__.py",
    "src/utils/helpers.py",

    # cli
    "src/cli.py",
]

for file_path in LIST_FILES:
    file_path = Path(file_path)
    file_dir, file_name = os.path.split(file_path)

    # first make dir
    if file_dir!="":
        os.makedirs(file_dir, exist_ok= True)
        print(f"Creating Directory: {file_dir} for file: {file_name}")
    
    if (not os.path.exists(file_path)) or (os.path.getsize(file_path)==0):
        with open(file_path, "w") as f:
            pass
            print(f"Creating an empty file: {file_path}")
    else:
        print(f"File already exists {file_path}")
