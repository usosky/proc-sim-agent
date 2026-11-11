# Publishing checklist (GitHub, Zenodo, Anthropic's plugin directory, GitLab)

Order for the first public release: GitHub public, Zenodo switched on, release `v0.3.1` (DOI),
directory submission. The directory's validation can run earlier, while the repository is still
private (section 4).

## 1. Before every release

- [ ] One version in `plugins/proc-sim-agent/.claude-plugin/plugin.json`,
      `plugins/proc-sim-agent/plugin.json`, SKILL.md `metadata.version`, `fwlib/__init__.py`,
      `CITATION.cff` (with `date-released`) and `.zenodo.json`; the tests check that they agree.
      A `CHANGELOG.md` entry.
- [ ] `python -m pytest -q` passes (it includes the directory preflight). On a computer with
      Aspen Plus installed it also runs the local test on the official examples.
- [ ] `claude plugin validate --strict .` and
      `claude plugin validate --strict ./plugins/proc-sim-agent` pass.
- [ ] `python tools/scrub_aspen_files.py --check evals/cases` reports nothing.
- [ ] README shows the AuSpire logo and the EU emblem, and the acknowledgment text is unchanged
      (EU rules: https://commission.europa.eu/funding-and-tenders/managing-your-project/communicating-and-raising-eu-visibility_en).
- [ ] No help files, indexes, models or private files in the tree: `git status`, `.gitignore`.

## 2. GitHub

1. Merge the release PR and delete the merged branches.
2. Settings > General > Danger Zone > Change visibility > Public.
3. About: description, topics (`aspen-plus`, `process-simulation`, `chemical-engineering`,
   `agent-skills`, `claude-code`), website = the Zenodo DOI once it exists.
4. From a clean Claude Code: `/plugin install proc-sim-agent --marketplace usosky/proc-sim-agent`.

## 3. Zenodo (DOI)

1. Once the repository is public: log in to Zenodo with GitHub; Account > GitHub; switch on
   `usosky/proc-sim-agent`.
2. Zenodo reads `.zenodo.json` and ignores `CITATION.cff` when both exist: check the title,
   creator, licence, grant and notes there.
3. Optional rehearsal, because a published Zenodo record cannot be deleted. Before step 1, switch
   the repository on at sandbox.zenodo.org only, publish a GitHub release with a tag such as
   `v0.3.1-rc1`, look at the sandbox record, then delete that release and its tag on GitHub.
4. GitHub > Releases > Draft a new release: tag `v0.3.1` on `main`, title "proc-sim-agent 0.3.1",
   notes from `CHANGELOG.md`. Publishing the release creates the Zenodo record and the DOI.
5. Add the DOI badge to `README.md` and `doi:` to `CITATION.cff`, then report the DOI in the
   AuSpire dissemination records.

## 4. Anthropic's plugin directory

Portal: https://claude.ai/directory/manage (it replaced the Console form in September 2026). Read
the Anthropic Software Directory Terms and Policy before submitting:
https://support.claude.com/en/articles/13145338-anthropic-software-directory-terms and
https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy.

1. Icon: `plugins/proc-sim-agent/.claude-plugin/icon.png`, a square PNG (512 to 2048 px a side,
   under 2 MB; the tests check it). The directory takes the listing icon once: the first time the
   plugin is saved or submitted in the portal. Changing the file later does not change the
   listing. `claude plugin validate` reports a missing icon.
2. Connect GitHub in claude.ai. While the repository is private, validation also needs the Claude
   GitHub App on the repository and your consent to the source upload. Publishing needs the
   repository public.
3. Submit new > Plugin bundle. Repository `usosky/proc-sim-agent`; plugin path
   `plugins/proc-sim-agent`; branch or tag empty (the directory follows `main`).
4. Validate. Fix every finding marked Blocking, push, Re-validate. The error "Couldn't validate
   that repository" has three possible causes: a file name that is invalid on Windows or macOS,
   the plugin path, or a `.gitattributes` attribute.
5. Listing details come from `plugin.json` and the plugin folder's README. Data handling: answer
   from the README section "What it runs, reads, writes and sends" (the scripts send nothing, keep
   their indexes on the user's computer until the user deletes them, and are not aimed at people
   under 18).
6. Review and submit. When the version passes, select Publish; a reviewer publishes the first
   version.
7. Updates: merge to `main` with a higher `version`. The directory scans the new commit.
8. Before submitting, load the plugin once on each surface you list it for (Claude Code, and the
   Claude desktop app with a model folder connected).

## 5. GitLab (mirror)

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

## 6. Community lists

Community lists of skills and plugins accept pull requests that add the repository link and a
one-sentence description.
