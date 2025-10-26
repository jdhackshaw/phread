"""A prototype program for teaching adults to read"""
__version__ = '0.1'

from tkinter import *
from threading import Thread
import string

import sounddevice as sd
import soundfile as sf
import numpy as np

import whisper
import Levenshtein as lev
from openai import OpenAI

# Dependencies
# ------------
# tkinter
# numpy
# python-sounddevice
# python-soundfile
# openai

# Whisper speech-to-text API initialisation
client = OpenAI(
  api_key="cPa7JWZoKIqK7HkOC1hCoFiu71ldEJ9Q",
  base_url="https://api.lemonfox.ai/v1",
)

# Course content
PAGES = [
    {"type": "start", "text": "Welcome to Phread"},
    {"type": "lesson", "text": "a", "file": "aah.wav"},
    {"type": "lesson", "text": "k", "file": "k.wav"},
    {"type": "lesson", "text": "t", "file": "tt.wav"},
    {"type": "lesson", "text": "act", "file": "act.wav"},
    {"type": "exercise", "text": "act"},
    {"type": "lesson", "text": "cat", "file": "cat.wav"},
    {"type": "exercise", "text": "cat"},
    {"type": "lesson", "text": "m", "file": "mm.wav"},
    {"type": "exercise", "text": "mat"},
    {"type": "lesson", "text": "mat", "file": "mat.wav"},
    {"type": "lesson", "text": "th", "file": "th.wav"},
    {"type": "lesson", "text": "e", "file": "eh.wav"},
    {"type": "lesson", "text": "the cat", "file": "the-cat.wav"},
    {"type": "exercise", "text": "the cat"},
    {"type": "lesson", "text": "s", "file": "ss.wav"},
    {"type": "exercise", "text": "sat"},
    {"type": "lesson", "text": "sat", "file": "sat.wav"},
    {"type": "lesson", "text": "o", "file": "oo.wav"},
    {"type": "lesson", "text": "n", "file": "nn.wav"},
    {"type": "lesson", "text": "sat on", "file": "sat-on.wav"},
    {"type": "exercise", "text": "sat on"},
    {"type": "exercise", "text": "the cat sat on the mat"},
    {"type": "lesson", "text": "the cat sat on the mat", "file": ""},
    {"type": "end", "text": "Lesson complete. Good job!"}
]

rules = [
    ("ng", "ნგ"),
    ("th", "თ"),
    ("sh", "შ"),
    ("ch", "ჩ"),
    ("a", "ა"),
    ("e", "ე"),
    ("i", "ი"),
    ("o", "ო"),
    ("u", "უ"),
    ("k", "კ"),
    ("c", "კ"),
    ("t", "ტ"),
    ("s", "ს"),
    ("m", "მ"),
    ("n", "ნ"),
    ("l", "ლ"),
    ("r", "რ"),
    ("v", "ვ"),
    ("d", "დ"),
    ("h", "ჰ"),
    ("p", "პ")
]

# Transliterate latin script English to Georgian script English
def transliterate(text):
    text = text.lower()
    for (src, dst) in rules:
        text = text.replace(src, dst)
    return text

# Create an appropriate file name appended with wav
def wav_kebab(text):
    text = list(text)
    for i in range(len(text)):
        if text[i] == ' ':
            text[i] = '-'

    text = "".join(text)
    text = text + ".wav"
    return text


class Page(Frame):
    """Base page template that provides standard nav buttons and an update hook.

    Subclasses should call super().__init__ and implement update_content(self, data).
    """
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # This label displays the lesson content in large bold letters
        self.main_label = Label(self, font=("Arial", 18, "bold"))
        self.main_label.pack(pady=(16, 8))

        self.content_frame = Frame(self)
        self.content_frame.pack(fill="both", expand=True, padx=12, pady=6)

        # Navigation bar
        nav = Frame(self)
        nav.pack(pady=12)
        self.back_btn = Button(nav, text="◀ Back", width=10, command=self.go_back)
        self.back_btn.pack(side=LEFT, padx=8)
        self.next_btn = Button(nav, text="Next ▶", width=10, command=self.go_next)
        self.next_btn.pack(side=LEFT, padx=8)

    # Update the content when the user changes page
    def update_content(self, data: dict):
        self.in_english = data.get("text", "")
        self.in_georgian = transliterate(self.in_english)
        self.main_label.config(text=self.in_georgian)

    def go_back(self):
        idx = self.controller.state["page_index"]
        self.controller.show_page(idx - 1)

    def go_next(self):
        idx = self.controller.state["page_index"]
        self.controller.show_page(idx + 1)

# Superclass for the start and end pages
class StubPage(Page):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

    # Show the text in untransliterated English
    def update_content(self, data: dict):
        self.main_label.config(text=data.get("text", ""))

# Class for the initial page. It has no back button
class StartPage(StubPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.back_btn.destroy()


# Class for the final page. It has no next button
class EndPage(StubPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.next_btn.destroy()


# Lessons have Georgian text and audio the user can listen to
class LessonPage(Page):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        # Example: add a "Listen" button for lesson pages
        self.listen_image = PhotoImage(file='img/volume-up-fill.png')
        self.listen_button = Button(self.content_frame,
                                    image=self.listen_image,
                                    command=self.on_listen)
        # place it under the text label by default
        self.listen_button.pack(pady=(8, 0))
        self.has_listened = False

    def update_content(self, data : dict):
        super().update_content(data)
        base_name = data["file"]
        if base_name == "":
            base_name = wav_kebab(data["text"])

        self.audio_data, self.samplerate = sf.read("audio/" + base_name, dtype="float32")
        self.has_listened = False

    def on_listen(self):
        self.has_listened = True
        sd.play(self.audio_data, self.samplerate)


# Exercises require the user to read the displayed text
class ExercisePage(Page):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        self.microphone_image = PhotoImage(file='img/mic-fill.png')
        self.mute_image = PhotoImage(file='img/mic-off-fill.png')
        self.record_button = Button(self.content_frame,
                                    image=self.microphone_image,
                                    command=self.toggle_recording)
        self.record_button.pack(pady=(8, 0))

        self.correct_image = PhotoImage(file="img/check-line.png").subsample(2,2)
        self.speak_image = PhotoImage(file="img/speak-fill.png").subsample(2,2)
        self.wrong_image = PhotoImage(file="img/close-line.png").subsample(2,2)
        self.loading_image = PhotoImage(file="img/loader-4-line.png").subsample(2,2)

        self.feedback_label = Label(self.content_frame, image=self.speak_image, fg="green")
        self.feedback_label.pack(pady=(8, 0))

        self.audio_buffer = []
        self.threads = []
        self.is_recording = False
        self.stream = "" # placeholder value, stream is not a string
        self.transcript = "" # placeholder value, transcript is not a string
        self.rate = 16000
        self.transcript_waiting = False

    def update_content(self, data: dict):
        super().update_content(data)
        self.feedback_label.config(image=self.speak_image)
        self.english_text = data["text"]

    def toggle_recording(self):
        if self.is_recording == False:
            self.is_recording = True
            self.record_button.config(image=self.mute_image)
            self.start_recording()
        else:
            self.is_recording = False
            self.record_button.config(image=self.microphone_image)
            #print("Stopping the recording")
            self.stop_recording()
            #print("Recording stopped")
            #print("Starting API thread")
            self.transcript_waiting = True
            self.feedback_label.config(image=self.loading_image)
            t = Thread(target=self.get_transcript)
            t.start()
            self.threads.append(t)
                
    
    def get_transcript(self):
        #print("Sending file to transcription service...")
        audio_file = open("recording.wav", "rb")
        self.transcript = client.audio.transcriptions.create(
          model="whisper-1",
          file=audio_file,
          language="en"
        )
        #print("Audio transcript finished")
        #print(self.transcript)
        clean_transcript = self.transcript.text.lower().translate(str.maketrans('', '', string.punctuation))
        #print(f"Comparing '{clean_transcript}' to '{self.english_text}'")
        distance = lev.distance(clean_transcript, self.english_text)
        #print(f"Found a Levenshtein distance of {distance}")
        if (distance / len(self.english_text)) > 0.34:
            self.feedback_label.config(image=self.wrong_image)
        else:
            self.feedback_label.config(image=self.correct_image)

        self.feedback_label.config(text=self.transcript.text)
        self.transcript_waiting = False

    def callback(self, indata, frames, time, status):
        self.audio_buffer.append(indata.copy())
        
    def start_recording(self):
        self.audio_buffer = []
        self.is_recording = True

        self.stream = sd.InputStream(samplerate=self.rate,
                                     channels=1,
                                     callback=self.callback)
        self.stream.start()

    def stop_recording(self):
        self.stream.stop()
        self.stream.close()

        if self.audio_buffer:
            #print("Writing recording to file")
            audio_data = np.concatenate(self.audio_buffer, axis=0)
            sf.write("recording.wav", audio_data, self.rate)
        else:
            print("No audio recorded")


class App(Tk):
    def __init__(self):
        super().__init__()
        self.title("Generalized Lesson App (Page base)")
        self.geometry("560x320")
        self.resizable(False, False)

        # Shared state
        self.state = {"page_index": 0}

        # Container that holds both templates in the same grid cell
        container = Frame(self)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Create exactly one instance of each template, grid them into same cell
        self.start_page = StartPage(parent=container, controller = self)
        self.lesson_page = LessonPage(parent=container, controller=self)
        self.exercise_page = ExercisePage(parent=container, controller=self)
        self.end_page = EndPage(parent=container, controller = self)

        # Put both in same cell so we can tkraise them as needed
        self.start_page.grid(row=0, column=0, sticky="nsew")
        self.lesson_page.grid(row=0, column=0, sticky="nsew")
        self.exercise_page.grid(row=0, column=0, sticky="nsew")
        self.end_page.grid(row=0, column=0, sticky="nsew")

        # Start by showing the first page
        self.show_page(0)

    def show_page(self, index: int):
        """Show PAGES[index]. Safe to call with out-of-range index (wraps/clamps)."""
        if index < 0:
            index = 0
        if index >= len(PAGES):
            index = len(PAGES) - 1

        self.state["page_index"] = index
        page_data = PAGES[index]

        # choose template, update it with content, then raise it
        if page_data["type"] == "start":
            self.start_page.update_content(page_data)
            self.start_page.tkraise()
        elif page_data["type"] == "lesson":
            self.lesson_page.update_content(page_data)
            self.lesson_page.tkraise()
        elif page_data["type"] == "exercise":
            self.exercise_page.update_content(page_data)
            self.exercise_page.tkraise()
        elif page_data["type"] == "end":
            self.end_page.update_content(page_data)
            self.end_page.tkraise()
        else:
            print(f"Unrecognised page type: {page_data["type"]}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
