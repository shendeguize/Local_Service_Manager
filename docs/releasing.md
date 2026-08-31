# Releasing LocalSM

This repository publishes a GitHub Release and the npm package
`@shendeguize/local-sm` from the same version tag. The npm package includes
the matching Python wheel, so npm users do not depend on LocalSM being
published to PyPI. The release workflow uses GitHub OIDC; no npm token is
stored in the repository. PyPI publishing remains optional.

## One-time publisher setup

Before the first npm release, configure npm:

1. On npmjs.com, configure the package
   `@shendeguize/local-sm` to trust GitHub Actions for the same owner,
   repository, and workflow filename. The package scope must be allowed to
   publish publicly. npm Trusted Publishing requires npm CLI 11.5.1+ and
   Node 22.14.0+; the workflow uses Node 24.

The GitHub repository must also allow Actions to create tags and releases.
Configure the `npm` environment for the npm trusted publisher. Configure the
`pypi` environment only if PyPI publishing is enabled later.

## Release process

1. Run the **Release preparation** workflow with the next stable version.
2. Review the generated branch and fill in the new `CHANGELOG.md` entry.
3. Run `make release-preflight` locally and merge the pull request.
4. The **Tag release** workflow creates `vX.Y.Z` on the merged version.
5. The **Release** workflow validates the tag, verifies that it points to a
   commit reachable from `main`, builds the wheel and sdist, creates the
   GitHub Release, embeds the wheel in the npm package, and publishes npm
   through the `npm` environment. No local `npm publish` is required. PyPI
   remains skipped for tag pushes; after configuring its publisher, run the
   workflow manually with `publish_pypi` enabled.
6. Verify the public installation:

```sh
npx @shendeguize/local-sm --version
```

For the initial release, use the **Release preparation** workflow and merge
its pull request. The **Tag release** and **Release** workflows then run
automatically.

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
