# Forensic-Search (Hackathon Edition)

This guide documents the exact sequence of steps to run the platform locally, process your dataset (250 videos), and deploy a static, blazingly fast demo environment to Google Cloud Platform (GCP).

**Note:** As this is preconfigured for GCP Cloud Run read-only mode, you will run the AI/ML processes locally *once*, and package the extracted evidence into a Docker image for judges to interact with purely in RAM.

---

## 1. Local Pre-Processing (Your Computer)

You must run the ML pipeline on your local machine to generate the `.vtt` and `.json` artifacts before deploying.

### Setup Environment
1. Open terminal and create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install the necessary dependencies (requires `ffmpeg` installed on your OS):
   ```bash
   pip install -r requirements.txt
   ```

### Process the Video Dataset (The 250 Videos)
1. Place all your `mp4`/`mkv`/`wav` files into the `media/` folder.
2. Run the batch folder processor using a faster Whisper model (`tiny` or `small` is highly recommended for 250 files):
   ```bash
   python scripts/process_folder.py --model small
   ```
3. Wait for the processing to finish. (This may take several hours depending on your hardware. Using a GPU will drastically reduce this time).
4. *Verification:* Check the `data/captions/` directory. You should see three files (`.srt`, `.vtt`, `.json`) for every video in the `media/` folder.
5. Check `data/index.json`. It has been generated dynamically and minified for fast loading.

---

## 2. Local Testing (Optional)

Test the UI locally to ensure the index and videos map correctly.

```bash
# Temporarily enable auto processing just in case you want to test the watcher
export DISABLE_AUTO_PROCESS=""
python app.py
```
* Open `http://127.0.0.1:8080/` in a browser.
* Try searching to ensure the index loads instantly into memory.

---

## 3. Deployment (Google Cloud Run)

You will push the code *including* the processed `media` and `data` folders to GitHub. GCP Cloud Run will pull your repository, build the Dockerfile, and serve your app.

### Prepare Git and Push

```bash
# 1. Add all files (including media and data folders, if they aren't gitignored)
git add .
git commit -m "chore: push hackathon dataset and minified index"
git push origin main
```
*Wait for your files to finish uploading to GitHub.*

### Configure GCP Cloud Run

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Navigate to **Cloud Run** -> **Create Service**.
3. Under "Deploy one revision from source code," click **Continuously deploy new revisions from a source repository**.
4. Connect to GitHub and select the **Forensic-Search** repository.
5. Under **Authentication**, select **Allow unauthenticated invocations** (this allows judges to access the URL).
6. Under **Container, Connections, Security**, specify:
    *   **Container port**: `8080`
    *   **Capacity**: `2 to 4 CPUs`, `2GB to 4GB RAM` (High CPU is required if multiple judges search concurrently; RAM holds the index).
    *   **Timeout**: `3600 seconds` (Maximum)
7. Click **Create / Deploy**.

### 4. Demo Time!

Once Cloud Run finishes building (~5-10 minutes), it will present a Public URL (e.g. `https://forensic-search-xxx-uc.a.run.app`). 

Provide this URL to the judges.

* The app will boot, read the minified `index.json` into RAM (making queries instant), and serve the HTML5 video players streaming files out of the Docker container.
* Because `DISABLE_AUTO_PROCESS=1` is injected inside the provided `Dockerfile`, the Python server won't waste CPU scanning the readonly `/media` directory.