import torch
import torch.nn as nn
import torch.nn.functional as F
# from nnsp.tts.mol_attention import MOLAttention
from nnsp.ctc_seq2seq_ppg_vc.mol_attention import MOLAttention
from nnsp.layers.basic_layers import Linear, Conv1d
from nnsp.utils.vc_utils import get_mask_from_lengths


class DecoderPrenet(nn.Module):
    def __init__(self, in_dim, sizes):
        super().__init__()
        in_sizes = [in_dim] + sizes[:-1]
        self.layers = nn.ModuleList(
            [Linear(in_size, out_size, bias=False)
             for (in_size, out_size) in zip(in_sizes, sizes)])

    def forward(self, x):
        for linear in self.layers:
            x = F.dropout(F.relu(linear(x)), p=0.5, training=True)
        return x


class Decoder(nn.Module):
    """Mixture of Logistic (MoL) attention-based RNN Decoder."""
    def __init__(
        self,
        enc_dim,
        num_mels,
        frames_per_step,
        attention_rnn_dim,
        decoder_rnn_dim,
        prenet_dims,
        num_mixtures,
        num_decoder_rnn_layer=1,
        use_stop_tokens=False,
        concat_context_to_last=True,
    ):
        super().__init__()
        self.enc_dim = enc_dim
        self.num_mels = num_mels
        self.frames_per_step = frames_per_step
        self.attention_rnn_dim = attention_rnn_dim
        self.decoder_rnn_dim = decoder_rnn_dim
        self.prenet_dims = prenet_dims
        self.use_stop_tokens = use_stop_tokens
        self.num_decoder_rnn_layer = num_decoder_rnn_layer
        self.concat_context_to_last = concat_context_to_last

        # Mel prenet
        self.prenet = DecoderPrenet(num_mels, prenet_dims)
        self.prenet_pitch = DecoderPrenet(num_mels, prenet_dims)

        # Attention RNN
        self.attention_rnn = nn.LSTMCell(
            prenet_dims[-1] + enc_dim,
            attention_rnn_dim
        )
        
        # Attention
        self.attention_layer = MOLAttention(attention_rnn_dim, M=num_mixtures)

        # Decoder RNN
        self.decoder_rnn_layers = nn.ModuleList()
        for i in range(num_decoder_rnn_layer):
            if i == 0:
                self.decoder_rnn_layers.append(
                    nn.LSTMCell(
                        2 * enc_dim + attention_rnn_dim,
                        decoder_rnn_dim))
            else:
                self.decoder_rnn_layers.append(
                    nn.LSTMCell(
                        decoder_rnn_dim,
                        decoder_rnn_dim))
        # self.decoder_rnn = nn.LSTMCell(
            # 2 * enc_dim + attention_rnn_dim,
            # decoder_rnn_dim
        # )
        if concat_context_to_last:
            self.linear_projection = Linear(
                enc_dim * 2 + decoder_rnn_dim,
                num_mels * frames_per_step
            )
        else:
            self.linear_projection = Linear(
                decoder_rnn_dim,
                num_mels * frames_per_step
            )


        # Stop-token layer
        if self.use_stop_tokens:
            if concat_context_to_last:
                self.stop_layer = Linear(
                    enc_dim * 2 + decoder_rnn_dim, 1, bias=True, w_init_gain="sigmoid"
                )
            else:
                self.stop_layer = Linear(
                    decoder_rnn_dim, 1, bias=True, w_init_gain="sigmoid"
                )
                

    def get_go_frame(self, memory):
        B = memory.size(0)
        go_frame = torch.zeros((B, self.num_mels), dtype=torch.float,
                               device=memory.device)
        return go_frame

    def initialize_decoder_states(self, memory, mask, memory_pitch=None, mask_pitch=None):
        device = next(self.parameters()).device
        B = memory.size(0)
        
        # attention rnn states
        self.attention_hidden = torch.zeros(
            (B, self.attention_rnn_dim), device=device)
        self.attention_cell = torch.zeros(
            (B, self.attention_rnn_dim), device=device)

        # decoder rnn states
        self.decoder_hiddens = []
        self.decoder_cells = []
        for i in range(self.num_decoder_rnn_layer):
            self.decoder_hiddens.append(
                torch.zeros((B, self.decoder_rnn_dim),
                            device=device)
            )
            self.decoder_cells.append(
                torch.zeros((B, self.decoder_rnn_dim),
                            device=device)
            )
        # self.decoder_hidden = torch.zeros(
            # (B, self.decoder_rnn_dim), device=device)
        # self.decoder_cell = torch.zeros(
            # (B, self.decoder_rnn_dim), device=device)
        
        self.attention_context =  torch.zeros(
            (B, self.enc_dim), device=device)
        # self.attention_pitch_context =  torch.zeros(
            # (B, self.enc_dim), device=device)

        self.memory = memory
        # self.processed_memory = self.attention_layer.memory_layer(memory)
        self.mask = mask
        self.memory_pitch = memory_pitch
        # self.mask_pitch = mask_pitch

    def parse_decoder_inputs(self, decoder_inputs):
        """Prepare decoder inputs, i.e. gt mel
        Args:
            decoder_inputs:(B, T_out, n_mel_channels) inputs used for teacher-forced training.
        """
        decoder_inputs = decoder_inputs.reshape(
            decoder_inputs.size(0),
            int(decoder_inputs.size(1)/self.frames_per_step), -1)
        # (B, T_out//r, r*num_mels) -> (T_out//r, B, r*num_mels)
        decoder_inputs = decoder_inputs.transpose(0, 1)
        # (T_out//r, B, num_mels)
        decoder_inputs = decoder_inputs[:,:,-self.num_mels:]
        return decoder_inputs
        
    def parse_decoder_outputs(self, mel_outputs, alignments, stop_outputs):
        """ Prepares decoder outputs for output
        Args:
            mel_outputs:
            alignments:
        """
        # (T_out//r, B, T_enc) -> (B, T_out//r, T_enc)
        alignments = torch.stack(alignments).transpose(0, 1)
        # alignments_pitch = torch.stack(alignments_pitch).transpose(0, 1)
        # (T_out//r, B) -> (B, T_out//r)
        if stop_outputs is not None:
            if alignments.size(0) == 1:
                stop_outputs = torch.stack(stop_outputs).unsqueeze(0)
            else:
                stop_outputs = torch.stack(stop_outputs).transpose(0, 1)
            stop_outputs = stop_outputs.contiguous()
        # (T_out//r, B, num_mels*r) -> (B, T_out//r, num_mels*r)
        mel_outputs = torch.stack(mel_outputs).transpose(0, 1).contiguous()
        # decouple frames per step
        # (B, T_out, num_mels)
        mel_outputs = mel_outputs.view(
            mel_outputs.size(0), -1, self.num_mels)
        return mel_outputs, alignments, stop_outputs     
    
    def attend(self, decoder_input):
        cell_input = torch.cat((decoder_input, self.attention_context), -1)
        self.attention_hidden, self.attention_cell = self.attention_rnn(
            cell_input, (self.attention_hidden, self.attention_cell))
        # NOTE
        self.attention_context, attention_context_pitch, attention_weights = self.attention_layer(
            self.attention_hidden, self.memory, self.memory_pitch, self.mask)
        
        decoder_rnn_input = torch.cat(
            (self.attention_hidden, self.attention_context, attention_context_pitch), -1)

        return decoder_rnn_input, self.attention_context, attention_context_pitch, attention_weights

    def decode(self, decoder_input):
        for i in range(self.num_decoder_rnn_layer):
            if i == 0:
                self.decoder_hiddens[i], self.decoder_cells[i] = self.decoder_rnn_layers[i](
                    decoder_input, (self.decoder_hiddens[i], self.decoder_cells[i]))
            else:
                self.decoder_hiddens[i], self.decoder_cells[i] = self.decoder_rnn_layers[i](
                    self.decoder_hiddens[i-1], (self.decoder_hiddens[i], self.decoder_cells[i]))
        return self.decoder_hiddens[-1]
    
    def forward(self, memory, mel_inputs, memory_lengths, memory_pitch):
        """ Decoder forward pass for training
        Args:
            memory: (B, T_enc, enc_dim) Encoder outputs
            decoder_inputs: (B, T, num_mels) Decoder inputs for teacher forcing.
            memory_lengths: (B, ) Encoder output lengths for attention masking.
        Returns:
            mel_outputs: (B, T, num_mels) mel outputs from the decoder
            alignments: (B, T//r, T_enc) attention weights.
        """
        # [1, B, num_mels]
        go_frame = self.get_go_frame(memory).unsqueeze(0)
        # [T//r, B, num_mels]
        mel_inputs = self.parse_decoder_inputs(mel_inputs)
        # [T//r + 1, B, num_mels]
        mel_inputs = torch.cat((go_frame, mel_inputs), dim=0)
        # [T//r + 1, B, prenet_dim]
        decoder_inputs = self.prenet(mel_inputs) 

        self.initialize_decoder_states(
            memory, mask=~get_mask_from_lengths(memory_lengths),
            memory_pitch=memory_pitch
        )
        
        self.attention_layer.init_states(memory)

        mel_outputs, alignments = [], []
        if self.use_stop_tokens:
            stop_outputs = []
        else:
            stop_outputs = None
        while len(mel_outputs) < decoder_inputs.size(0) - 1:
            decoder_input = decoder_inputs[len(mel_outputs)]
            # decoder_input_pitch = decoder_inputs_pitch[len(mel_outputs)]

            decoder_rnn_input, context, context_pitch, attention_weights = self.attend(decoder_input)

            decoder_rnn_output = self.decode(decoder_rnn_input)
            if self.concat_context_to_last:    
                decoder_rnn_output = torch.cat(
                    (decoder_rnn_output, context, context_pitch), dim=1)
                   
            mel_output = self.linear_projection(decoder_rnn_output)
            if self.use_stop_tokens:
                stop_output = self.stop_layer(decoder_rnn_output)
                stop_outputs += [stop_output.squeeze()]
            mel_outputs += [mel_output.squeeze(1)] #? perhaps don't need squeeze
            alignments += [attention_weights]
            # alignments_pitch += [attention_weights_pitch]   

        mel_outputs, alignments, stop_outputs = self.parse_decoder_outputs(
            mel_outputs, alignments, stop_outputs)
        if stop_outputs is None:
            return mel_outputs, alignments
        else:
            return mel_outputs, stop_outputs, alignments

    def inference(self, memory, memory_pitch, stop_threshold=0.5):
        """ Decoder inference
        Args:
            memory: (1, T_enc, D_enc) Encoder outputs
        Returns:
            mel_outputs: mel outputs from the decoder
            alignments: sequence of attention weights from the decoder
        """
        # [1, num_mels]
        decoder_input = self.get_go_frame(memory)

        self.initialize_decoder_states(memory, mask=None, memory_pitch=memory_pitch)

        self.attention_layer.init_states(memory)
        
        mel_outputs, alignments = [], []
        max_decoder_step = memory.size(1) * 8  # NOTE(sx): heuristic
        min_decoder_step = memory.size(1) * 2
        while True:
            decoder_input = self.prenet(decoder_input)

            decoder_input_final, context, context_pitch, alignment = self.attend(decoder_input)

            #mel_output, stop_output, alignment = self.decode(decoder_input)
            decoder_rnn_output = self.decode(decoder_input_final)
            if self.concat_context_to_last:    
                decoder_rnn_output = torch.cat(
                    (decoder_rnn_output, context, context_pitch), dim=1)
            
            mel_output = self.linear_projection(decoder_rnn_output)
            stop_output = self.stop_layer(decoder_rnn_output)
            
            mel_outputs += [mel_output.squeeze(1)]
            alignments += [alignment]
            
            if torch.sigmoid(stop_output.data) > stop_threshold and len(mel_outputs) >= min_decoder_step:
                break
            if len(mel_outputs) == max_decoder_step:
                print("Warning! Decoding steps reaches max decoder steps.")
                break

            decoder_input = mel_output[:,-self.num_mels:]


        mel_outputs, alignments, _  = self.parse_decoder_outputs(
            mel_outputs, alignments, None)

        return mel_outputs, alignments
