# Releasing LocalSM

This repository publishes a GitHub Release and the npm package
`@shendeguize/local-sm` from the same version tag. The npm package includes
the matching Python wheel, so npm users do not depend on LocalSM being
published to PyPI. The release workflow uses GitHub OIDC; no npm token is
stored in the repository. PyPI publishing remains optional.

## One-time publisher setup

Before the first automated npm release, configure npm. A trusted publisher can
only be attached to a package that already exists on the registry, so the very
first version of a new package has to be published manually once:

```sh
make package-npm
npm publish ./packages/npm --access public
```

Then attach GitHub Actions as the trusted publisher for
`@shendeguize/local-sm`, either on npmjs.com or with `npm trust github`. Use
this repository's owner and name, workflow filename `release.yml`, and
environment `npm`, and grant the publish permission. The scope must be allowed
to publish publicly. `npm trust` requires npm CLI 11.10+ and account-level 2FA;
the release workflow itself runs Node 24.

On the GitHub side, the repository needs the `npm` environment, permission for
Actions to create tags and releases, and permission for Actions to create pull
requests (used by the release preparation workflow). Configure the `pypi`
environment only if PyPI publishing is enabled later.

## Release process

1. Run the **Release preparation** workflow with the next stable version.
2. Review the generated branch and fill in the new `CHANGELOG.md` entry.
3. Run `make release-preflight` locally and merge the pull request.
4. The **Tag release** workflow creates `vX.Y.Z` on the merged version and then
   dispatches the release workflow. A tag pushed with `GITHUB_TOKEN` does not
   raise a push event, so this explicit dispatch is what keeps the chain
   connected.
5. The **Release** workflow validates the tag, verifies that it points to a
   commit reachable from `main`, builds the wheel and sdist from the tag,
   creates the GitHub Release, embeds the wheel in the npm package, and
   publishes npm through the `npm` environment. No local `npm publish` is
   required. PyPI remains skipped unless the workflow is run manually with
   `publish_pypi` enabled.
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
