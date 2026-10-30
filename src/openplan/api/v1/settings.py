import os

import dotenv

dotenv.load_dotenv()

CURRENT_APP_VERSION = os.environ.get("CURRENT_APP_VERSION", "dev")

MIN_BASELINE_YEAR = int(os.environ.get("MIN_BASELINE_YEAR", "2023"))
MAX_BASELINE_YEAR = int(os.environ.get("MAX_BASELINE_YEAR", "2024"))
MAX_HORIZON_YEAR = int(os.environ.get("MAX_HORIZON_YEAR", "2047"))

BLOB_STORAGE_ACCOUNT = os.environ.get("BLOB_STORAGE_ACCOUNT", "")
BLOB_STORAGE_CONTAINER = os.environ.get("BLOB_STORAGE_CONTAINER", "")
