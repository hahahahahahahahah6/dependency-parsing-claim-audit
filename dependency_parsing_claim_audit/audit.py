"""Read-only static source and documentation inspection."""
import ast
import os
import re
from pathlib import Path
from .phrases import DEP, NODEP, GENERIC_NAMES


def phrase_matches(text):
    text = re.sub(r'```[^\n]*\n.*?(?:```|\Z)', '', text, flags=re.S)
    text = text.replace('`', '').lower()
    found = []
    for phrases, kind in [(NODEP, 'NODEP'), (DEP, 'DEP')]:
        for phrase in sorted(phrases, key=len, reverse=True):
            start = text.find(phrase)
            while start >= 0:
                found.append((kind, phrase))
                text = text[:start] + ' ' * len(phrase) + text[start + len(phrase):]
                start = text.find(phrase)
    return found


def has_evidence(source):
    tree = ast.parse(source)
    shadow = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    imports = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                imports[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                imports[a.asname or a.name] = (n.module or '') + '.' + a.name
    values = {}

    def resolve(n):
        if isinstance(n, ast.Name):
            return '' if n.id in shadow else imports.get(n.id, '')
        if isinstance(n, ast.Attribute):
            base = resolve(n.value)
            return base + '.' + n.attr if base else ''
        return ''

    def value(n):
        if isinstance(n, ast.Name):
            return '' if n.id in shadow else values.get(n.id, '')
        if isinstance(n, ast.Call):
            route = resolve(n.func)
            if route == 'spacy.load':
                return 'spacy-model'
            if route == 'stanza.Pipeline' and any(k.arg == 'processors' and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str) and 'depparse' in k.value.value.lower() for k in n.keywords):
                return 'stanza-model'
            base = value(n.func)
            if base in ('spacy-model', 'stanza-model'):
                return base.replace('model', 'doc')
        if isinstance(n, ast.Attribute):
            base = value(n.value)
            if n.attr == 'sentences' and base == 'stanza-doc':
                return 'stanza-sentences'
            if n.attr == 'words' and base == 'stanza-sentence':
                return 'stanza-words'
        return ''

    def bind(target, kind):
        if isinstance(target, ast.Name):
            values[target.id] = kind
        elif isinstance(target, (ast.Tuple, ast.List)):
            for t in target.elts:
                bind(t, '')

    def visit(n):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in GENERIC_NAMES:
                # Definitions of a route or its base defeat that route.
                base = f.value
                while isinstance(base, ast.Attribute):
                    base = base.value
                if f.attr not in shadow and not (isinstance(base, ast.Name) and base.id in shadow):
                    return True
            if isinstance(f, ast.Name) and f.id not in shadow and resolve(f).split('.')[-1] in GENERIC_NAMES:
                return True
        if isinstance(n, ast.Attribute):
            kind = value(n.value)
            if n.attr in ('dep_', 'head') and kind in ('spacy-doc', 'spacy-token'):
                return True
            if n.attr == 'dependencies' and kind in ('stanza-doc', 'stanza-sentence'):
                return True
            if n.attr in ('deprel', 'head') and kind == 'stanza-word':
                return True
        if isinstance(n, (ast.Assign, ast.AnnAssign)):
            if n.value is not None:
                kind = value(n.value)
                for t in n.targets if isinstance(n, ast.Assign) else [n.target]:
                    bind(t, kind)
        if isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
            kinds = {'spacy-doc': 'spacy-token', 'stanza-doc': 'stanza-sentence', 'stanza-sentences': 'stanza-sentence', 'stanza-words': 'stanza-word'}
            bind(n.target, kinds.get(value(n.iter), ''))
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            for g in n.generators:
                if visit(g):
                    return True
            children = [n.key, n.value] if isinstance(n, ast.DictComp) else [n.elt]
        else:
            children = ast.iter_child_nodes(n)
        return any(visit(child) for child in children)
    return visit(tree)


def audit(repo='.', ignore=(), verbose=False):
    root = Path(repo)
    if not root.is_dir():
        raise OSError('Repository is not a directory: ' + str(root))
    sources, documents = [], []
    decisions = []
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in {'.git', '__pycache__', '.venv', 'venv', 'env'} and not (Path(directory) / d / 'pyvenv.cfg').exists() and not (Path(directory) / d).is_symlink() and not any((Path(directory) / d).relative_to(root).as_posix().startswith(p) for p in ignore))
        for name in sorted(files):
            path = Path(directory) / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or any(rel.startswith(p) for p in ignore):
                decisions.append(rel + ': ignored')
                continue
            test = 'tests' in Path(rel).parts[:-1]
            doc = rel == 'README.md' or (rel.startswith('docs/') and name.endswith('.md'))
            if name.endswith('.py') or doc or (test and name.endswith('.md')):
                text = path.read_text(encoding='utf-8')
                decisions.append(rel + ': scanned')
                if name.endswith('.py'):
                    sources.append(has_evidence(text))
                if doc or test:
                    documents.append((rel, text, test and not doc))
    evidence = any(sources)
    claims = [(rel, kind, phrase, test) for rel, text, test in documents for kind, phrase in phrase_matches(text)]
    shipped = any(kind == 'DEP' and not test for _, kind, _, test in claims)
    findings = []
    for rel, kind, phrase, test in claims:
        if (kind == 'DEP' and not evidence and not (test and shipped)) or (kind == 'NODEP' and evidence and not test):
            rule = 'documented-' + ('no-' if kind == 'NODEP' else '') + 'dependency-parsing-claim-false'
            findings.append(dict(rule=rule, verdict='MEDIUM' if test else 'HIGH', message='Documentation assertion conflicts with static source evidence.', path=rel, phrase=phrase))
    if verbose:
        import sys
        print('Scope: README.md, docs/**/*.md, tests fixtures, recursive Python sources', file=sys.stderr)
        for decision in decisions:
            print(decision, file=sys.stderr)
    return findings
