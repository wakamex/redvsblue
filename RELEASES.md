# Website releases

The version in `pyproject.toml` identifies the site's code, methodology, and presentation. [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) publish the committed notes; the production footer identifies the release actually deployed. The shared [release policy](https://github.com/wakamex/pacman/blob/main/RELEASE_POLICY.md) defines the release gates and immutable tags.

## Validation and build

The repository uses [uv](https://docs.astral.sh/uv/) with the committed lockfile and Python version. Run `uv run --locked pytest -q` to run the complete test suite. `uv run --locked python -m rb.release build --output reports/preview-site` creates a development build in a new directory. It downloads fresh inputs into a temporary workspace, computes and validates the results, and records their provenance. Set `FRED_API_KEY` in the environment or local `.env` file. The build includes the static site and generated data; it does not distribute downloaded source files.

The data manifest records the generating commit and release, input URLs, retrieval times, content hashes, available upstream modification dates, effective inference settings, normalized-input hashes, and the generated data hash. Production builds require an annotated tag matching the manifest version and an unchanged checkout. Development builds have no release link.

## Release and deployment controls

Prepare `release-notes/vX.Y.Z.md` and commit only the version, lockfile, and notes as `Release vX.Y.Z`. Push `main`, wait for `release-eligible / validate` on that exact commit, confirm remote `main` still matches, then push the annotated tag when authorized. For the first release, retain the existing version.

`publish.yml` validates, builds from the tag with fresh inputs, uploads the site artifact for 90 days, creates the immutable release from the notes, and conditionally deploys the same artifact to [Cloudflare Pages](https://developers.cloudflare.com/pages/). Main pushes never deploy production. Publishing release notes does not establish that a version has been deployed.

The repository variable `PRODUCTION_DEPLOY_ENABLED` must equal `true` for any production deploy or scheduled refresh. A missing variable or any other value keeps production unchanged. This permits building and publishing a release while holding deployment. The variable is currently held at `false` until deployment is authorized.

After deployment is authorized, set the variable to `true` and manually run `deploy-site.yml` with the successful publish workflow's numeric `run_id`. It verifies the artifact's release identity, static files, and data hash before deploying. This also supports an explicit rollback to a retained earlier release artifact. If an artifact has expired, rerun its tag publication workflow to rebuild with the same released code and fresh inputs; existing release notes remain unchanged. Do not move a tag.

`refresh-data.yml` runs weekly or manually. Inside the shared production concurrency group, it reads production's version manifest, verifies its annotated tag and commit, checks out that code, runs tests, and regenerates the site with fresh inputs. It fails if production's identity is missing or inconsistent. The initial release deployment supplies the first version manifest. Refresh artifacts are retained for 90 days; refreshes do not commit generated snapshots back to the development branch.

Release publication, explicit deployment, and refreshes share the `production-site` concurrency group with cancellation disabled. This prevents an in-progress refresh from overwriting a newer release deployment. Preview builds and validation do not publish a production artifact.
