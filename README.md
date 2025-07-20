# Nativelink Benchmarks
This benchmark uses [Change Point Detection](https://en.wikipedia.org/wiki/Change_detection) (CPD) to catch regressions in performance. The CPD calculations[^1] are done using the (incubating) [Apache Otava](https://github.com/apache/otava) project currently at v0.6.0. Otava is written in Python.


## Apache Otava
The tool supports posting results it finds to Slack, if a valid [`SLACK_BOT_TOKEN`](https://github.com/apache/otava/blob/9bce358eb9e27d5b11e23b0667c452f3bf189dc8/otava/resources/otava.yaml#L27-L28) is added to the `otava.yaml` config file.

## Target Repo
The OSS project adopted for the Nativelink benchmarks is the [LLVM project](https://github.com/llvm/llvm-project). LLVM is massive C/C++ monorepo that is well-known among developers as platform for building compiler toolchains. 

Picking a recognizable monorepo like LLVM should hopefully illustrate the immense value of Bazel's remote caching (and execution) features as a means of shortening build times drastically.

### Competing Build Systems
A major reason for selecting the LLVM project is due to its support of two different build systems for building the monorepo:
* CMake — the main build system which is officially supported by the project maintainers and;
* Bazel[^2] — an [experimental](https://github.com/llvm/llvm-project/tree/main/utils/bazel) but fully functional alternative build system supported by the community.

---

## Deployment
Using the GitHub CLI tool [`gh`](https://cli.github.com/) to setup and trigger all the GitHub Actions that make up the benchmarks is significantly faster than using the web interface, so the bulk of this section will use it for most tasks and thus assumes you already have a recent version (v2.74.2+) of `gh` installed locally.

1. Your current `gh` session should have these permissions:
   - `read:packages`;
   - `write:packages`;
   - `delete:packages`;
   - `repo`;
   - `workflow`;
   
   for the next CLI actions to succeed.
   
   1a. If you are not logged in via `gh` yet, log in with the necessary permissions:
    ```sh
      gh auth login --scopes "read:packages,write:packages,delete:packages,repo,workflow"
    ```

   1b. If you are already logged in, check that you have the necessary permissions using `gh auth status`:
    ```sh
      gh auth status    

      github.com
        ✓ Logged in to github.com account ayewo (/Users/<user>/.config/gh/hosts.yml)
        - Active account: true
        - Git operations protocol: https
        - Token: gho_************************************
        - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
    ```

    1c. If some of those permissions are missing like in the output above, add them to your current session using `gh auth refresh`:
     ```sh
      gh auth refresh --scopes "read:packages,write:packages,delete:packages"
    ```

    1d. Confirm that all necessary permissions have been added to your current session via `gh auth status`:
     ```sh
      gh auth status

      github.com
        ✓ Logged in to github.com account ayewo (keyring)
        - Active account: true
        - Git operations protocol: https
        - Token: gho_************************************
        - Token scopes: 'delete:packages', 'gist', 'read:org', 'repo', 'workflow', 'write:packages'
    ```

2. Clone the code for the benchmarks locally:
  ```sh
    cd /tmp
    git clone https://github.com/ayewo/nativelink-rbe-benchmarks -b main --single-branch nativelink-rbe-benchmarks
  ```

3. Reset the cloned repo's `./git` folder by removing it and adding a new one with your own `git config`:
  ```sh
    cd nativelink-rbe-benchmarks/
    rm -rf .git/
    git init
    git config user.name "ayewo" && git config user.email "ayewo@users.noreply.github.com"
    git add .
    git commit -m "Initial commit [skip ci]"
  ```

4. Create a new repo from the cloned repo and push the code to GitHub:
   ```sh
    gh repo create --source=. --public --push
   ```
5. Enable GitHub Pages for the newly created repo. We will change the defaults for "Build and deployment" so that the static HTML files are automatically built and published to GitHub Pages anytime the benchmarks are run. We will make the following changes as part of the enablement:
   - change the `"source"` (i.e. `"build_type"`) from "Deploy from a branch" (i.e. `"legacy"`) to "GitHub Actions" (i.e. `"workflow"`);
   - set the `"source[branch]"` to `"main"`;
   - set the `"source[path]"` to `"/"`;
  ```sh
    gh api \
     -X POST \
     -H "Accept: application/vnd.github+json" \
     -H "X-GitHub-Api-Version: 2022-11-28" \
     "/repos/ayewo/nativelink-rbe-benchmarks/pages" \
     -f "build_type=workflow" \
     -f "source[branch]=main" \
     -f "source[path]=/"
  ```
  ```sh
    {
    "url": "https://api.github.com/repos/ayewo/nativelink-rbe-benchmarks/pages",
    "status": null,
    "cname": null,
    "custom_404": false,
    "html_url": "https://ayewo.github.io/nativelink-rbe-benchmarks/",
    "build_type": "workflow",
    "source": {
      "branch": "main",
      "path": "/"
    },
    "public": true,
    "protected_domain_state": null,
    "pending_domain_unverified_at": null,
    "https_enforced": true
  }
  ```
 
6. Now set `ubuntu-22.04-rbe-worker` as the RBE [custom image](https://www.nativelink.com/docs/nativelink-cloud/rbe#custom-images) name to be used for the remote execution part of the benchmarks:
  ```sh
    gh variable set NATIVELINK_WORKER_DOCKER_IMAGE --body "ubuntu-22.04-rbe-worker"
  ```

7. The custom image is a Docker image containing dependencies needed by Nativelink's RBE worker. It will be built and be published to `ghcr.io` by this workflow:
  ```sh
    gh workflow run 01-docker-rbe-worker.yml
  ```

8. After the Docker image has been built and published, confirm that it is publicly accessible via `docker pull`.
   
   8a. Run `docker pull ...` locally:
     ```sh
       docker pull ghcr.io/ayewo/ubuntu-22.04-rbe-worker:latest
       latest: Pulling from ayewo/ubuntu-22.04-rbe-worker
       89dc6ea4eae2: Pulling fs layer
       93e65aed90f6: Pulling fs layer
       5e62ee7e7765: Pulling fs layer
       ...
      ```
   8b. If it is not public, you can make it public from the web interface: _GitHub profile_ → _Packages_ → _select package "ubuntu-22.04-rbe-worker"_ → _Package settings_ → _Change visibility_

9. Setup the Nativelink API key as a repo secret (or visit [secrets/actions](https://github.com/ayewo/nativelink-rbe-benchmarks/settings/secrets/actions) page):
  ```sh
    gh secret set NATIVELINK_HEADER_API_KEY --body "x-nativelink-api-key=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  ```

10. Setup several variables as repo variables (or visit [variables/actions](https://github.com/ayewo/nativelink-rbe-benchmarks/settings/variables/actions) page):
  ```sh
    gh variable set NATIVELINK_HEADER_PROJECT_NAME --body "x-nativelink-project=nativelink-rbe-benchmarks"
    gh variable set NATIVELINK_HEADER_REMOTE_EXECUTOR --body '"container-image=docker://ghcr.io/ayewo/ubuntu-22.04-rbe-worker:latest"'
    gh variable set NATIVELINK_URL_REMOTE_CACHE --body "grpcs://cas-<user-domain-hostname>.build-faster.nativelink.net"
    gh variable set NATIVELINK_URL_BES_BACKEND --body "grpcs://bes-<user-domain-hostname>.build-faster.nativelink.net"
    gh variable set NATIVELINK_URL_BES_RESULTS --body "https://app.nativelink.com/a/<user-domain>/build"
    gh variable set NATIVELINK_URL_REMOTE_EXECUTOR --body "grpcs://scheduler-<user-domain-hostname>.build-faster.nativelink.net:443"
  ```

11. Create output files needed by the benchmarks:
  ```sh
    gh workflow run 02-bazel-baseline.yml
  ```
12. Run the benchmarks proper:
  ```sh
    gh workflow run 03-bazel-benchmarks.yml
  ```
13. The building of the Astro-based static website will be triggered automatically when the benchmarks run to completion.

To view it, please visit: https://ayewo.github.io/nativelink-rbe-benchmarks/




## Footnotes
[^1]: The statistical [analysis](https://github.com/apache/otava/blob/9bce358eb9e27d5b11e23b0667c452f3bf189dc8/otava/analysis.py) uses [Student's T-test](https://en.wikipedia.org/wiki/Student%27s_t-test). Inspiration to use Apache Otava came from this InfoQ presentation: [Practical Benchmarking: How to Detect Performance Changes in Noisy Results](https://www.infoq.com/presentations/noise-tips/) which introduced an OSS [analysis](https://github.com/apache/otava/blob/ef6f9bd22cf09555edf4372cd988634acbad7fab/hunter/analysis.py) tool called "Hunter". The project would later be renamed to Apache Otava and it turns out that there's also an implementation in the Lucene benchmarks in [`benchUtil.py#simpleReport()`](https://github.com/mikemccand/luceneutil/blob/a75b8a4d3a8c146f3ff7e6695ab6bbf2e34e4b90/src/python/benchUtil.py#L1387-L1468) of the ["Student's T-Test"](https://github.com/mikemccand/luceneutil/blob/a75b8a4d3a8c146f3ff7e6695ab6bbf2e34e4b90/src/python/benchUtil.py#L1467).
[^2]: The [LLVM project](https://github.com/llvm/llvm-project) is primarily built using CMake, but in 2021, a [proposal](https://github.com/llvm/llvm-www/blob/main/proposals/LP0002-BazelBuildConfiguration.md) seeking to add an alternative way of building the LLVM monorepo was accepted. For years, Google had been maintaining [`llvm-bazel`](https://github.com/google/llvm-bazel) to allow them build the LLVM monorepo internally using Bazel (instead of the official build system based on CMake), so once the proposal was accepted, code from the `llvm-bazel` repo was merged into `llvm-project`.

