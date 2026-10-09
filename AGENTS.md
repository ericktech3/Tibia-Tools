# AGENTS
- Fetchers return core.result.Result (ok/kind/stale/age); UI shows result.user_message(). Why: consistent, friendly errors and data-age display.
- Parsers live in integrations/parsers/ with no network calls. Why: testable with saved HTML.
- Screen rules without Kivy live in features/<screen>/logic.py; main.py only wires UI. Why: shrink main.py and allow unit tests.
- CI (.github/workflows/ci.yml) runs compile, pyflakes (undefined names), KV tab check and unittest on every push. Why: catch breakage before building the APK.
- Long informational rows use wrapping labels with texture-driven height. Why: deaths and empty-filter messages must remain readable on narrow screens.
- Shared toolbar alignment is applied after KivyMD calculates its height, and KV fallback mirrors the current screen files. Why: normal and emergency layouts must preserve the same positioning fixes.
- GitHub cover art lives in docs/github/ as an optimized JPG referenced by README.md, and repo-owner links point at the real GitHub account. Why: the README stays light and every badge and link resolves to the live repository.

- App integrations must call `core.http_client.get`, never patch or rely on a patched global `requests.get`. Why: global patching made cache behavior leak into unrelated code and hid intermittent bugs.
- Everything written to the crash log passes through `services.error_reporting.redact`; logs stay on-device and are shared only by explicit user action. Why: privacy.
