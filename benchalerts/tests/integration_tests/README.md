Integration tests
-----------------

These tests will interact with various services like GitHub and Conbench. To run only
these tests, do

    pytest -vv --log-level=DEBUG tests/integration_tests

To run tests that interact with GitHub, you need the following environment variables
configured correctly:

- `GITHUB_API_TOKEN` - a Personal Access Token that has at least the `repo:status`
    permission. Only used for the integration tests that need a PAT.

    If the token has insufficient permissions, the tests will fail with a 403.

    If this environment variable isn't found, the PAT tests will be skipped. This is
    currently the case in our GitHub Actions CI builds.
- `GITHUB_APP_ID` - the GitHub App ID of an App that was created following the
    instructions in the
    [main README](../../README.md#creating-a-github-app-to-work-with-benchalerts).
    The App must be installed on the `conbench` organization, with access to the
    `conbench/benchalerts` repository.

    If the App has insufficient permissions, the tests will fail with a 403.

    If this environment variable isn't found, the App tests will be skipped. This
    variable is populated in our GitHub Actions CI builds, so some of these tests are
    run in CI.
- `GITHUB_APP_PRIVATE_KEY` - the contents of the private key file of the same app as
    above.

    If this environment variable isn't found, the App tests will be skipped.
- `CI` - this env var must *NOT* be set, or the tests that post comments to PRs will be
    skipped. By default, `CI=true` in GitHub Actions, so we'll never run these PR
    comment tests in the CI build. (We still run other GitHub App-authenticated
    integration tests.)

License information
-------------------

Copyright (c) 2022, Voltron Data.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
