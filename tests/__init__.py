import os
import tempfile

TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "test_queuectl.db")

def setup_test_environment():
   
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except (OSError, PermissionError):
            pass

def teardown_test_environment():
    
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except (OSError, PermissionError):
            pass