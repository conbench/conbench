# benchalerts

A package to facilitate automated alerting based on Conbench data.

## Overview

This package is intended to make the following steps easier in CI. Before these steps,
it is assumed that an execution environment has performed a run of benchmarks and
submitted the results to Conbench.

- Hit the Conbench API to understand if there were any:
    - errors
    - regressions (with configuration for how these regressions may be detected)
    - improvements (with configuration for how these improvements may be detected)
- Format and submit a summary of these findings to various places (again, with
  configuration):
    - GitHub Status on a commit
    - GitHub Check on a commit with a Markdown summary

In the future, there will be more places to submit alerts/reports/summaries, and more
configuration possible.

Currently, the way to configure these workflows in CI is to create and run a Python
script that imports this package and runs a workflow, like so:

```python
import os
from benchalerts import update_github_check_based_on_regressions

update_github_check_based_on_regressions(
    contender_sha=os.environ["GITHUB_SHA"], repo="my_org/my_repo"
)
```

See the docstrings of each function for more details on how to configure the workflow,
including how to set up the required environment variables.

## GitHub App Authentication

The preferred method that `benchalerts` recommends for authenticating and posting to
GitHub is to use a machine user called a [GitHub
App](https://docs.github.com/en/developers/apps/getting-started-with-apps/about-apps).
Using an App will allow you to post using a "bot" entity without taking up a seat in
your organization, and will allow you to use the extra features of the [Checks
API](https://docs.github.com/en/rest/guides/getting-started-with-the-checks-api). These
features give much more context when analyzing benchmark runs.

Each Conbench server must create its own GitHub App for security reasons. To do so,
follow these instructions.

### Creating a GitHub App to work with `benchalerts`

1. Go to the official [GitHub
    instructions](https://docs.github.com/en/developers/apps/building-github-apps/creating-a-github-app)
    for creating an App.
    - If you are an admin of your GitHub organization, follow the instructions for "a
        GitHub App owned by an organization." This method is preferred because the org
        will own the app instead of a user, who may not be part of the org in the
        future. (This will not affect the identity of the bot that posts to GitHub, just
        the ownership of the App.)
    - If not, you can follow the instructions for "a GitHub App owned by a personal
        account." You will send an installation request to org admins after creating the
        app. You can always transfer the ownership of the app to an org later.
1. For the App Name, use `conbench-<your org>`.
1. For the Homepage URL, use the link to your Conbench server.
1. Ignore the Callback URL and Setup URL.
1. Uncheck the "Active" box under Webhook. Since this App will not be an active service,
    we don't need GitHub to push webhook events to the App.
1. For full use of this package, the App requires the following permissions:
    - Repository > Checks > Read and Write
    - Repository > Commit statuses > Read and Write
    - Repository > Pull requests > Read and Write
1. After creating the App, save the App ID for later.
1. For the App's photo, use [this
   one](https://avatars.githubusercontent.com/u/61704591).
1. In the App Settings, scroll down to Private Keys and generate a private key. This
    will download a file to your computer. Treat the contents of this file like a
    password.
1. IMPORTANT: After creation, go to
    `https://github.com/apps/<YOUR_APP_NAME>/installations/new` to install the new App
    on the repos you'd like it to be able to post to. You must be a member of the
    organization to install the App on. If you are not an admin, an email request will
    be sent to org admins, which must be approved.

### Running `benchalerts` as the GitHub App you created

All that's necessary to use `benchalerts` workflows that post to GitHub as your App is
to set the following environment variables:

- `GITHUB_APP_ID` - the App ID from above
- `GITHUB_APP_PRIVATE_KEY` - the _contents_ of the private key file from above. This is
    a multiline file, so ensure you quote the contents correctly if necessary.

Since `benchalerts` is usually used in CI, it's recommended to set these two environment
variables in your CI pipeline as secret env vars. Most CI systems have a mechanism for
doing this. For security reasons, do not check these values into version control.

## License information

Copyright (c) 2022, Voltron Data.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this
file except in compliance with the License. You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under
the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied. See the License for the specific language governing
permissions and limitations under the License.
