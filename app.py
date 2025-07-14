import os
import zipfile
import requests
import shutil
from flask import Flask, request, render_template, abort, send_from_directory

app = Flask(__name__)

# Configuration
CACHE_DIR = "cache"
STATIC_PLOTS_DIR = "static/plots"

# Ensure directories exist
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(STATIC_PLOTS_DIR, exist_ok=True)


def download_and_extract_artifact(repo, artid):
    """Download and extract artifact, return the extraction path"""
    cache_path = os.path.join(CACHE_DIR, f"{repo.replace('/', '_')}_{artid}")
    plots_path = os.path.join(
        STATIC_PLOTS_DIR, f"{repo.replace('/', '_')}_{artid}"
    )

    # Check if already cached
    if os.path.exists(plots_path):
        return plots_path

    # Get artifact URL
    artifact_url = f"https://api.github.com/repos/{repo}/actions/artifacts/{artid}/zip"
    if not artifact_url:
        return None

    # Download artifact
    zip_path = f"{cache_path}.zip"
    try:
        GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        response = requests.get(artifact_url, headers=headers)
        response.raise_for_status()

        with open(zip_path, "wb") as f:
            f.write(response.content)

        # Extract artifact
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(cache_path)

        # Move to plots directory
        shutil.move(cache_path, plots_path)

        # Clean up zip file
        os.remove(zip_path)

        return plots_path
    except (requests.exceptions.RequestException, zipfile.BadZipFile):
        # Clean up on error
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists(cache_path):
            shutil.rmtree(cache_path)
        return None


def get_plot_categories(plots_path):
    """Get categories and their PNG files"""
    categories = {}

    if not os.path.exists(plots_path):
        return categories

    for item in sorted(os.listdir(plots_path)):
        item_path = os.path.join(plots_path, item)
        if os.path.isdir(item_path):
            png_files = [f for f in os.listdir(item_path) if f.lower().endswith(".png")]
            if png_files:
                categories[item] = sorted(png_files)

    return categories


@app.route("/")
def index():
    """Main page with form"""
    return render_template("index.html")


@app.route("/view")
def view_plots():
    """View plots for a repository and run"""
    repo = request.args.get("repo")
    artid = request.args.get("id")

    if not repo or not artid:
        abort(400, "Both 'repo' and 'id' parameters are required")

    try:
        artid = int(artid)
    except ValueError:
        abort(400, "Artifact ID must be an integer")

    # Download and extract artifact
    plots_path = download_and_extract_artifact(repo, artid)
    if not plots_path:
        abort(404, "Artifact not found or could not be downloaded")

    # Get categories and plots
    categories = get_plot_categories(plots_path)
    if not categories:
        abort(404, "No plot categories found in artifact")

    # Hardcoded checks for now
    checks = [
        {"name": "Check 1", "status": True},
        {"name": "Check 2", "status": True},
    ]

    return render_template(
        "plots.html",
        repo=repo,
        run=artid,
        categories=categories,
        plots_base_path=f"{repo.replace('/', '_')}_{artid}",
        checks=checks,
    )


@app.route("/static/plots/<path:filename>")
def serve_plot(filename):
    """Serve plot images"""
    return send_from_directory(STATIC_PLOTS_DIR, filename)


@app.errorhandler(400)
def bad_request(error):
    return render_template(
        "error.html", error_code=400, error_message=str(error.description)
    ), 400


@app.errorhandler(404)
def not_found(error):
    return render_template(
        "error.html", error_code=404, error_message=str(error.description)
    ), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template(
        "error.html", error_code=500, error_message="Internal server error"
    ), 500


@app.route("/checks")
def get_checks():
    """Return available checks and their status for a given repo/run"""
    repo = request.args.get("repo")
    run = request.args.get("run")

    if not repo or not run:
        abort(400, "Both 'repo' and 'run' parameters are required")

    try:
        int(run)
    except ValueError:
        abort(400, "Run number must be an integer")

    # In the future, checks could depend on repo/run
    checks = [
        {"name": "Check 1", "status": True},
        {"name": "Check 2", "status": True},
    ]
    return {"checks": checks}


if __name__ == "__main__":
    app.run(debug=True)
