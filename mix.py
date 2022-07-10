import math
import torch
import torch.nn.functional as F
import librosa
import soundfile as sf
import argparse
# target_file = "convert_speaker_aligned.wav"
# noise_file = "source_music2.wav"
def mix(target_file, noise_file, out_file):
     SNR_dB = 0
     FLT_EPSILON = 1.19209290e-7

     sr = 16000
     start_times = 0.0

     target_signal, _ = librosa.load(target_file, sr=sr)
     noise_signal, _ = librosa.load(noise_file, sr=sr)

     target_signal = torch.from_numpy(target_signal)
     noise_signal = torch.from_numpy(noise_signal)

     target_power = target_signal.norm(p=2)
     noise_power = noise_signal.norm(p=2) + FLT_EPSILON

     print(f"NOISE before scaling: {noise_signal}")
     scale_factor = math.sqrt(10**(-SNR_dB / 10) * target_power / noise_power)
     noise_signal *= scale_factor

     print(f"TARGET: {target_signal}")
     print(f"NOISE after scaling: {noise_signal}")


     # Not to use offset (start_times)
     mixed_signal = torch.zeros_like(target_signal)
     if len(noise_signal) > len(target_signal):
          # Trimmed noise_signal to the length of target_signal
          noise_signal = noise_signal[:len(target_signal)]
     else:
          # Zero padding
          to_pad = len(target_signal) - len(noise_signal)
          noise_signal = F.pad(input=noise_signal, pad=(0, to_pad), mode='constant', value=0)

     assert target_signal.size() == mixed_signal.size(), f"CAN'T ADD TWO UNEQUAL VECTORS: {target_signal.size} - {mixed_signal.size}"
     alpha = 1.0
     mixed_signal = target_signal + alpha * noise_signal
     mixed_signal = mixed_signal.numpy()

     print(f"MIXED: {mixed_signal}")

     sf.write(out_file, mixed_signal, samplerate=sr)

import sys


if __name__ == '__main__':
     print(sys.argv)
     arg = sys.argv
     mix(arg[1], arg[2], arg[3])