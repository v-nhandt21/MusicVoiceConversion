. ppg-vc/path.sh || exit 1;
export CUDA_VISIBLE_DEVICES=4

stage=1
stop_stage=1
config=/data/nhandt23/Workspace/ppg-vc/pretrain/bneSeq2seqMoL-vctk-libritts460-oneshot/seq2seq_mol_ppg2mel_vctk_libri_oneshotvc_r4_normMel_v2.yaml
model_file=/data/nhandt23/Workspace/ppg-vc/pretrain/bneSeq2seqMoL-vctk-libritts460-oneshot/best_loss_step_304000.pth
src_wav_dir=/data/nhandt23/Workspace/ppg-vc/content.wav
ref_wav_path=/data/nhandt23/Workspace/ppg-vc/ref.wav
echo ${config}

# =============== One-shot VC ================
if [ ${stage} -le 1 ] && [ ${stop_stage} -ge 1 ]; then
  exp_name="$(basename "${config}" .yaml)"
  echo Experiment name: "${exp_name}"
#   src_wav_dir="/home/shaunxliu/data/cmu_arctic/cmu_us_rms_arctic/wav"
#   ref_wav_path="/home/shaunxliu/data/cmu_arctic/cmu_us_slt_arctic/wav/arctic_a0001.wav"
  output_file="converted.wav"

  python ppg-vc/convert_from_wav.py \
    --ppg2mel_model_train_config ${config} \
    --ppg2mel_model_file ${model_file} \
    --src_wav_dir "${src_wav_dir}" \
    --ref_wav_path "${ref_wav_path}" \
    -o "${output_file}"
fi
