import os

source = "AUDIO/Safe/safe_source_16.wav"
target = "AUDIO/spanish.wav"
out = "AUDIO/Safe/spanish.wav"
os.system("python vocal-remover/inference.py --input "+source+" --gpu 0")
os.system("bash ppg-vc/convert.sh TMP/source_singer.wav "+target+" TMP/convert_speaker.wav")
os.system("python mix.py TMP/convert_speaker.wav TMP/source_music.wav "+ out)