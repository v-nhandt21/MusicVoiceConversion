#!/usr/bin/env python3

# Copyright 2020 Songxiang Liu
# Apache 2.0

from typing import Dict
from typing import Tuple
from typing import List

import torch
import torch.nn as nn
import torch.nn.functional as F
from typeguard import check_argument_types

import math
import numpy as np

from .abs_model import AbsMelDecoder
from .basic_layers import Linear, Conv1d
from .rnn_decoder_mol import Decoder
from .cnn_postnet import Postnet
from .vc_utils import get_mask_from_lengths


class MelDecoderMOLv2(AbsMelDecoder):
    """Use an encoder to preprocess ppg."""
    def __init__(
        self,
        num_speakers: int,
        spk_embed_dim: int,
        bottle_neck_feature_dim: int,
        encoder_dim: int = 256,
        encoder_downsample_rates: List = [2, 2],
        attention_rnn_dim: int = 512,
        attention_dim: int = 512,
        decoder_rnn_dim: int = 512,
        num_decoder_rnn_layer: int = 1,
        concat_context_to_last: bool = True,
        prenet_dims: List = [256, 128],
        prenet_dropout: float = 0.5,
        num_mixtures: int = 5,
        frames_per_step: int = 2,
        postnet_num_layers: int = 5,
        postnet_hidden_dim: int = 512,
        mask_padding: bool = True,
        use_spk_dvec: bool = False,
    ):
        assert check_argument_types()
        super().__init__()
        
        self.mask_padding = mask_padding
        self.bottle_neck_feature_dim = bottle_neck_feature_dim
        self.num_mels = 80
        self.encoder_down_factor=np.cumprod(encoder_downsample_rates)[-1]
        self.frames_per_step = frames_per_step
        self.multi_speaker = True if num_speakers > 1 or self.use_spk_dvec else False
        self.use_spk_dvec = use_spk_dvec

        input_dim = bottle_neck_feature_dim
        
        # Downsampling convolution
        self.bnf_prenet = torch.nn.Sequential(
            torch.nn.Conv1d(input_dim, encoder_dim, kernel_size=1, bias=False),
            torch.nn.LeakyReLU(0.1),

            torch.nn.InstanceNorm1d(encoder_dim, affine=False),
            torch.nn.Conv1d(
                encoder_dim, encoder_dim, 
                kernel_size=2*encoder_downsample_rates[0], 
                stride=encoder_downsample_rates[0], 
                padding=encoder_downsample_rates[0]//2,
            ),
            torch.nn.LeakyReLU(0.1),
            
            torch.nn.InstanceNorm1d(encoder_dim, affine=False),
            torch.nn.Conv1d(
                encoder_dim, encoder_dim, 
                kernel_size=2*encoder_downsample_rates[1], 
                stride=encoder_downsample_rates[1], 
                padding=encoder_downsample_rates[1]//2,
            ),
            torch.nn.LeakyReLU(0.1),

            torch.nn.InstanceNorm1d(encoder_dim, affine=False),
        )
        decoder_enc_dim = encoder_dim
        self.pitch_convs = torch.nn.Sequential(
            torch.nn.Conv1d(2, encoder_dim, kernel_size=1, bias=False),
            torch.nn.LeakyReLU(0.1),

            torch.nn.InstanceNorm1d(encoder_dim, affine=False),
            torch.nn.Conv1d(
                encoder_dim, encoder_dim, 
                kernel_size=2*encoder_downsample_rates[0], 
                stride=encoder_downsample_rates[0], 
                padding=encoder_downsample_rates[0]//2,
            ),
            torch.nn.LeakyReLU(0.1),
            
            torch.nn.InstanceNorm1d(encoder_dim, affine=False),
            torch.nn.Conv1d(
                encoder_dim, encoder_dim, 
                kernel_size=2*encoder_downsample_rates[1], 
                stride=encoder_downsample_rates[1], 
                padding=encoder_downsample_rates[1]//2,
            ),
            torch.nn.LeakyReLU(0.1),

            torch.nn.InstanceNorm1d(encoder_dim, affine=False),
        )
        
        if self.multi_speaker:
            if not self.use_spk_dvec:
                self.speaker_embedding_table = nn.Embedding(num_speakers, spk_embed_dim)
            self.reduce_proj = torch.nn.Linear(encoder_dim + spk_embed_dim, encoder_dim)

        # Decoder
        self.decoder = Decoder(
            enc_dim=decoder_enc_dim,
            num_mels=self.num_mels,
            frames_per_step=frames_per_step,
            attention_rnn_dim=attention_rnn_dim,
            decoder_rnn_dim=decoder_rnn_dim,
            num_decoder_rnn_layer=num_decoder_rnn_layer,
            prenet_dims=prenet_dims,
            num_mixtures=num_mixtures,
            use_stop_tokens=True,
            concat_context_to_last=concat_context_to_last,
            encoder_down_factor=self.encoder_down_factor,
        )

        # Mel-Spec Postnet: some residual CNN layers
        self.postnet = Postnet()
    
    def parse_output(self, outputs, output_lengths=None):
        if self.mask_padding and output_lengths is not None:
            mask = ~get_mask_from_lengths(output_lengths, outputs[0].size(1))
            mask = mask.unsqueeze(2).expand(mask.size(0), mask.size(1), self.num_mels)
            outputs[0].data.masked_fill_(mask, 0.0)
            outputs[1].data.masked_fill_(mask, 0.0)
        return outputs

    def forward(
        self,
        bottle_neck_features: torch.Tensor,
        feature_lengths: torch.Tensor,
        speech: torch.Tensor,
        speech_lengths: torch.Tensor,
        logf0_uv: torch.Tensor = None,
        spembs: torch.Tensor = None,
        styleembs: torch.Tensor = None,
        output_att_ws: bool = False,
    ):
        decoder_inputs = self.bnf_prenet(
            bottle_neck_features.transpose(1, 2)
        ).transpose(1, 2)
        logf0_uv = self.pitch_convs(logf0_uv.transpose(1, 2)).transpose(1, 2)
        decoder_inputs = decoder_inputs + logf0_uv
            
        if self.multi_speaker:
            assert spembs is not None
            if not self.use_spk_dvec:
                spk_embeds = self.speaker_embedding_table(spembs)
                spk_embeds = F.normalize(
                    spk_embeds).unsqueeze(1).expand(-1, decoder_inputs.size(1), -1)
            else:
                spk_embeds = F.normalize(
                    spembs).unsqueeze(1).expand(-1, decoder_inputs.size(1), -1)
            decoder_inputs = torch.cat([decoder_inputs, spk_embeds], dim=-1)
            decoder_inputs = self.reduce_proj(decoder_inputs)
        
        # (B, num_mels, T_dec)
        mel_outputs, predicted_stop, alignments = self.decoder(
            decoder_inputs, speech, feature_lengths//int(self.encoder_down_factor))
        ## Post-processing
        mel_outputs_postnet = self.postnet(mel_outputs.transpose(1, 2)).transpose(1, 2)
        mel_outputs_postnet = mel_outputs + mel_outputs_postnet
        if output_att_ws: 
            return self.parse_output(
                [mel_outputs, mel_outputs_postnet, predicted_stop, alignments], speech_lengths)
        else:
            return self.parse_output(
                [mel_outputs, mel_outputs_postnet, predicted_stop], speech_lengths)

        # return mel_outputs, mel_outputs_postnet

    def inference(
        self,
        bottle_neck_features: torch.Tensor,
        logf0_uv: torch.Tensor = None,
        spembs: torch.Tensor = None,
        use_stop_tokens: bool = True,
    ):
        decoder_inputs = self.bnf_prenet(bottle_neck_features.transpose(1, 2)).transpose(1, 2)
        logf0_uv = self.pitch_convs(logf0_uv.transpose(1, 2)).transpose(1, 2)
        decoder_inputs = decoder_inputs + logf0_uv
        if self.multi_speaker:
            assert spembs is not None
            # spk_embeds = self.speaker_embedding_table(spembs)
            # spk_embeds = F.normalize(
                # spk_embeds).unsqueeze(1).expand(-1, bottle_neck_features.size(1), -1)
            if not self.use_spk_dvec:
                spk_embeds = self.speaker_embedding_table(spembs)
                spk_embeds = F.normalize(
                    spk_embeds).unsqueeze(1).expand(-1, decoder_inputs.size(1), -1)
            else:
                spk_embeds = F.normalize(
                    spembs).unsqueeze(1).expand(-1, decoder_inputs.size(1), -1)
            bottle_neck_features = torch.cat([decoder_inputs, spk_embeds], dim=-1)
            bottle_neck_features = self.reduce_proj(bottle_neck_features)

        ## Decoder
        if bottle_neck_features.size(0) > 1:
            mel_outputs, alignments = self.decoder.inference_batched(bottle_neck_features)
        else:
            mel_outputs, alignments = self.decoder.inference(bottle_neck_features,)
        ## Post-processing
        mel_outputs_postnet = self.postnet(mel_outputs.transpose(1, 2)).transpose(1, 2)
        mel_outputs_postnet = mel_outputs + mel_outputs_postnet
        # outputs = mel_outputs_postnet[0]
        
        return mel_outputs[0], mel_outputs_postnet[0], alignments[0]
