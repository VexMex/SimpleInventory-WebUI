# Project instructions

- Work in VexMex/SimpleInventory-WebUI through the GitHub connector. Do not create a local project checkout unless the user explicitly changes this preference. In-memory validation on the user's computer is allowed.
- Never read real credentials into generated source, examples, tests, commit messages, issues, screenshots, or logs.
- Before EVERY upload, including create_file, update_file, create_blob, create_tree and PR text: scan the EXACT outgoing text with tools/secret_guard.py, inspect the outgoing diff, and stop on any finding or scanner failure. Scanning after upload is too late.
- Secret Guard is a conservative heuristic, not proof that arbitrary content is safe. Also manually review credentials, URLs, examples and high-entropy strings. Never bypass a finding with an allowlist to make an upload pass.
- For a Git checkout, additionally require Gitleaks scanning of outgoing commits before push. GitHub Actions alone cannot prevent a secret reaching GitHub.
- Keep credentials out of GitHub entirely, including GitHub Actions secrets and artifacts. Runtime settings must be supplied manually after installation. The user permits local storage on the installation LXC, outside the repository, with restricted permissions.
- Never request credentials in chat. Do not put them into commands, shell history, query strings, frontend code or browser storage.
- Do not copy local .env files, SSH keys, HA backups, exports or logs into the repository.
- A deployment must keep code separate from private runtime configuration, and preserve private settings on updates.
- Do not change repository visibility, install on Proxmox, create a container or provision credentials without a corresponding user request.
