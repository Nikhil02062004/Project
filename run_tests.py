import unittest
import sys
import os
import warnings

def run_all_tests():
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    
    
    loader = unittest.TestLoader()
    start_dir = os.path.join(project_root, 'tests')
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2, failfast=False)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    print("Running QueueCTL Test Suite...")
    print("Note: Some tests may take longer due to retry backoffs")
    success = run_all_tests()
    sys.exit(0 if success else 1)