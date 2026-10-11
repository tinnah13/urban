import os
from dotenv import load_dotenv
load_dotenv()
DB_URL = os.getenv('DB_URL', 'sqlite:///database/urban_mobility.db')
DATA_DIR = os.getenv('DATA_DIR', 'data')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
