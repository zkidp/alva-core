import unittest
from benchmarks.host_v3_acceptance.protocol import design,tools
from benchmarks.compact_deepseek.api import totals,usage


class Contract(unittest.TestCase):
    def test_fixed_fresh_schedule_balances_each_pair(self):
        d=design();rows=d['schedule']
        self.assertEqual(len(rows),12)
        self.assertEqual(len({r['id'] for r in rows}),12)
        for a,b in (('T','V2'),('T','V3'),('V2','V3')):
            before=0
            for task in d['tasks']:
                arms=[r['arm'] for r in rows if r['task']==task]
                self.assertEqual(set(arms),{'T','V2','V3'})
                before+=arms.index(a)<arms.index(b)
            self.assertEqual(before,2)
    def test_model_surface_is_closed_and_solutions_are_absent(self):
        d=design()
        self.assertEqual(tools('V2'),tools('V3'))
        for arm in ('T','V2','V3'):
            self.assertEqual([t['name'] for t in tools(arm)],['read_target','prepare_change','publish_change','study_doc'])
            self.assertTrue(all(t['inputSchema']['additionalProperties'] is False for t in tools(arm)))
        self.assertEqual(set(d['docs']),{'language.md','SKILL.md','references/workflow.md','references/diagnostics.md','references/examples.md'})
        self.assertNotIn('witness',d['developer_instructions'].lower())
    def test_cached_usage_is_never_subtracted_and_missing_reasoning_stays_null(self):
        u=usage({'total_tokens':100,'prompt_tokens':80,'prompt_cache_hit_tokens':70,'completion_tokens':20})
        self.assertEqual(totals([u,u]),{'totalTokens':200,'inputTokens':160,'cachedInputTokens':140,'outputTokens':40,'reasoningOutputTokens':None})


if __name__=='__main__':unittest.main()
