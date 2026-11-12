# Publish the portfolio on GitHub

This guide uses the ready-to-run static website in `docs/`. There is no need to purchase dashboard hosting to publish the included browser demonstrations.

## 1. Prepare and run the files

1. Extract the downloaded ZIP into a folder on your computer.
2. Open a terminal in the folder that contains `README.md` and `build_all.py`.
3. Run `python build_all.py`.
4. Run `python -m http.server 8000 --directory docs` and open `http://localhost:8000`.
5. Check both dashboards and complete the [review checklist](PORTFOLIO_REVIEW_CHECKLIST.md).

On Windows, `py` can be used in place of `python` when that is how Python is installed. Rebuilding replaces generated data and website outputs, so keep personal edits in the source files described by `build_all.py`.

## 2. Create and upload a repository

Create a new GitHub repository named `supply-chain-analytics-portfolio`. Upload the **contents of the extracted project folder**, so `README.md`, `build_all.py`, `projects/`, and `docs/` appear at the repository root. Uploading only the ZIP does not make the dashboards browsable.

For the browser workflow, open the repository, choose **Add file → Upload files**, drag the extracted files or folders into the page, and commit the upload. GitHub documents a limit of 100 files per browser upload and 25 MiB per file. If necessary, use more than one upload or GitHub Desktop. See [GitHub's official upload guide](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository).

Include `.github/` if you want the validation workflow. Keep generated SQLite databases out of commits; the build recreates them and `.gitignore` excludes them. CSV files, JSON outputs, SQL, documentation, and the static website are intended to be included.

## 3. Turn on GitHub Pages

1. Open the repository's **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Choose the branch containing the uploaded files, normally `main`.
4. Choose **/docs** as the folder and save.
5. Wait for GitHub's deployment to finish, then use the site URL GitHub displays.

The included `.nojekyll` file lets the generated static files be served as written. The validation workflow checks the project but does not deploy changes or write rebuilt outputs back to the repository. After editing source data or code, run the build locally and commit the resulting `docs/` changes before expecting the published site to update.

GitHub Pages supports a branch's root or `/docs` directory as a source. Public repositories are supported on GitHub Free; see [GitHub's publishing-source documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

## 4. Present the work on your profile

Add the actual published portfolio URL to the repository's **About** section and your profile's website field. Add topics such as `supply-chain`, `sql`, `inventory`, `logistics`, and `data-analytics`.

On your GitHub profile, choose **Customize your pins** and pin the portfolio repository. If you later separate the case studies into independent repositories, pin those too. GitHub supports up to six pinned repositories and gists; see [pinning items](https://docs.github.com/en/account-and-profile/how-tos/profile-customization/pinning-items-to-your-profile).

An optional profile README uses a public repository whose name exactly matches your GitHub username, with `README.md` in its root. A suitable short introduction is:

> Supply Chain Analyst focused on inventory, fulfillment, procurement, and logistics analytics. This portfolio contains reproducible case studies using synthetic data, documented SQL measures, and interactive dashboards.

Follow it with the actual repository and dashboard links after publishing. See [managing a profile README](https://docs.github.com/en/account-and-profile/how-tos/profile-customization/managing-your-profile-readme).

## 5. Add a native BI dashboard later

The project folders include Power BI model instructions and DAX measures. Import the documented CSVs, build the model, and reconcile key totals against SQL before adding a `.pbix` file or screenshots.

[Power BI Publish to web](https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-publish-to-web) has license, permission, and administrator-setting requirements. It makes the report and underlying model data accessible publicly. The synthetic project data is designed for this use; do not substitute confidential employer records.

[Tableau Public](https://help.tableau.com/current/pro/desktop/en-us/public_faq.htm) is a free option for creating and publicly sharing a Tableau version. Add its actual live link only after the workbook has been built and published.

Documentation checked November 12, 2026. Platform interfaces and account settings can change; the linked official guides are the reference for current behavior.
