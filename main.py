from re import L
import librosa, sys
from PIL import Image
import streamlit as st
from annotated_text import annotated_text
from pydub import AudioSegment
import os

def header(url):
     st.markdown(f'<p style="background-color:#0066cc;color:#33ff33;font-size:24px;border-radius:2%;">{url}</p>', unsafe_allow_html=True)

if __name__ == "__main__":

     st.title("Music Voice Conversion")

     diagram = Image.open('diagram.png')
     st.image(diagram, caption='')

     st.markdown(f'<h1 style="color:#2eb82e;font-size:24px;">{"Sample Demo"}</h1>', unsafe_allow_html=True)
     st.write("Order: Source - Target - Clone")

     annotated_text(("Safe and Sound - Taylor Swift", "", "#8ef"))
     st.write("")

     annotated_text(("English Female", "", "#faa"))
     st.write("")
     st1, st2, st3 = st.columns(3)
     st1.audio("AUDIO/Safe/safe_source_16.wav")
     st2.audio("AUDIO/english_female.wav")
     st3.audio("AUDIO/Safe/english_female.wav")

     annotated_text(("English Male", "", "#faa"))
     st.write("")
     st1, st2, st3 = st.columns(3)
     st1.audio("AUDIO/Safe/safe_source_16.wav")
     st2.audio("AUDIO/english_male.wav")
     st3.audio("AUDIO/Safe/english_male.wav")

     annotated_text(("Chinese", "", "#faa"))
     st.write("")
     st1, st2, st3 = st.columns(3)
     st1.audio("AUDIO/Safe/safe_source_16.wav")
     st2.audio("AUDIO/chinese.wav")
     st3.audio("AUDIO/Safe/chinese.wav")

     annotated_text(("Spanish", "", "#faa"))
     st.write("")
     st1, st2, st3 = st.columns(3)
     st1.audio("AUDIO/Safe/safe_source_16.wav")
     st2.audio("AUDIO/spanish.wav")
     st3.audio("AUDIO/Safe/spanish.wav")

     #################################################

     annotated_text(("City of Stars - Duet ft. Ryan Gosling", "", "#8ef"))
     st.write("")

     annotated_text(("English Female", "", "#faa"))
     st.write("")
     st1, st2, st3 = st.columns(3)
     st1.audio("AUDIO/City/city_source_16.wav")
     st2.audio("AUDIO/english_female.wav")
     st3.audio("AUDIO/City/english_female.wav")

     annotated_text(("English Male", "", "#faa"))
     st.write("")
     st1, st2, st3 = st.columns(3)
     st1.audio("AUDIO/City/city_source_16.wav")
     st2.audio("AUDIO/english_male.wav")
     st3.audio("AUDIO/City/english_male.wav")

     annotated_text(("Chinese", "", "#faa"))
     st.write("")
     st1, st2, st3 = st.columns(3)
     st1.audio("AUDIO/City/city_source_16.wav")
     st2.audio("AUDIO/chinese.wav")
     st3.audio("AUDIO/City/chinese.wav")

     annotated_text(("Spanish", "", "#faa"))
     st.write("")
     st1, st2, st3 = st.columns(3)
     st1.audio("AUDIO/City/city_source_16.wav")
     st2.audio("AUDIO/spanish.wav")
     st3.audio("AUDIO/City/spanish.wav")

     st.markdown(f'<h1 style="color:#2eb82e;font-size:24px;">{"Realtime Demo"}</h1>', unsafe_allow_html=True)
     
     annotated_text(("Source Music", "", "#8ef"))
     source_music = st.file_uploader("Music audio with singer voice 16000Hz - 5s long")
     
     annotated_text(("Target Speaker", "", "#8ef"))
     target_speaker = st.file_uploader("Voice you want to sing the song")

     gen = st.button("Generate My Sing Voice")
     
     if gen :#and source_music and target_speaker:
          st.write("Currently, I am hosting in my local, I can't receive too much requeset, If available, you can ping for demo")

          # st.write("Generating: ...")
          # os.system("python vocal-remover/inference.py --input TMP/source.wav --gpu 0")
          # os.system("bash ppg-vc/convert.sh TMP/source_singer.wav TMP/target.wav TMP/convert_speaker.wav")
          # os.system("python mix.py TMP/convert_speaker.wav TMP/source_music.wav TMP/convert.wav")

          st.write("Source Music")
          st.audio("TMP/source.wav")
          st.write("Speaker Target")
          st.audio("TMP/target.wav")
          st.write("Converted Sing Speaker")
          st.audio("TMP/convert_speaker.wav")
          st.write("Converted Sing Speaker with Music")
          st.audio("TMP/convert.wav")

          # source_music_audio = AudioSegment.from_ogg(source_music)
          # target_speaker_audio = AudioSegment.from_ogg(target_speaker)

     elif gen and source_music:
          st.write("Please Upload Target Speaker")

     elif gen and target_speaker:
          st.write("Please Upload Source Music")

     elif gen:
          st.write("Please Upload source music and target speaker")