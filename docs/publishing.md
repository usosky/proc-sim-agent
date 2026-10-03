# Publishing checklist (GitHub, GitLab, Zenodo, plugin directory)

## Before every release

- [ ] README shows the AuSpire logo and the EU emblem (`assets/`), and the acknowledgment text is
      unchanged (EU rules: https://commission.europa.eu/funding-and-tenders/managing-your-project/communicating-and-raising-eu-visibility_en).
- [ ] `python -m pytest -q` passes; `claude plugin validate --strict .` and
      `claude plugin validate --strict plugins/aspen-plus` pass.
- [ ] `python tools/scrub_aspen_files.py --check examples` reports nothing.
- [ ] No help files, indexes or private models in the tree: `git status`, `.gitignore`.

## GitHub (primary)

1. Create `usosky/modelaide` (private while reviewing, no template files), then
   `git remote add origin https://github.com/usosky/modelaide.git && git push -u origin main`.
2. Review the repository on GitHub, then Settings > General > Danger Zone > Change visibility >
   Public.
3. Settings > About: description, topics (`aspen-plus`, `process-simulation`,
   `chemical-engineering`, `claude-code`, `claude-skills`), website = Zenodo DOI once it exists.
4. Check that `/plugin marketplace add usosky/modelaide` works from a clean Claude Code.

## GitLab (mirror)

Either use GitLab's pull mirroring (GitLab project > Settings > Repository > Mirroring
repositories > `https://github.com/usosky/modelaide.git`, direction Pull), or the push workflow in
`.github/workflows/gitlab-mirror.yml`: create an empty GitLab project, a project access token with
`write_repository`, and add the repository secrets `GITLAB_TOKEN` (the token) and `GITLAB_REPO`
(for example `gitlab.com/usosky/modelaide.git`).

## Zenodo (DOI)

1. Once the repository is public: log in to Zenodo with GitHub; Account > GitHub; switch on
   `usosky/modelaide`.
2. Zenodo reads `.zenodo.json` (title, creator with ORCID, MIT, EU grant 101177949, the Joule
   paper as related work, AuSpire acknowledgment in notes).
3. GitHub > Releases > Draft a new release, tag `v0.1.0`, title "ModelAide 0.1.0", notes from
   `CHANGELOG.md`. Publishing the release triggers the Zenodo archive and DOI.
4. Add the DOI badge to `README.md` and the DOI to `CITATION.cff` (`doi:` and
   `identifiers:`), then report the DOI in the AuSpire dissemination records.

## Releases

- Bump `version` in `plugins/aspen-plus/.claude-plugin/plugin.json` and in
  `.claude-plugin/marketplace.json` together; add a `CHANGELOG.md` entry; update
  `date-released` and `version` in `CITATION.cff`; tag `vX.Y.Z`.
- Users update with `/plugin marketplace update modelaide`.

## Plugin directories

- Anthropic's plugin submission form: https://platform.claude.com/plugins/submit (link the
  GitHub repository; the marketplace manifest is at `.claude-plugin/marketplace.json`).
- Community lists of Claude skills and plugins accept pull requests that add a line with the
  repository link and a one-sentence description.
