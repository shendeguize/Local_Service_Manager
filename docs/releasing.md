# Releasing LocalSM

This repository publishes the Python distribution `local-sm`, a GitHub
Release, and the npm launcher `@shendeguize/local-sm` from the same
version tag. The release workflow uses GitHub OIDC; no PyPI or npm token is
stored in the repository.

## One-time publisher setup

Before the first release, configure both registries:

1. On PyPI, add a pending trusted publisher for project `local-sm`:
   - owner: `shendeguize`;
   - repository: `Local_Service_Manager`;
   - workflow filename: `release.yml`;
   - environment: `pypi`.
2. On npmjs.com, configure the package
   `@shendeguize/local-sm` to trust GitHub Actions for the same owner,
   repository, workflow filename, and `pypi` environment. The package scope
   must be allowed to publish publicly. npm Trusted Publishing requires npm
   CLI 11.5.1+ and Node 22.14.0+; the workflow uses Node 24.

The GitHub repository must also allow Actions to create tags and releases.
The `pypi` environment should be protected if a manual approval gate is
desired.

## Release process

1. Run the **Release preparation** workflow with the next stable version.
2. Review the generated branch and fill in the new `CHANGELOG.md` entry.
3. Run `make release-preflight` locally and merge the pull request.
4. The **Tag release** workflow creates `vX.Y.Z` on the merged version.
5. The **Release** workflow validates the tag, verifies that it points to a
   commit reachable from `main`, builds the wheel and sdist, creates the
   GitHub Release, and publishes to PyPI and npm.
6. Verify the public installations:

```sh
uvx --from local-sm==X.Y.Z LocalSM --version
npx @shendeguize/local-sm --version
```

For the initial `v0.1.0`, create the tag after all release workflows and
trusted publishers are configured:

```sh
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

## Main branch protection

After the first CI workflow has run on GitHub, configure `CI status` as the
required check. The repository's agreed policy requires the check and blocks
direct pushes, but does not require a pull-request reviewer for this
single-maintainer repository. The setting can be applied with:

```sh
gh api --method PUT repos/shendeguize/Local_Service_Manager/branches/main/protection \
  --input -
```

Use the GitHub branch protection form for the JSON body, with
`required_status_checks.contexts` set to `["CI status"]`, strict checks
enabled, force pushes and deletions disabled, and
`required_pull_request_reviews` set to `null`.
