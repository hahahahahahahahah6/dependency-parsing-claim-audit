POSITIVE = ['dependency parsing', 'dependency parser', 'dependency parse', 'parses dependencies', 'parse dependencies', 'dependency parses', 'parsing dependencies', 'dependency-parsed', 'dependency tree', 'dependency trees', 'dependency relations', 'dependency relation', 'syntactic dependencies', 'syntactic dependency parsing', 'syntactic dependency parser', 'dependency grammar parsing', 'dependency grammar', 'dependency structure', 'dependency structures', 'assigns dependency labels', 'assign dependency labels', 'labels dependencies', 'label dependencies', 'identifies dependencies', 'identify dependencies', 'detects dependencies', 'detect dependencies', 'extracts dependencies', 'extract dependencies', 'supports dependency parsing', 'provides dependency parsing', 'performs dependency parsing', 'dependency parsing support', 'dependency parsing feature', 'dependency parsing capability', 'dependency parsing system', 'dependency parsing model', 'supports a dependency parser', 'provides a dependency parser', 'dependency annotation', 'dependency annotations', 'syntactic dependency annotation', 'dependency links', 'dependency arcs', 'dependency analysis', 'syntactic dependency analysis', 'dependency label assignment', 'assigns dependency relations', 'dependency tree construction', 'dependency tree building']
NEGATIVE = ['does not parse dependencies', 'do not parse dependencies', "doesn't parse dependencies", "don't parse dependencies", 'no dependency parsing', 'without dependency parsing', 'never parses dependencies', 'does not perform dependency parsing', 'never performs dependency parsing', 'dependency parsing not supported', 'dependency parsing unsupported', 'no dependency parsing support', 'lacks dependency parsing', 'missing dependency parsing', 'dependency parsing disabled', 'no dependency parser', 'without a dependency parser', 'does not provide dependency parsing', 'does not support dependency parsing', 'no dependency tree', 'without dependency parsing support', 'does not identify dependencies', 'dependency parsing not available', 'no syntactic dependency parsing']
NAMES = ['parse_dependencies', 'dependency_parse', 'get_dependencies', 'extract_dependencies', 'dependency_parse_text', 'parse_dependency_tree', 'build_dependency_tree', 'get_dependency_tree', 'dependency_parse_sentence', 'analyze_dependencies', 'analyse_dependencies', 'detect_dependencies', 'identify_dependencies', 'label_dependencies', 'assign_dependency_labels', 'dependency_annotate', 'annotate_dependencies', 'dependency_parsing', 'dependency_tree_parse', 'parse_with_dependencies', 'extract_dependency_relations', 'get_dependency_relations', 'dependency_relation_parse', 'parse_dependency_relations']
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from dependency_parsing_claim_audit.audit import audit, has_evidence, phrase_matches
from dependency_parsing_claim_audit.phrases import DEP, NODEP, GENERIC_NAMES


class AuditTests(unittest.TestCase):
    def fixture(self, files):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        return root

    def cli(self, root, *args):
        return subprocess.run([sys.executable, '-m', 'dependency_parsing_claim_audit', 'audit', str(root), *args], capture_output=True, text=True)

    def test_phrase_oracle(self):
        self.assertEqual(DEP, POSITIVE)
        self.assertEqual(NODEP, NEGATIVE)
        self.assertEqual((len(DEP), len(NODEP)), (50, 24))

    def test_generic_oracle(self):
        self.assertEqual(GENERIC_NAMES, NAMES)
        self.assertEqual(len(NAMES), 24)

    def test_spacy(self):
        for prefix, load in [('import spacy', 'spacy.load'), ('import spacy as s', 's.load'), ('from spacy import load', 'load'), ('from spacy import load as L', 'L')]:
            for attr in ['dep_', 'head']:
                for form in ['p=LOAD("en")\nd=p(text)\nd.ATTR', 'LOAD("en")(text).ATTR', 'p=LOAD("en")\np(text).ATTR', 'p=LOAD("en")\nfor t in p(text):\n t.ATTR', '[t.ATTR for t in LOAD("en")(text)]']:
                    with self.subTest(prefix=prefix, attr=attr, form=form):
                        self.assertTrue(has_evidence(prefix+'\n'+form.replace('LOAD',load).replace('ATTR',attr)))

    def test_stanza(self):
        for prefix, make in [('import stanza','stanza.Pipeline'), ('import stanza as s','s.Pipeline'), ('from stanza import Pipeline','Pipeline'), ('from stanza import Pipeline as P','P')]:
            for form in ['p=MAKE(processors="tokenize,DEPPARSE")\nd=p(text)\nd.dependencies', 'MAKE(processors="depparse")(text).dependencies', 'p=MAKE(processors="depparse")\nfor s in p(text).sentences:\n for w in s.words:\n  w.ATTR', '[w.ATTR for s in MAKE(processors="depparse")(text).sentences for w in s.words]']:
                for attr in ['deprel','head']:
                    with self.subTest(form=form, attr=attr, prefix=prefix):
                        self.assertTrue(has_evidence(prefix+'\n'+form.replace('MAKE',make).replace('ATTR',attr)))

    def test_generic_calls(self):
        for name in NAMES:
            for code in ['x.'+name+'(text)', 'from example import '+name+'\n'+name+'(text)', 'from example import '+name+' as f\nf(text)']:
                with self.subTest(code=code):
                    self.assertTrue(has_evidence(code))

    def test_rejections(self):
        cases = ['import spacy', 'from stanza import Pipeline', 'from x import parse_dependencies', 'nltk.pos_tag(text)', 'nltk.ne_chunk(text)', 'Tree(text)', 'tree.parse(text)', 'x.extract_keywords(text)', 'KeyphraseModel()(text)', 'pipeline("sentiment-analysis")(text)', 'x.sentiment(text)', 'pipeline("text-classification")(text)', 'Classifier()(text)', 'tokenizer(text)', 'lemmatizer(text)', '"parse_dependencies"\n# x.parse_dependencies(text)', 'parse_dependencies', 'parse_dependencies(text)', 'subprocess.run(["dependency-parser"])', 'import spacy\np=spacy.load("en")', 'import stanza\np=stanza.Pipeline(processors="depparse")', 'import stanza\np=stanza.Pipeline(processors="tokenize,pos")\np(text).dependencies', 'import spacy\np=spacy.load("en")\nx(text).dep_', 'x.generate(text)', 'import spacy\np=spacy.load("en")\np(text).pos_', 'import spacy\np=spacy.load("en")\np(text).tag_', 'import spacy\np=spacy.load("en")\np(text).ents', 'import spacy\np=spacy.load("en")\np(text).lemma_', 'import stanza\np=stanza.Pipeline(processors="ner")\np(text).dependencies', 'NERTagger().predict(text)', 'import stanza\np=stanza.Pipeline(processors="depparse")\nx.dependencies']
        for code in cases:
            with self.subTest(code=code):
                self.assertFalse(has_evidence(code))

    def test_shadowing(self):
        for code in ['from x import parse_dependencies\ndef parse_dependencies(x): pass\nparse_dependencies(text)', 'from x import parse_dependencies as p\nclass p: pass\np(text)', 'from spacy import load\ndef load(x): pass\nload("en")(text).dep_', 'from stanza import Pipeline\nclass Pipeline: pass\nPipeline(processors="depparse")(text).dependencies', 'import spacy\nclass spacy: pass\nspacy.load("en")(text).head']:
            with self.subTest(code=code):
                self.assertFalse(has_evidence(code))

    def test_split_modules(self):
        root=self.fixture({'README.md':'dependency parsing', 'a.py':'import spacy\np=spacy.load("en")', 'b.py':'p(text).dep_'})
        self.assertEqual(audit(root)[0]['verdict'], 'HIGH')

    def test_span_removal(self):
        self.assertEqual(phrase_matches('does not parse dependencies'), [('NODEP','does not parse dependencies')])
        self.assertEqual(phrase_matches('dependency parsing system'), [('DEP','dependency parsing system')])

    def test_fences_inline_case_hyphens(self):
        self.assertEqual(phrase_matches('```text\ndependency parsing\n```'), [])
        self.assertEqual(phrase_matches('`DEPENDENCY PARSING`'), [('DEP','dependency parsing')])
        self.assertEqual(phrase_matches('dependency-parsing'), [])

    def test_cli_good(self):
        root=self.fixture({'README.md':'dependency parsing','a.py':'x.parse_dependencies(text)'})
        result=self.cli(root)
        self.assertEqual(result.returncode,0)
        self.assertIn('PASS',result.stdout)

    def test_cli_bad_json(self):
        result=self.cli(self.fixture({'README.md':'dependency parsing'}),'--json')
        self.assertEqual(result.returncode,2)
        f=json.loads(result.stdout)[0]
        self.assertEqual(f['rule'],'documented-dependency-parsing-claim-false')
        self.assertEqual(f['verdict'],'HIGH')
        self.assertTrue(f['message'])

    def test_cli_test_only(self):
        root=self.fixture({'tests/fixture.md':'dependency parsing'})
        self.assertEqual(self.cli(root).returncode,0)
        result=self.cli(root,'--json','--fail-on','medium')
        self.assertEqual(result.returncode,2)
        self.assertEqual(json.loads(result.stdout)[0]['verdict'],'MEDIUM')

    def test_cli_denial(self):
        root=self.fixture({'README.md':'does not parse dependencies','x.py':'x.parse_dependencies(text)'})
        result=self.cli(root,'--json')
        self.assertEqual(result.returncode,2)
        self.assertEqual(json.loads(result.stdout)[0]['rule'],'documented-no-dependency-parsing-claim-false')
        self.assertEqual(json.loads(result.stdout)[0]['verdict'],'HIGH')

    def test_cli_no_claim(self):
        self.assertEqual(self.cli(self.fixture({'README.md':'Hello'})).stdout.strip(),'PASS')

    def test_cli_version(self):
        r=subprocess.run([sys.executable,'-m','dependency_parsing_claim_audit','--version'],capture_output=True,text=True)
        self.assertEqual(r.stdout.strip(),'0.1.0')
        self.assertEqual(r.returncode,0)

    def test_cli_ignore_verbose(self):
        root=self.fixture({'docs/bad.md':'dependency parsing','vendor/x.py':'x.parse_dependencies(text)'})
        self.assertEqual(self.cli(root,'--ignore','vendor/').returncode,2)
        result=self.cli(root,'--ignore','docs/','--ignore','vendor/','--verbose')
        self.assertEqual(result.returncode,0)
        self.assertIn('Scope:',result.stderr)

    def test_cli_errors(self):
        self.assertEqual(self.cli('/nonexistent').returncode,1)
        self.assertEqual(self.cli('.', '--unknown').returncode,1)
        self.assertEqual(self.cli(self.fixture({'a.py':'def !'})).returncode,1)

    def test_exclusions(self):
        root=self.fixture({'README.md':'dependency parsing','.git/x.py':'x.parse_dependencies(text)','v/pyvenv.cfg':'','v/x.py':'x.parse_dependencies(text)'})
        self.assertEqual(audit(root)[0]['verdict'],'HIGH')

    def test_self_readme(self):
        readme=Path(__file__).resolve().parents[1]/'README.md'
        if not readme.exists():
            import importlib.metadata
            text=importlib.metadata.metadata('dependency-parsing-claim-audit').get_payload()
        else:
            text=readme.read_text(encoding='utf-8')
        self.assertEqual(phrase_matches(text),[])
        self.assertEqual(audit(self.fixture({'README.md':text})),[])
