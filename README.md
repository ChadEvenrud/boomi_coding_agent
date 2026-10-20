# Boomi Coding Agent

A starter kit that turns an AI coding agent (Claude Code, Cursor, Codex, etc.) into a Swinerton Boomi integration developer. Clone this repo, add your Boomi credentials, and the agent can design, build, review, push and deploy Boomi processes that follow Swinerton's integration standards.

It contains no application of its own. It bundles three things the agent works from:

1. **Agent skills**: instructions, reference docs and CLI scripts that teach the agent how to work with the Boomi platform and how Swinerton builds integrations.
2. **Process templates**: the Swinerton Producer, Router and Consumer templates exported from Boomi, which new processes are cloned from.
3. **Best practices**: [swinerton_best_practices.md](swinerton_best_practices.md), the rules every design must follow.

## Architecture the agent builds

Every standard Swinerton integration follows one asynchronous pattern:

```text
Producer -> EBO -> EBS Router -> Boomi Atom Queue -> Consumer
```

- **Producer** (source side) extracts source data, maps it to an Enterprise Business Object (EBO) and routes it to the EBS Router.
- **EBS Router** receives the EBO and sends it to one point-to-point queue per consuming application.
- **Consumer** (target side) listens on its queue, maps the EBO to the target format and calls the target system.
- **Error handling**: every Producer and Consumer sends failures through the shared Generic Notification & Audit framework.

## Repository layout

```text
boomi_coding_agent/
├── .claude/skills/              Skills for Claude Code (loaded automatically)
├── .agents/skills/              The same skills, for other coding agents
├── process_template/            Swinerton process templates pulled from Boomi
├── swinerton_best_practices.md  Swinerton Boomi standards for the agent
├── .env.example                 Template for your credentials
└── .gitignore                   Keeps .env out of git
```

### Skills

| Skill | What it does |
| --- | --- |
| `boomi-integration` | Core Boomi framework: CLI scripts to search, pull, create, push, deploy and test components, plus Boomi reference docs. |
| `boomi-marketplace` | Searches and installs recipes from the Boomi Marketplace as reference samples. |
| `swinerton-producer` | Builds and reviews Producer processes. |
| `swinerton-ebs-router` | Builds and reviews EBS Router processes. |
| `swinerton-consumer` | Builds and reviews Consumer processes. |
| `swinerton-error-handling` | Swinerton Try/Catch, notification and audit standard. |

`.claude/skills` and `.agents/skills` hold identical copies. **If you change a skill, change it in both folders.**

### Process templates

| Folder | Contents |
| --- | --- |
| `process/` | `Producer_Source_System_BusinessObject`, `Router_BusinessObject`, `Consumer_Target_System_BusinessObject` |
| `processproperty/` | `Common Props` process properties |
| `profile.xml/`, `profile.flatfile/`, `transform.map/` | Generic Notification & Audit profile and map used by error handling |
| `connector-settings/`, `connector-action/` | Sample MySQL STMCC connection and operation |
| `inventories/` | What was pulled from Boomi, with component IDs |
| `import_templates.py` | Script that refreshes the templates from Boomi |

## Prerequisites

- An AI coding agent, such as [Claude Code](https://claude.com/claude-code).
- A Boomi account with Platform API access and an API token.
- `bash`, `curl` and `jq`. On Windows, use Git Bash; install `jq` with `winget install jqlang.jq`.
- Python 3.9+ (standard library only), for `import_templates.py` and `boomi-profile-inspect.py`.

## Setup

1. **Clone the repo**

   ```bash
   git clone https://github.com/ChadEvenrud/boomi_coding_agent.git
   cd boomi_coding_agent
   ```

2. **Create your `.env`**

   ```bash
   cp .env.example .env
   ```

   Fill in the values:

   | Variable | Required | Purpose |
   | --- | --- | --- |
   | `BOOMI_API_URL` | Yes | Boomi Platform API base URL, e.g. `https://api.boomi.com` |
   | `BOOMI_USERNAME` | Yes | Your Boomi user name |
   | `BOOMI_API_TOKEN` | Yes | Boomi API token (Settings → Account Information → Platform API Tokens) |
   | `BOOMI_ACCOUNT_ID` | Yes | Boomi account ID |
   | `BOOMI_VERIFY_SSL` | No | `true` unless told otherwise |
   | `BOOMI_TARGET_FOLDER` | No | Default Boomi folder for new components |
   | `BOOMI_ENVIRONMENT_ID` | For deploys | Environment to deploy to |
   | `BOOMI_TEST_ATOM_ID` | For tests | Runtime used for test executions |
   | `SERVER_*` | For web services | Shared Web Server URL and credentials (`SERVER_AUTH_TYPE`: `basic`, `bearer` or `none`) |

   Never commit `.env`. `.gitignore` already excludes it.

3. **Check your settings.** From the repo root, run this to see which `.env` variables are set (values are not printed):

   ```bash
   bash .claude/skills/boomi-integration/scripts/boomi-env-check.sh
   ```

   The scripts read `.env` from the current directory, so always run them (and your agent) from the repo root.

## How to use it

### With Claude Code

Open the repo folder in Claude Code. It loads the skills from `.claude/skills` automatically. Point it at the best-practices file in your first message, or copy the file into a `CLAUDE.md` so it is always loaded.

Then describe what you need in plain language. For example:

- *"Build a Producer that pulls new vendors from Viewpoint and routes a Vendor EBO to the Vendor EBS. Follow swinerton_best_practices.md."*
- *"Add a Procore consumer to the Job EBS router."*
- *"Create a Consumer that listens on the Employee queue and upserts into the STMCC MySQL database."*
- *"Review process `<component ID>` against Swinerton standards."*
- *"Search the Boomi Marketplace for a Salesforce to NetSuite recipe."*

A typical session goes like this:

1. The agent reads the relevant skill and the best practices.
2. It clones the matching template from `process_template/`, or pulls existing components from Boomi.
3. It builds and edits the component XML locally in `active-development/`.
4. It pushes the components to Boomi, then deploys and tests them if you have set the environment and runtime IDs.
5. It checks its work against the self-validation checklist in the best-practices file.

Whether the agent asks before it pushes or deploys to Boomi depends on your agent's permission settings. Review what it plans to push before you approve it.

### With other coding agents

Point your agent at `.agents/skills/` and at `swinerton_best_practices.md`. For example, reference them from your agent's rules file (`AGENTS.md`, `.cursor/rules`, etc.). Each skill's entry point is its `SKILL.md`.

### Running the Boomi scripts directly

The scripts in `.claude/skills/boomi-integration/scripts/` also work without an agent. For example:

```bash
S=.claude/skills/boomi-integration/scripts
bash $S/boomi-component-search.sh   # find components
bash $S/boomi-component-pull.sh     # download a component's XML
bash $S/boomi-component-push.sh     # upload local changes
bash $S/boomi-deploy.sh             # package and deploy a process
bash $S/boomi-test-execute.sh       # run a process on the test runtime
```

See [.claude/skills/boomi-integration/README.md](.claude/skills/boomi-integration/README.md) for the full tool list and options.

### Refreshing the templates

If the templates change in Boomi, pull them again:

```bash
python process_template/import_templates.py
```

The script finds the Boomi folder named `Templates`, pulls every process in it along with the components each one references, and rewrites `process_template/` and its inventories. It reads `.env` from the repo root.

## Security notes

- Keep this repository **private**. `process_template/connector-settings/MySQL STMCC.xml` contains the STMCC database address, user name and an encrypted password.
- Credentials belong only in `.env`, which is git-ignored.
- Use your own Boomi API token. Don't share tokens between developers.

## Credits

`boomi-integration` and `boomi-marketplace` come from Boomi's official repositories ([OfficialBoomi/boomi-integration](https://github.com/OfficialBoomi/boomi-integration), [OfficialBoomi/boomi-marketplace](https://github.com/OfficialBoomi/boomi-marketplace)); see their `LICENSE` files. The Swinerton skills, templates and best practices are Swinerton internal standards.
