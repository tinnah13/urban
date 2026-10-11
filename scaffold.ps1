# Urban Mobility Explorer - Scaffold Script
$ErrorActionPreference = "Stop"

Write-Host "Creating directories..." -ForegroundColor Cyan
$dirs = @(
  "codevibe-reports","data","database","docs/screenshots",
  "backend/data_pipeline","backend/algorithms/tests","backend/db/migrations",
  "backend/routes","backend/services","backend/tests",
  "frontend/css","frontend/js","frontend/assets/icons",
  "scripts","notebooks",".github/workflows"
)
foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path $d | Out-Null }

Write-Host "Creating root files..." -ForegroundColor Cyan
@"
__pycache__/
*.py[cod]
.venv/
venv/
env/
*.egg-info/
.pytest_cache/
.env
*.env.local
data/*.parquet
database/*.db
database/*.sqlite
.DS_Store
Thumbs.db
.vscode/
.idea/
*.swp
*.log
logs/
!codevibe-reports/*.report.json
!data/taxi_zone_lookup.csv
"@ | Set-Content -Path ".gitignore" -Encoding UTF8

@"
DB_URL=sqlite:///database/urban_mobility.db
FLASK_ENV=development
FLASK_PORT=5000
DATA_DIR=data
"@ | Set-Content -Path ".env.example" -Encoding UTF8

Set-Content -Path "README.md" -Value "# Urban Mobility Explorer" -Encoding UTF8
Set-Content -Path "LICENSE" -Value "Academic Project - ALU Summative 2025" -Encoding UTF8

Write-Host "Creating backend..." -ForegroundColor Cyan
@"
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
"@ | Set-Content -Path "backend/app.py" -Encoding UTF8

@"
import os
from dotenv import load_dotenv
load_dotenv()
DB_URL = os.getenv('DB_URL', 'sqlite:///database/urban_mobility.db')
DATA_DIR = os.getenv('DATA_DIR', 'data')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
"@ | Set-Content -Path "backend/config.py" -Encoding UTF8

"flask`nflask-cors`npandas`npyarrow`nsqlalchemy`npython-dotenv" |
  Set-Content -Path "backend/requirements.txt" -Encoding UTF8

$backendFiles = @(
  "backend/data_pipeline/__init__.py",
  "backend/data_pipeline/loader.py",
  "backend/data_pipeline/cleaner.py",
  "backend/data_pipeline/features.py",
  "backend/data_pipeline/outlier_log.py",
  "backend/data_pipeline/run_pipeline.py",
  "backend/algorithms/__init__.py",
  "backend/algorithms/custom_sort.py",
  "backend/algorithms/anomaly_detector.py",
  "backend/algorithms/tests/test_sort.py",
  "backend/algorithms/tests/test_anomaly.py",
  "backend/db/__init__.py",
  "backend/db/seed.py",
  "backend/db/build_database.py",
  "backend/db/queries.py",
  "backend/routes/__init__.py",
  "backend/routes/health.py",
  "backend/routes/summary.py",
  "backend/routes/analytics.py",
  "backend/routes/trips.py",
  "backend/routes/zones.py",
  "backend/routes/anomalies.py",
  "backend/services/__init__.py",
  "backend/services/analytics_service.py",
  "backend/services/filter_service.py",
  "backend/services/insight_service.py",
  "backend/tests/test_api.py",
  "backend/tests/test_cleaner.py",
  "backend/tests/test_features.py"
)
foreach ($f in $backendFiles) { Set-Content -Path $f -Value "" -Encoding UTF8 }

Set-Content -Path "backend/db/schema.sql" -Value "-- Schema" -Encoding UTF8
Set-Content -Path "backend/db/migrations/001_initial.sql" -Value "-- Migration" -Encoding UTF8
Set-Content -Path "backend/algorithms/README.md" -Value "# Custom Algorithms" -Encoding UTF8

Write-Host "Creating frontend..." -ForegroundColor Cyan
@"
<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='UTF-8'>
<title>Urban Mobility Explorer</title>
<link rel='stylesheet' href='css/styles.css'>
</head>
<body>
<h1>Urban Mobility Explorer</h1>
<p>Dashboard loading...</p>
<script src='js/app.js'></script>
</body>
</html>
"@ | Set-Content -Path "frontend/index.html" -Encoding UTF8

Set-Content -Path "frontend/css/styles.css" -Value "body { font-family: system-ui, sans-serif; margin: 0; padding: 20px; background: #f5f6fa; }" -Encoding UTF8
Set-Content -Path "frontend/css/dashboard.css" -Value "/* dashboard styles */" -Encoding UTF8
Set-Content -Path "frontend/css/responsive.css" -Value "/* media queries */" -Encoding UTF8
Set-Content -Path "frontend/js/api.js" -Value "const API = '/api'; const api = { get: (p) => fetch(API + p).then(r => r.json()) };" -Encoding UTF8
Set-Content -Path "frontend/js/charts.js" -Value "// chart renderers" -Encoding UTF8
Set-Content -Path "frontend/js/app.js" -Value "console.log('Urban Mobility Explorer loaded');" -Encoding UTF8
Set-Content -Path "frontend/js/filters.js" -Value "// filter state" -Encoding UTF8
Set-Content -Path "frontend/js/table.js" -Value "// trips table" -Encoding UTF8
Set-Content -Path "frontend/js/insights.js" -Value "// insights panel" -Encoding UTF8
Set-Content -Path "frontend/assets/logo.svg" -Value "<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'></svg>" -Encoding UTF8
Set-Content -Path "frontend/assets/icons/taxi.svg" -Value "<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24'></svg>" -Encoding UTF8
Set-Content -Path "frontend/assets/icons/chart.svg" -Value "<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24'></svg>" -Encoding UTF8

Write-Host "Creating docs + database + scripts..." -ForegroundColor Cyan
Set-Content -Path "database/README.md" -Value "# Database" -Encoding UTF8
Set-Content -Path "database/dump.sql" -Value "-- DB dump placeholder" -Encoding UTF8
Set-Content -Path "docs/technical_report.md" -Value "# Technical Report" -Encoding UTF8
Set-Content -Path "docs/data_dictionary.md" -Value "# Data Dictionary" -Encoding UTF8
Set-Content -Path "docs/cleaning_log.md" -Value "# Cleaning Log" -Encoding UTF8
Set-Content -Path "docs/architecture_diagram.mmd" -Value "graph LR`n  A[Browser] --> B[Flask API]`n  B --> C[SQLAlchemy]`n  C --> D[(SQLite)]" -Encoding UTF8
Set-Content -Path "scripts/download_data.sh" -Value "#!/bin/bash" -Encoding UTF8
Set-Content -Path "scripts/init_db.sh" -Value "#!/bin/bash`npython backend/db/build_database.py" -Encoding UTF8
Set-Content -Path "scripts/run_backend.sh" -Value "#!/bin/bash`ncd backend && python app.py" -Encoding UTF8
Set-Content -Path "scripts/export_dump.sh" -Value "#!/bin/bash`nsqlite3 database/urban_mobility.db .dump > database/dump.sql" -Encoding UTF8
Set-Content -Path "scripts/verify_codevibe.sh" -Value "#!/bin/bash" -Encoding UTF8
Set-Content -Path "codevibe-reports/README.md" -Value "# CodeVibe Reports" -Encoding UTF8
Set-Content -Path ".github/workflows/tests.yml" -Value "name: tests" -Encoding UTF8

Write-Host "Creating notebooks..." -ForegroundColor Cyan
$nb = '{"cells":[],"metadata":{},"nbformat":4,"nbformat_minor":5}'
Set-Content -Path "notebooks/01_exploration.ipynb" -Value $nb -Encoding UTF8
Set-Content -Path "notebooks/02_cleaning_analysis.ipynb" -Value $nb -Encoding UTF8
Set-Content -Path "notebooks/03_insights.ipynb" -Value $nb -Encoding UTF8

$count = (Get-ChildItem -Recurse -File).Count
Write-Host ""
Write-Host "===========================================" -ForegroundColor Green
Write-Host " SUCCESS: $count files created." -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green
Write-Host ""