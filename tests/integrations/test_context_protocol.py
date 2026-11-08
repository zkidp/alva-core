import unittest
from benchmarks.context_v4.protocol import design,tools
from integrations.codex.maintenance_context import References


class Protocol(unittest.TestCase):
    def test_fixed_tasks_and_balanced_schedule(self):
        d=design();self.assertEqual(list(d['tasks']),['H01','H02','H03','H04']);self.assertEqual(len(d['schedule']),12)
        for a,b in [('T','V3'),('T','V4'),('V3','V4')]:
            before=0
            for task in d['tasks']:
                order=[r['arm'] for r in d['schedule'] if r['task']==task]
                self.assertEqual(set(order),{'T','V3','V4'});before+=order.index(a)<order.index(b)
            self.assertEqual(before,2)
    def test_information_access_is_equal_and_profile_smaller(self):
        self.assertEqual(tools('V3'),tools('V4'))
        self.assertEqual(tools('T')[3:],tools('V4')[3:])
        refs=References();self.assertLess(len(refs.docs['host']),len(refs.docs['legacy_skill']))
        self.assertNotIn('archived',refs.docs['language'])
        self.assertNotIn('needs_build',refs.docs['language'])


if __name__=='__main__':unittest.main()
