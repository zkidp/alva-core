"""Batch transport must preserve the original P34 decision and fail closed."""
import copy
import unittest

from integrations.codex.precommit_scope_guard import GuardedNative
from tests.integrations.test_precommit_scope_guard import fixture


def new(bulk=True):
    inner, policy = fixture()
    original = inner.request
    inner.corrupt = lambda envelope: None
    def request(method, params, **kwargs):
        if params.get('name') != 'inspect_scope_snapshot':
            return original(method, params, **kwargs)
        inner.calls.append('inspect_scope_snapshot')
        if inner.inspect_failure: return {'isError':True}
        nodes = {}
        def walk(rev):
            if rev in nodes:return
            nodes[rev] = copy.deepcopy(inner.graph[rev])
            for children in nodes[rev]['slots'].values():
                for child in children:walk(child)
        walk('m')
        envelope = {'project':{'modules':{'module:m':'m'},'project_revision':'project'}, 'nodes':nodes}
        inner.corrupt(envelope)
        return {'isError':False,'structuredContent':envelope}
    inner.request = request
    guard = GuardedNative(inner, policy, {'begin_transaction','commit_transaction'},
        snapshot_tool='inspect_scope_snapshot' if bulk else None)
    guard.tool('begin_transaction', {})
    return inner,guard


class Tests(unittest.TestCase):
    def test_decisions_and_snapshot_digests_match_legacy(self):
        def body(g):g['a']['slots']['body']=['a1']
        def spill(g):g['b']['slots']['body']=['b1']
        def shared(g):
            g['a']['slots']['body']=['b1'];g['b']['slots']['body']=['b1']
        def metadata(g):g['a']['fields']['pure']=False
        def signature(g):g['a']['slots']['returns']=['a0']
        def interface(g):g['m']['fields']['exports']=['b']
        def declarations(g):g['m']['slots']['functions']=['a']
        def unsupported(g):g['m']['slots']['new_slot']=[]
        def extern(g):g['m']['slots']['externs']=['a0']
        for mutate in (lambda g:None,body,spill,shared,metadata,signature,interface,declarations,unsupported,extern):
            with self.subTest(case=mutate.__name__):
                old,legacy = new(False);fast,batch = new(True)
                self.assertEqual(legacy._baselines,batch._baselines)
                mutate(old.graph);mutate(fast.graph)
                a = legacy.tool('commit_transaction', {'transaction_id':'tx'})
                b = batch.tool('commit_transaction', {'transaction_id':'tx'})
                self.assertEqual(a,b)
                self.assertEqual(old.calls.count('commit_transaction'),fast.calls.count('commit_transaction'))
                self.assertEqual(fast.calls.count('inspect_scope_snapshot'),2)
                self.assertNotIn('inspect_entity',fast.calls)

    def test_corrupt_or_incomplete_batch_never_authorizes_commit(self):
        def missing(e):e['nodes'].pop('a0')
        def wrong_revision(e):e['nodes']['a0']['revision']='other'
        def bad_slots(e):e['nodes']['a']['slots']['body']='a0'
        def extra(e):e['nodes']['unreachable']=copy.deepcopy(e['nodes']['a0'])
        def project(e):e['project']['modules']={}
        def envelope(e):e['extra']=True
        def bound(e):e['nodes'].update({str(i):{} for i in range(2049)})
        for corrupt in (missing,wrong_revision,bad_slots,extra,project,envelope,bound):
            with self.subTest(case=corrupt.__name__):
                inner,guard=new();inner.corrupt=corrupt
                decision=guard.tool('commit_transaction',{'transaction_id':'tx'})
                self.assertEqual(decision['structuredContent']['host_scope']['status'],'SCOPE_UNVERIFIED')
                self.assertNotIn('commit_transaction',inner.calls)
        inner,guard=new();inner.inspect_failure=True
        self.assertTrue(guard.tool('commit_transaction',{'transaction_id':'tx'})['isError'])
        self.assertNotIn('commit_transaction',inner.calls)

    def test_no_fallback_or_model_transport_selection(self):
        inner,guard=new();inner.inspect_failure=True
        guard.tool('commit_transaction',{'transaction_id':'tx'})
        self.assertNotIn('inspect_entity',inner.calls)
        self.assertNotIn('inspect_project',inner.calls)
        self.assertTrue(guard.tool('commit_transaction',{'transaction_id':'tx','snapshot_tool':None})['isError'])


if __name__ == '__main__':unittest.main()
