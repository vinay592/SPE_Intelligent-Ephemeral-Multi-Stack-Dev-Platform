import unittest
import json
import sys
import os

# Add the parent directory to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app

class BackendTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        self.app = app.test_client()

    def test_health_check(self):
        """Test the root endpoint returns a 200 status."""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_invalid_login(self):
        """Test login with non-existent user."""
        response = self.app.post('/login',
                                 data=json.dumps({"username": "nonexistent", "password": "123"}),
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(data['status'], False)
        self.assertIn("Invalid", data['message'])

    def test_signup_validation(self):
        """Test signup requires both username and password."""
        response = self.app.post('/signup',
                                 data=json.dumps({"username": "onlyuser"}),
                                 content_type='application/json')
        # Depending on app.py logic, it should handle missing fields
        self.assertEqual(response.status_code, 200) # App handles errors with status flags
        data = json.loads(response.data)
        self.assertEqual(data['status'], False)

if __name__ == '__main__':
    unittest.main()
