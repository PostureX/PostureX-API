echo "[ `date` ]": "START"
echo "[ `date` ]": "Creating virtual env" 
uv venv
echo "[ `date` ]": "activate venv"
source .venv/bin/activate
echo "[ `date` ]": "installing the requirements" 
uv pip install -r requirements.txt
echo "[ `date` ]": "creating folders and files" 
python template.py
echo "[ `date` ]": "END"