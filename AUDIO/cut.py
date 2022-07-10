import torchaudio

w, sr = torchaudio.load("safe_16.wav")

w = w[:,16000*17:16000*23]

torchaudio.save("safe_source_16.wav", w, 16000)