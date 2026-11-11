"""Test cho cải tiến Bài 4: tool call bị in ra dạng văn bản không được coi là final answer."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, tool_call, final

# Output thật của qwen2.5:7b ở case E4 trong eval_before.json.
LEAKED = 'brtc {"name": "get_incident_details", "arguments": {"provider": "github", "incident_id": "xr3myzj7ms51"}} </tool_call>'
URL = 'https://stspg.io/pjgptg3cfc6n'


class MalformedToolCallTests(unittest.TestCase):
    def test_leaked_tool_call_gets_retry_and_is_executed(self):
        fake = FakeProvider([final(LEAKED),
                             tool_call('c1', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}'),
                             final('Webhooks, Actions, Pages bị ảnh hưởng; Actions có liên quan. ' + URL)])
        result = run_agent('Xem incident GitHub xr3myzj7ms51', fake, StatusTools(), max_steps=4)
        self.assertEqual(result['status'], 'completed')
        events = [t['event'] for t in result['trace']]
        self.assertIn('validation_malformed_tool_call', events)
        self.assertIn('tool', events)
        self.assertNotIn('</tool_call>', result['answer'])
        # Model phải nhận được phản hồi sau assistant message hỏng.
        self.assertEqual(fake.histories[1][-1]['role'], 'user')
        self.assertIn('function calling', fake.histories[1][-1]['content'])

    def test_leaked_tool_call_at_budget_limit_is_not_completed(self):
        result = run_agent('x', FakeProvider([final(LEAKED)]), StatusTools(), max_steps=1)
        self.assertEqual(result['status'], 'max_steps')

    def test_normal_answer_without_tool_markup_is_accepted(self):
        text = 'GitHub Actions operational theo snapshot; không có incident đang mở. Nguồn: https://www.githubstatus.com'
        result = run_agent('x', FakeProvider([final(text)]), StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(any(t['event'].startswith('validation') for t in result['trace']))


if __name__ == '__main__':
    unittest.main()
