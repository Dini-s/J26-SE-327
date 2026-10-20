# GitHub App push integration

The local dashboard supports two connection modes: public repository URL imports use
60-second polling; repositories connected through the GitHub App use signed push
webhooks. App mode does not poll GitHub for new commits. A local queue worker wakes to
process received events and finish/retry existing jobs. This is a single-user local
dashboard, not a multi-user hosted OAuth service.

## Server configuration

Configure these in `project/.env` (never commit it):

```
GITHUB_APP_ID=<numeric app ID>
GITHUB_APP_CLIENT_ID=<app client ID>
GITHUB_APP_PRIVATE_KEY_PATH=<absolute path to downloaded PEM file>
GITHUB_WEBHOOK_SECRET=<random secret shared with GitHub>
GITHUB_WEBHOOK_PORT=8001
```

The private key remains in its existing local file; only its path is stored. RS256
requests are signed with OpenSSL. Installation tokens are generated when needed and
passed to Git through its process environment, never stored in remotes or checkpoints.
No client secret or user OAuth token is required for this single-user installation flow.

## Install and select repositories

1. In GitHub App settings grant Contents read-only, retain Metadata read-only, and
   subscribe to Push. Install the App and select repositories you own or administer.
2. In the dashboard choose **Add a project → Connect GitHub / Refresh repositories**.
   Use **Install Aspire on GitHub / Manage repository access** if not installed yet.
3. Refresh the repository list, select a repository and its branch, and add it.
   A branch left unspecified resolves to the default branch at import time.
4. For a project already imported, use **Code changes → Enable GitHub App webhooks**
   after installing the App on that repository. This preserves its project key and links.

A third party's public repository cannot deliver your App push events unless its owner
installs the App. Public URL imports retain polling for this reason.

## Public webhook URL for a local demo

Start the API normally from `project`:

```sh
.venv/bin/python -m apps.api.server
```

When a webhook secret is configured, the server also starts a dedicated receiver at
`127.0.0.1:8001`. It exposes only `POST /api/github/webhook`, not dashboard APIs.

For a temporary Cloudflare Quick Tunnel on macOS:

```sh
brew install cloudflared
cloudflared tunnel --url http://127.0.0.1:8001
```

Keep that terminal running. In GitHub App settings enable Webhook Active and enter:

```
https://<generated-host>.trycloudflare.com/api/github/webhook
```

Set GitHub's Secret to the exact `GITHUB_WEBHOOK_SECRET` in the local `.env`, keep SSL
verification enabled, and save. A Quick Tunnel URL changes when restarted; update the
App webhook URL accordingly. Use a stable deployment/tunnel for longer-running use.

To copy the existing secret on macOS without displaying it, run this from `project`:

```sh
.venv/bin/python -c "from dotenv import dotenv_values; import subprocess; subprocess.run(['pbcopy'], input=dotenv_values('.env')['GITHUB_WEBHOOK_SECRET'].encode(), check=True)"
```

## Verify the demo

Generate initial trace links, then push a meaningful source change to the selected
branch. GitHub App settings → Advanced → Recent Deliveries should show a successful
2xx response. The dashboard shows queued sync, fetched commits, and the resulting drift
checks. Another branch, tag, repository or installation cannot trigger this project.

Webhook requests are authenticated against their exact raw bytes using HMAC SHA-256.
Deliveries are durably queued in SQLite and deduplicated by delivery ID. The HTTP receiver
acknowledges before doing Git or AI work. Events arriving during an analysis remain
queued. Commit checkpoints advance only after successful C4 completion; failed work is
retried after restart. Keep the API and public tunnel running.

References:
- https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
- https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app
- https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
