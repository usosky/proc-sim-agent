# Publishing checklist (GitHub, GitLab, Zenodo, plugin directory)

## Before every release

- [ ] README shows the AuSpire logo and the EU emblem (`assets/`), and the acknowledgment text is
      unchanged (EU rules: https://commission.europa.eu/funding-and-tenders/managing-your-project/communicating-and-raising-eu-visibility_en).
- [ ] `python -m pytest -q` passes; `claude plugin validate --strict .` and
      `claude plugin validate --strict plugins/aspen-plus` pass.
- [ ] `python tools/scrub_aspen_files.py --check examples` reports nothing.
- [ ] No help files, indexes or private models in the tree: `git status`, `.gitignore`.

## GitHub (primary)

1. Create `usosky/proc-sim-agent` (private while reviewing, no template files), then
   `git remote add origin https://github.com/usosky/proc-sim-agent.git && git push -u origin main`.
2. Review the repository on GitHub, then Settings > General > Danger Zone > Change visibility >
   Public.
3. Settings > About: description, topics (`aspen-plus`, `process-simulation`,
   `chemical-engineering`, `claude-code`, `claude-skills`), website = Zenodo DOI once it exists.
4. Check that `/plugin marketplace add usosky/proc-sim-agent` works from a clean Claude Code.

## GitLab (mirror)

The workflow `.github/workflows/gitlab-mirror.yml` pushes `main` and tags to GitLab after every
push. It works on GitLab Free:

1. Create an empty GitLab project (no README), e.g. `gitlab.com/usosky/proc-sim-agent`.
2. GitLab > avatar > Edit profile > Access tokens: add a personal access token with the scope
   `write_repository` and an expiry date. (Project access tokens and pull mirroring need GitLab
   Premium on gitlab.com.)
3. GitHub > repository Settings > Secrets and variables > Actions > New repository secret:
   `GITLAB_TOKEN` = the token, `GITLAB_REPO` = `gitlab.com/usosky/proc-sim-agent.git`.
4. The next push to `main` (or a re-run of the workflow) fills the GitLab project. Renew the token
   before it expires.

Without the secrets the workflow skips itself.

## Zenodo (DOI)

1. Once the repository is public: log in to Zenodo with GitHub; Account > GitHub; switch on
   `usosky/proc-sim-agent`.
2. Zenodo reads `.zenodo.json` (title, creator with ORCID, MIT, EU grant 101177949, the Joule
   paper as related work, AuSpire acknowledgment in notes).
3. GitHub > Releases > Draft a new release, tag `v0.1.0`, title "proc-sim-agent 0.1.0", notes from
   `CHANGELOG.md`. Publishing the release triggers the Zenodo archive and DOI.
4. Add the DOI badge to `README.md` and the DOI to `CITATION.cff` (`doi:` and
   `identifiers:`), then report the DOI in the AuSpire dissemination records.

## Releases

- Bump `version` in `plugins/aspen-plus/.claude-plugin/plugin.json` (and `__version__` in
  `fwlib/__init__.py`); the marketplace entry carries no version. Add a `CHANGELOG.md` entry;
  update `date-released` and `version` in `CITATION.cff`; publish a GitHub release `vX.Y.Z`
  (Zenodo adds a new version under the same concept DOI).
- Users update with `/plugin marketplace update proc-sim-agent` or
  `claude plugin update aspen-plus@proc-sim-agent`, or turn on auto-update for the marketplace in
  `/plugin` > Marketplaces.

## Plugin directories

- Anthropic's community marketplace: submit through the Console form
  https://platform.claude.com/plugins/submit (for individual authors; the claude.ai form needs a
  Team or Enterprise organization). Run `claude plugin validate --strict .` first. Once listed,
  users can also install with `/plugin marketplace add anthropics/claude-plugins-community` and
  `/plugin install aspen-plus@claude-community`.
- Community lists of Claude skills and plugins accept pull requests that add a line with the
  repository link and a one-sentence description.
