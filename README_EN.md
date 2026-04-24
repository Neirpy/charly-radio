# 📻 Charly Lab Radio

*Lire ceci en [Français](README.md).*

The Charly Lab Radio that syncs with real-time. 
This project is a complete intelligent webradio system. It includes a time-synchronized web player, a visual programming interface, and a hybrid AI engine capable of generating a 24-hour music schedule without repetitions, tailored to the daily mood.

## 🛠️ Project Architecture

The project is divided into three main parts:

1. **Web Player (Frontend)**: A website built with Vite/JS that reads the `playlist_radio.json` file and perfectly synchronizes playback according to the listener's real local time.
2. **Programming Interface (Desktop)**: The `planner_radio.py` script provides a graphical user interface (PyQt6) to view the schedule grid, drag and drop tracks, and generate time slots using a local AI (Ollama).
3. **Auto-Pilot Engine (Cloud)**: The `gemini_planner.py` script generates a full 24-hour schedule instantly using the Google Gemini API. It is designed to be triggered automatically every night by GitHub Actions.

---

## 🚀 1. Web Player Installation (Frontend)

This is the part visible to the listeners.

**Prerequisites**: Have [Node.js](https://nodejs.org/) installed.

1. Install dependencies:
   ```bash
   npm install
   ```
2. Start the development server:
   ```bash
   npm run dev
   ```
3. Open your browser at `http://localhost:5173`. The music will start at the exact correct moment based on the generated playlist!

---

## 🖥️ 2. Local Programming Interface (GUI)

This is your studio tool. It allows you to view and manually modify the schedule grid.

**Prerequisites**: Have Python 3.10+ and [Ollama](https://ollama.com/) (if you use local generation).

1. Create a virtual environment and activate it:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Install the PyQt6 libraries:
   ```bash
   pip install PyQt6
   ```
3. Launch the application:
   ```bash
   python planner_radio.py
   ```
*Note: If you use the "Generate with AI" button in this interface, make sure the Ollama application is running in the background with the requested model downloaded.*

---

## 🧠 3. The AI Auto-Pilot (Gemini Planner)

This script (`gemini_planner.py`) generates the `playlist_radio.json` file for 24 hours using the Gemma 4 model hosted on the Google Gemini API.

### Installation & Security

1. Ensure you have the required dependencies:
   ```bash
   pip install python-dotenv google-genai
   ```
2. Create an `.env` file at the root of the project (this file will never be shared on GitHub thanks to `.gitignore`):
   ```env
   GEMINI_API_KEY=Your_Secret_Key_Here
   ```
3. Test the script:
   ```bash
   python gemini_planner.py
   ```
   *The script will read the guidelines from `ai_config.json`, generate 12 "anchors" via Gemini, and intelligently fill all the gaps without repeating tracks. It will then update `playlist_radio.json` and `historique_diffusion.json`.*

---

## 🤖 4. Automation with GitHub Actions

The project is configured to **update itself automatically every night at midnight**.

1. Go to your GitHub repository.
2. Go to **Settings > Secrets and variables > Actions**.
3. Click on **New repository secret**.
4. Name the secret `GEMINI_API_KEY` and paste your real secret key into the value field.
5. That's it! Every night, GitHub will run `gemini_planner.py`, create the day's schedule, and push the changes online. The web player will automatically be up to date for listeners.

### Configuring the Radio's Mood
You can modify the instructions given to the AI by simply editing the `ai_config.json` file.
