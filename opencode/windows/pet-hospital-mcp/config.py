import os


PET_API_BASE_URL = os.getenv("PET_API_BASE_URL", "http://127.0.0.1:8080")
PET_API_TIMEOUT = float(os.getenv("PET_API_TIMEOUT", "10.0"))
