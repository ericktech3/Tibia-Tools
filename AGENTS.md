# AGENTS
- Fetchers return core.result.Result (ok/kind/stale/age); UI shows result.user_message(). Why: consistent, friendly errors and data-age display.
- Parsers live in integrations/parsers/ with no network calls. Why: testable with saved HTML.
- Screen rules without Kivy live in features/<screen>/logic.py; main.py only wires UI. Why: shrink main.py and allow unit tests.
- CI (.github/workflows/ci.yml) runs compile, pyflakes (undefined names), KV tab check and unittest on every push. Why: catch breakage before building the APK.
