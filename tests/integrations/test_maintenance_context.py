"""Context bounds/encoding and profile routing; zero models."""
import io,json,unittest
from integrations.codex.maintenance_context import References,sectioned,source_read,TOOLS,serve
from integrations.codex.maintenance_host import TOOLS as BASE


class Context(unittest.TestCase):
    def test_sections_preserve_code_fences_and_exact_text(self):
        text='# Intro\n\n## one\nA\n```text\n## not-a-section\n```\n## two\nB\n'
        sections=sectioned(text)
        self.assertEqual(list(sections),['overview','one','two'])
        self.assertEqual(''.join(sections.values()),text)
    def test_reference_paths_are_closed_and_full_information_remains_available(self):
        ref=References()
        for name,text in ref.docs.items():
            self.assertEqual(ref.read({'document':name,'section':'all'})['content'],text)
            self.assertEqual(''.join(ref.sections[name].values()),text)
        self.assertEqual(ref.read({'document':'../../secret','section':'all'})['status'],'REJECTED')
        self.assertEqual(ref.read({'document':[],'section':'all'})['status'],'REJECTED')
        self.assertLess(len(ref.sections['language']['body'].encode()),1024)
        self.assertLess(len(ref.docs['host'].encode()),len(ref.docs['legacy_skill'].encode()))
    def test_source_reads_preserve_exact_crlf_and_bound_continuations(self):
        files={'m.alva':b'a\r\nb\r\nc\r\n'}
        first=source_read(files,{'path':'m.alva','count':2})
        self.assertEqual(first['content'],'a\r\nb\r\n');self.assertEqual(first['next_start'],3)
        last=source_read(files,{'path':'m.alva','start':3})
        self.assertEqual(first['content']+last['content'],files['m.alva'].decode());self.assertTrue(last['eof'])
        self.assertEqual(source_read(files,{'path':'../secret'})['status'],'REJECTED')
        self.assertEqual(source_read(files,{'path':'m.alva','count':True})['status'],'REJECTED')
        large={'m.alva':('x'*9000+'\n'+'y'*9000+'\n').encode()}
        bounded=source_read(large,{'path':'m.alva'})
        self.assertEqual(bounded['next_start'],2);self.assertLessEqual(len(bounded['content'].encode()),16384)
        self.assertEqual(source_read({'m':b'x'*17000},{'path':'m'})['status'],'REJECTED')
    def test_model_mcp_surface_retains_exact_mutations(self):
        self.assertEqual(TOOLS[:3],BASE)
        self.assertEqual([t['name'] for t in TOOLS],['read_target','prepare_change','publish_change','read_reference','read_source'])
        class Host:
            references=References()
            def invoke(self,name,args):return {'status':'REFERENCE','content':'public'}
        incoming=io.StringIO('\n'.join(json.dumps({'jsonrpc':'2.0','id':n,'method':method}) for n,method in enumerate(['initialize','tools/list'])))
        output=io.StringIO();serve(Host(),incoming,output)
        rows=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(rows[0]['result']['instructions'],Host.references.docs['host'])
        self.assertEqual(rows[1]['result']['tools'],TOOLS)


if __name__=='__main__':unittest.main()
