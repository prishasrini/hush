import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import database

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'DATABASE_URL':'', 'SQLITE_PATH':str(Path(self.temp.name)/'test.db'), 'PYTHON_DOTENV_DISABLED':'1'})
        self.env.start()
        import app
        database.init_db()
        self.app = app.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def login(self):
        with self.client.session_transaction() as state:
            state['user_id'] = 'alice'

    def test_guest_support_and_breathing(self):
        self.assertEqual(self.client.get('/sos').status_code, 200)
        page = self.client.get('/doctor')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn(b'request a session', page.data)
        self.assertIn(b'+919999666555', page.data)

    def test_no_unmonitored_requests_are_saved(self):
        self.login()
        self.assertEqual(self.client.post('/api/doctor/request', json={'message':'help'}).status_code, 503)
        conn = database.get_db()
        self.assertEqual(conn.execute('SELECT * FROM doctor_requests').fetchall(), [])
        conn.close()

    def test_recent_room_messages_without_account_identifiers(self):
        self.login()
        conn = database.get_db()
        for i in range(105):
            conn.execute('INSERT INTO room_messages (room,user_id,label,content) VALUES (?,?,?,?)', ('exam-stress', 'alice' if i == 104 else 'bob', '<img src=x>', str(i)))
        conn.commit(); conn.close()
        messages = self.client.get('/api/rooms/exam-stress/messages').get_json()
        self.assertEqual(len(messages), 100)
        self.assertEqual(messages[0]['content'], '5')
        self.assertEqual(messages[-1]['content'], '104')
        self.assertTrue(messages[-1]['is_mine'])
        self.assertFalse(messages[0]['is_mine'])
        self.assertTrue(all('user_id' not in m for m in messages))

    def test_failed_moderation_does_not_publish(self):
        self.login()
        with patch('urllib.request.urlopen', side_effect=TimeoutError):
            result = self.client.post('/api/rooms/exam-stress/send', json={'content':'hello','label':'owl'})
        self.assertEqual(result.status_code, 503)
        conn = database.get_db()
        self.assertEqual(conn.execute('SELECT * FROM room_messages').fetchall(), [])
        conn.close()

    def test_room_input_limits(self):
        self.login()
        for data in [[], {'content':[]}, {'content':'x'*2001}, {'content':'hi','label':'x'*21}]:
            self.assertEqual(self.client.post('/api/rooms/exam-stress/send', json=data).status_code, 400)
