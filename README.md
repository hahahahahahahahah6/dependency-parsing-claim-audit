# Documentation claim auditor

An offline checker compares assertions about head-word links with Python source patterns. It uses only the standard library, reads files without executing them, and sends no telemetry or network requests. It writes no files.

## Usage

Requires Python 3.9 or newer.

```sh
python3 -m pip install dependency-parsing-claim-audit
dependency-parsing-claim-audit audit . --json
python3 -m dependency_parsing_claim_audit audit . --verbose --ignore vendor/ --ignore build/ --fail-on medium
dependency-parsing-claim-audit --version
```

The directory defaults to the current directory. Repeatable ignore prefixes skip relative paths. The scan reads the root readme, Markdown under the documentation directory, test fixtures, and recursive Python sources. Version control, cache and virtual environment directories are excluded.

Fenced code is excluded from prose; inline code counts. Exact case-insensitive substrings are selected longest first, with denial spans removed before positive assertions. Hyphens are preserved.

HIGH findings fail by default. Test-only positive assertions have MEDIUM severity and fail only at the medium threshold. Exit codes are 0 for a passing threshold, 2 for findings meeting it, and 1 for usage or input errors. JSON output is a list with rule, verdict, message, path and phrase fields. Verbose scope and file decisions go to standard error.

```text
documented-dependency-parsing-claim-false
documented-no-dependency-parsing-claim-false
```

## Evidence

The checked feature concerns head-word links in sentence structure. Imported aliases resolve within each module. Local function and class definitions shadow imports. Paired routes require construction, invocation and access to the resulting values in the same module, including token iteration.

```text
spacy.load + call + dep_ / head
stanza.Pipeline(processors="tokenize,depparse") + call + dependencies
stanza word iteration + deprel / head
24 exact generic call names
```

Imports, strings, comments, incomplete pairs and unrelated tasks do not establish evidence.

## Differentiation

Neighboring tools inspect other outputs:

```text
part-of-speech-tagging-claim-audit: per-token word-class labels vs head-word links
named-entity-recognition-claim-audit: typed entity spans vs head-word links
classification-claim-audit: single label vs head-word links
```

A word-class label describes an individual token. Typed spans locate named referents. A single label categorizes an input. This checker concerns assertions about head-word links.

## Limitations

Static pattern matching is not semantic judgement. Exact phrases miss paraphrases. Generic method names can cause false positives. Dynamic dispatch, wrappers and flow across files can be missed. Recognized source patterns do not prove runtime behavior or output quality. Unreadable or malformed scanned files produce an input error.

## Development

```sh
python3 -m unittest discover
python3 -m build
```

The source archive includes the test suite. Licensed under MIT.
