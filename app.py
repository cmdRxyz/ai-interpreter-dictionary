"""
This is a Flask web application that serves as an AI-powered interpreter and dictionary tool. It allows users to input text or use voice input to translate sentences into a target language, while also providing word-level definitions and examples. The application supports multiple languages and includes a dark mode feature for better user experience. 
Academic and real-world dictionary definitions are fetched from a public API, with a fallback to an offline cache for common words. The application uses the Deep Translator library for translations if available, and it leverages the Web Speech API for voice input functionality.
Working with Flask, the application renders a dynamic HTML template that displays the translated sentence and a breakdown of individual words with their meanings and examples. The user interface is designed to be responsive and user-friendly, with clear visual cues for interactions such as voice input and theme toggling.
Python libraries used include Flask for web serving, urllib for API requests, and json for handling JSON data. The application is structured to be extensible, allowing for the addition of more languages and features in the future.
Backend logic is encapsulated in functions that handle translation, word definition fetching, and processing of user input, ensuring a clean separation of concerns and maintainability of the codebase.
Frontend interactivity is managed through JavaScript, enabling real-time voice recognition and dynamic updates to the user interface based on user actions. The application is designed to be deployed in a web environment, accessible via modern web browsers that support the necessary APIs for full functionality.

University students, language learners, and professionals can benefit from this tool for enhancing their language skills, understanding vocabulary in context, and facilitating communication across different languages. The application serves as a practical example of integrating AI capabilities into web applications for educational and professional use cases.

University of Texas at Austin - Python Programming Course Project
Apolo Reynoso Ruiz - EID: ar89369
Jorge Emiliano Gutiérrez Ramírez - EID: 

"""

# --- IMPORTS ---
import functools
import re
import urllib.parse
import urllib.request
import json
from flask import Flask, render_template_string, request, jsonify

# Optional dynamic translation library.
# If deep_translator is not installed, the application will still function but without automatic translation capabilities.
try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False

app = Flask(__name__)

# --- SUPPORTED LANGUAGES (EXTENSIBLE TO ALL MAJOR CODES) ---
SUPPORTED_LANGUAGES = {
    "es": "Spanish (Español)",
    "en": "English",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "it": "Italian (Italiano)",
    "pt": "Portuguese (Português)",
    "zh-CN": "Chinese Simplified (中文)",
    "ja": "Japanese (日本語)",
    "ko": "Korean (한국어)",
    "ru": "Russian (Русский)",
    "ar": "Arabic (العربية)",
    "hi": "Hindi (हिन्दी)"
}

# Web Speech API language mapping for SpeechRecognition
# This dictionary maps the language codes used in the application to the corresponding language codes recognized by the Web Speech API for voice input functionality.
SPEECH_LANG_MAP = {
    "auto": "en-US",
    "es": "es-ES",
    "en": "en-US",
    "fr": "fr-FR",
    "de": "de-DE",
    "it": "it-IT",
    "pt": "pt-BR",
    "zh-CN": "zh-CN",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "ru": "ru-RU",
    "ar": "ar-SA",
    "hi": "hi-IN"
}

# --- LOCAL CACHED VOCABULARY FALLBACK ---
# It works as a fallback for common words when the FreeDictionaryAPI is unreachable or offline.
OFFLINE_DICT = {
    "hello": {
        "meaning": "A greeting used when meeting someone or answering the phone.",
        "example": "Hello, how are you doing today?",
        "pos": "interjection"
    },
    "interpreter": {
        "meaning": "An entity or software that translates speech or code in real-time.",
        "example": "The AI interpreter assisted during the international meeting.",
        "pos": "noun"
    },
    "world": {
        "meaning": "The earth and all people, things, and phenomena upon it.",
        "example": "They traveled all across the world.",
        "pos": "noun"
    },
    "dictionary": {
        "meaning": "A reference resource providing definitions, pronunciations, and examples.",
        "example": "Check the dictionary whenever you encounter an unfamiliar word.",
        "pos": "noun"
    }
}

# --- DECORATORS ---
# Function decorators for input validation and logging, ensuring that the application handles user input and translation requests robustly.
def validate_text(func):
    """Decorator ensuring incoming text is trimmed and non-empty."""
    @functools.wraps(func)
    def wrapper(text, *args, **kwargs): # Accepts text as the first argument
        if not text or not str(text).strip():
            return []
        return func(str(text).strip(), *args, **kwargs)
    return wrapper
# Function decorator for logging execution of translation requests and timing metrics, providing insights into the performance of the translation engine.
def log_execution(func):
    """Decorator that logs translation requests and timing metrics."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs): # Accepts arbitrary arguments and keyword arguments
        print(f"[ENGINE] Invoking {func.__name__} with parameters: target={kwargs.get('target_lang')}")
        result = func(*args, **kwargs)
        print(f"[ENGINE] {func.__name__} completed successfully.")
        return result
    return wrapper


# --- DICTIONARY DEFINITION FETCHING (FREE DICTIONARY API WITH OFFLINE FALLBACK) ---
# Function to fetch word definitions and examples, with offline fallback for common words, ensuring that the application can provide meaningful information even without internet connectivity.
def fetch_word_definition(word: str) -> dict:
    """
    Attempts to fetch real-world dictionary definitions and usage examples.
    Falls back cleanly to offline cache if no internet connection is present.
    """
    clean = word.lower().strip()
    if clean in OFFLINE_DICT:
        return OFFLINE_DICT[clean]

    # Query public FreeDictionaryAPI (no auth token required)
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(clean)}"
        req = urllib.request.Request(url, headers={"User-Agent": "PythonInterpreterApp/1.0"})
        with urllib.request.urlopen(req, timeout=2.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, list) and len(data) > 0:
                    meanings = data[0].get("meanings", [])
                    if meanings:
                        first_meaning = meanings[0]
                        pos = first_meaning.get("partOfSpeech", "general")
                        definitions = first_meaning.get("definitions", [])
                        if definitions:
                            def_text = definitions[0].get("definition", "Definition not found.")
                            example_text = definitions[0].get("example", f"Example sentence using '{clean}'.")
                            return {"meaning": def_text, "example": example_text, "pos": pos}
    except Exception:
        pass

    # Generic contextual fallback if offline or not in English dictionary.
    return {
        "meaning": f"Contextual conversational term or translation for '{clean}'.",
        "example": f"Used in conversational speech: '... {word} ...'",
        "pos": "word"
    }


# --- TRANSLATION AND ANALYSIS ENGINE ---
# Function to process the conversation: translate, tokenize, and fetch definitions, with logging and validation.
@log_execution # Log execution of translation requests
@validate_text # Ensure incoming text is trimmed and non-empty
# Function to process the conversation: translate, tokenize, and fetch definitions, with logging and validation.
def process_conversation(text: str, source_lang: str = "auto", target_lang: str = "es") -> list[dict]:
    """
    Translates whole text, isolates words, and attaches definition & example dropdown cards.
    """
    # 1. Whole sentence translation
    full_translation = ""
    if HAS_TRANSLATOR:
        try:
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            full_translation = translator.translate(text)
        except Exception as e:
            full_translation = f"(Offline or translation error: {e})"
    else:
        full_translation = "(Install deep-translator for automatic multi-language translation)"

    # 2. Tokenize words while keeping clean tokens
    tokens = re.findall(r"\b[\w'-]+\b", text)
    processed_words = []

    for token in tokens:
        word_info = fetch_word_definition(token)
        
        # Word-level translation
        word_trans = ""
        if HAS_TRANSLATOR and target_lang:
            try:
                word_trans = GoogleTranslator(source=source_lang, target=target_lang).translate(token)
            except Exception:
                word_trans = token
        else:
            word_trans = token
# Save processed word data for rendering in the template, including translation, meaning, example, and part of speech.
        processed_words.append({
            "word": token,
            "translation": word_trans,
            "meaning": word_info.get("meaning"),
            "example": word_info.get("example"),
            "pos": word_info.get("pos")
        })
# Return the original text, full translation, and processed words for rendering in the template.
    return {
        "original_text": text,
        "full_translation": full_translation,
        "words": processed_words
    }


# --- TEMPLATE WITH DARK MODE & WEB SPEECH API SUPPORT ---
"""
HTML_TEMPLATE is a multi-line string that contains the HTML structure and embedded CSS and JavaScript for the web application. It includes a responsive design, dark mode toggle, voice input functionality using the Web Speech API, and dynamic rendering of translation results and word definitions. The template uses Jinja2 syntax for server-side rendering of variables and loops, allowing the Flask backend to inject data into the HTML before sending it to the client. The template is designed to provide a user-friendly interface for interacting with the AI interpreter and dictionary features, with clear visual cues and interactive elements for an enhanced user experience.
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Interpreter & Dictionary</title>
    <style>
        :root {
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --tag-bg: #eff6ff;
            --tag-color: #1e40af;
            --box-bg: #f1f5f9;
            --mic-bg: #ef4444;
        }

        [data-theme="dark"] {
            --bg: #090d16;
            --card-bg: #131b2e;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --border: #1e293b;
            --primary: #3b82f6;
            --primary-hover: #60a5fa;
            --tag-bg: #1e293b;
            --tag-color: #93c5fd;
            --box-bg: #0b1120;
            --mic-bg: #dc2626;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            transition: background-color 0.2s, color 0.2s, border-color 0.2s;
        }

        body {
            background-color: var(--bg);
            color: var(--text-main);
            padding: 24px 16px;
            display: flex;
            justify-content: center;
        }

        .container {
            width: 100%;
            max-width: 780px;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .theme-toggle-btn {
            background: var(--card-bg);
            color: var(--text-main);
            border: 1px solid var(--border);
            padding: 8px 14px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .header {
            text-align: center;
        }

        .header h1 {
            font-size: 1.7rem;
            margin-bottom: 6px;
        }

        .header p {
            color: var(--text-muted);
            font-size: 0.95rem;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }

        .language-selectors {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 14px;
        }

        .select-group label {
            display: block;
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 4px;
            font-weight: 500;
        }

        select {
            width: 100%;
            padding: 10px;
            background: var(--bg);
            color: var(--text-main);
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 0.95rem;
            outline: none;
        }

        .input-wrapper {
            position: relative;
        }

        textarea {
            width: 100%;
            height: 110px;
            padding: 12px;
            padding-right: 48px;
            background: var(--bg);
            color: var(--text-main);
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 1rem;
            resize: vertical;
            outline: none;
        }

        textarea:focus {
            border-color: var(--primary);
        }

        .mic-btn {
            position: absolute;
            right: 12px;
            bottom: 14px;
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-main);
            border-radius: 50%;
            width: 36px;
            height: 36px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
        }

        .mic-btn.recording {
            background: var(--mic-bg);
            color: white;
            border-color: transparent;
            animation: pulse 1.2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }

        .actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 14px;
        }

        .speech-status {
            font-size: 0.85rem;
            color: var(--text-muted);
        }

        .submit-btn {
            background-color: var(--primary);
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: 10px 22px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
        }

        .submit-btn:hover {
            background-color: var(--primary-hover);
        }

        .translation-banner {
            background: var(--box-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 16px;
        }

        .translation-banner h3 {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 4px;
        }

        .translation-banner p {
            font-size: 1.15rem;
            font-weight: 500;
            color: var(--text-main);
        }

        .word-grid {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        details.word-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
        }

        details.word-card[open] {
            border-color: var(--primary);
        }

        summary.word-header {
            padding: 12px 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-weight: 600;
            list-style: none;
        }

        summary.word-header::-webkit-details-marker {
            display: none;
        }

        .word-info {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }

        .badge {
            background: var(--tag-bg);
            color: var(--tag-color);
            font-size: 0.75rem;
            font-weight: 500;
            padding: 2px 8px;
            border-radius: 6px;
        }

        .chevron {
            font-size: 0.8rem;
            color: var(--text-muted);
        }

        details[open] .chevron {
            transform: rotate(180deg);
        }

        .word-body {
            padding: 12px 16px;
            border-top: 1px solid var(--border);
            background: var(--box-bg);
            display: flex;
            flex-direction: column;
            gap: 6px;
            font-size: 0.92rem;
        }

        .example-quote {
            border-left: 3px solid var(--primary);
            padding: 6px 10px;
            font-style: italic;
            color: var(--text-muted);
            margin-top: 4px;
        }

        @media (max-width: 600px) {
            .language-selectors {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <span>🌐 <strong>Universal Interpreter</strong></span>
            <button class="theme-toggle-btn" id="themeToggle">🌓 Toggle Theme</button>
        </div>

        <section class="card">
            <form method="POST" action="/" id="interpreterForm">
                <div class="language-selectors">
                    <div class="select-group">
                        <label for="srcLang">Input Language (or Speech)</label>
                        <select name="src_lang" id="srcLang">
                            <option value="auto" {% if src_lang == 'auto' %}selected{% endif %}>Auto Detect</option>
                            {% for code, name in languages.items() %}
                            <option value="{{ code }}" {% if src_lang == code %}selected{% endif %}>{{ name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="select-group">
                        <label for="targetLang">Target Translation Language</label>
                        <select name="target_lang" id="targetLang">
                            {% for code, name in languages.items() %}
                            <option value="{{ code }}" {% if target_lang == code %}selected{% endif %}>{{ name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>

                <div class="input-wrapper">
                    <textarea name="user_text" id="userText" placeholder="Type or click the microphone to speak...">{{ original_text }}</textarea>
                    <button type="button" class="mic-btn" id="micBtn" title="Speak into microphone">🎤</button>
                </div>

                <div class="actions">
                    <span class="speech-status" id="speechStatus">Microphone ready.</span>
                    <button type="submit" class="submit-btn">Interpret & Breakdown</button>
                </div>
            </form>
        </section>

        {% if result %}
        <section class="results">
            <div class="translation-banner">
                <h3>Translated Sentence</h3>
                <p>{{ result.full_translation }}</p>
            </div>

            <h3 style="margin-bottom: 12px; font-size: 1.1rem;">Vocabulary Dictionary (Click word to expand)</h3>
            <div class="word-grid">
                {% for item in result.words %}
                <details class="word-card">
                    <summary class="word-header">
                        <div class="word-info">
                            <span>{{ item.word }}</span>
                            <span style="color: var(--text-muted); font-weight: 400;">→ {{ item.translation }}</span>
                            <span class="badge">{{ item.pos }}</span>
                        </div>
                        <span class="chevron">▼</span>
                    </summary>
                    <div class="word-body">
                        <div><strong>Meaning:</strong> {{ item.meaning }}</div>
                        <div><strong>Example Context:</strong>
                            <div class="example-quote">"{{ item.example }}"</div>
                        </div>
                    </div>
                </details>
                {% endfor %}
            </div>
        </section>
        {% endif %}
    </div>

    <script>
        // --- 1. DARK MODE TOGGLE & PERSISTENCE ---
        const themeBtn = document.getElementById('themeToggle');
        const currentTheme = localStorage.getItem('theme') || 
            (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

        document.documentElement.setAttribute('data-theme', currentTheme);

        themeBtn.addEventListener('click', () => {
            const active = document.documentElement.getAttribute('data-theme');
            const next = active === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
        });

        // --- 2. VOICE INPUT (WEB SPEECH API) ---
        const micBtn = document.getElementById('micBtn');
        const userText = document.getElementById('userText');
        const speechStatus = document.getElementById('speechStatus');
        const srcLangSelect = document.getElementById('srcLang');

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;

            const langCodes = {{ speech_langs|tojson }};

            micBtn.addEventListener('click', () => {
                if (micBtn.classList.contains('recording')) {
                    recognition.stop();
                    return;
                }

                const selectedLang = srcLangSelect.value;
                recognition.lang = langCodes[selectedLang] || 'en-US';
                recognition.start();
                micBtn.classList.add('recording');
                speechStatus.innerText = 'Listening... Speak now';
            });

            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                userText.value = userText.value ? userText.value + ' ' + transcript : transcript;
                speechStatus.innerText = 'Voice captured.';
            };

            recognition.onspeechend = () => {
                recognition.stop();
                micBtn.classList.remove('recording');
            };

            recognition.onerror = (event) => {
                speechStatus.innerText = 'Voice recognition error: ' + event.error;
                micBtn.classList.remove('recording');
            };

            recognition.onend = () => {
                micBtn.classList.remove('recording');
            };
        } else {
            micBtn.style.display = 'none';
            speechStatus.innerText = 'Speech recognition not supported in this browser (use Chrome/Safari/Edge).';
        }
    </script>
</body>
</html>
"""

# --- ROUTES ---
# Main route for the web application, handling both GET and POST requests.
@app.route("/", methods=["GET", "POST"])
def index():
    src_lang = "auto"
    target_lang = "es"
    original_text = ""
    result = None
# Handle POST request: process user input and generate translation and word breakdown.
    if request.method == "POST":
        original_text = request.form.get("user_text", "")
        src_lang = request.form.get("src_lang", "auto")
        target_lang = request.form.get("target_lang", "es")
        if original_text.strip():
            result = process_conversation(original_text, source_lang=src_lang, target_lang=target_lang)
# Render the HTML template with dynamic data for languages, speech language mapping, source and target languages, original text, and translation results.
    return render_template_string(
        HTML_TEMPLATE,
        languages=SUPPORTED_LANGUAGES,
        speech_langs=SPEECH_LANG_MAP,
        src_lang=src_lang,
        target_lang=target_lang,
        original_text=original_text,
        result=result
    )
# Run the Flask application on host
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

#------------- End of file -------------#