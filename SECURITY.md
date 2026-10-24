# Credentials and upload policy

No actual passwords, Home Assistant tokens, API keys or private keys may be sent to GitHub, including private repositories, commits, issues, Actions secrets and artifacts.

Before an upload, run Secret Guard against the exact outgoing file contents AND commit/PR text, then review the diff manually. The guard reports paths, line numbers and rule names only, never matching values. Any finding, decoding error, unsupported payload or scanner failure blocks upload.

Input to tools/secret_guard.py is a UTF-8 JSON object with a nonempty "files" mapping (repository path to complete text) and optional "message" text. Feed this via stdin; do not use real secrets as command arguments. This also supports GitHub API edits without a local checkout.

For development in a Git checkout, additionally run Gitleaks with redaction over outgoing commits before pushing. Do not rely on .gitignore or a remote workflow as the upload gate: neither prevents secrets in already-tracked files or API writes. No scanner provides an absolute guarantee, so manual review remains mandatory.

Runtime configuration is supplied manually during installation or later configuration. The bootstrap does not request, generate or copy credentials and does not connect to Home Assistant. The user permits runtime credentials locally on the installation LXC. Store private configuration outside the source tree in /etc/simpleinventory-webui/app.env, owned by root with mode 0600, read by the eventual systemd service. Do not create real values until manually configured. Updates must preserve this file.

The future application must keep the HA token server-side, redact authorization data, validate input and protect authenticated write operations against CSRF. Do not automatically retry an inventory mutation after an ambiguous connection failure; first reconcile with HA to avoid double additions or removals.
