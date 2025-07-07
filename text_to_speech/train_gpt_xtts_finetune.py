import os
import json
import torch
import gc
import warnings
import torchaudio

from trainer import Trainer, TrainerArgs

from huggingface_hub import snapshot_download
import subprocess

from TTS.config.shared_configs import BaseDatasetConfig
from TTS.tts.datasets import load_tts_samples
from TTS.tts.layers.xtts.trainer.gpt_trainer import GPTArgs, GPTTrainer, GPTTrainerConfig, XttsAudioConfig
from TTS.utils.manage import ModelManager

warnings.filterwarnings("ignore", category=UserWarning)

torch.cuda.empty_cache()
gc.collect()
torch.cuda.set_per_process_memory_fraction(0.9)

RUN_NAME = "XTTS_CLOSS_FT"
PROJECT_NAME = "XTTS_soccer_trainer"
DASHBOARD_LOGGER = "tensorboard"
LOGGER_URI = None

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run", "training")

OPTIMIZER_WD_ONLY_ON_WEIGHTS = True
START_WITH_EVAL = False
BATCH_SIZE = 1
GRAD_ACUMM_STEPS = 32

config_dataset = BaseDatasetConfig(
    formatter="ljspeech",
    dataset_name="soccer_commentary_dataset",
    path="dataset_coqui/",
    meta_file_train="metadata.csv",
    language="es",
)

DATASETS_CONFIG_LIST = [config_dataset]

PRETRAINED_MODEL_PATH = os.path.abspath("text_to_speech/XTTS-v2-argentinian-spanish/")

def download_model():
    """Helper function to download the model"""
    os.makedirs(os.path.dirname(PRETRAINED_MODEL_PATH), exist_ok=True)
    
    snapshot_download(
        repo_id="UNRN/XTTS-v2-argentinian-spanish",
        local_dir=PRETRAINED_MODEL_PATH,
        local_dir_use_symlinks=False
    )
    
    print(f"Successfully cloned model to {PRETRAINED_MODEL_PATH}")

# Check if pretrained model exists, if not clone from Hugging Face
if not os.path.exists(PRETRAINED_MODEL_PATH):
    print(f"Pretrained model not found at {PRETRAINED_MODEL_PATH}")
    print("Cloning XTTS-v2-argentinian-spanish from Hugging Face...")
    
    try:
        download_model()
    except ImportError:
        print("huggingface_hub not installed. Installing...")
        subprocess.check_call(["pip", "install", "huggingface_hub"])
        download_model()  # No need to duplicate the download logic
    except Exception as e:
        print(f"Error cloning model: {e}")
        raise


CONFIG_FILE = os.path.join(PRETRAINED_MODEL_PATH, "config.json")
TOKENIZER_FILE = os.path.join(PRETRAINED_MODEL_PATH, "vocab.json")
XTTS_CHECKPOINT = os.path.join(PRETRAINED_MODEL_PATH, "model.pth")

DVAE_CHECKPOINT = os.path.join(PRETRAINED_MODEL_PATH, "dvae.pth")
MEL_NORM_FILE = os.path.join(PRETRAINED_MODEL_PATH, "mel_stats.pth")

# If DVAE checkpoint or mel norm file is missing, download them
if not os.path.isfile(DVAE_CHECKPOINT) or not os.path.isfile(MEL_NORM_FILE):
    print("DVAE checkpoint or mel norm file not found. Downloading...")
    # coqui/XTTS-v2 'dvae.pth and mel_stats.pth are available in the same repo
    dvae_url = "https://huggingface.co/coqui/XTTS-v2/resolve/main/dvae.pth"
    mel_norm_url = "https://huggingface.co/coqui/XTTS-v2/resolve/main/mel_stats.pth"
    os.makedirs(os.path.dirname(DVAE_CHECKPOINT), exist_ok=True)
    os.makedirs(os.path.dirname(MEL_NORM_FILE), exist_ok=True)
    try:
        subprocess.check_call(["wget", dvae_url, "-O", DVAE_CHECKPOINT])
        subprocess.check_call(["wget", mel_norm_url, "-O", MEL_NORM_FILE])
    except Exception as e:
        print(f"Error downloading files: {e}")
        raise 



required_files = [DVAE_CHECKPOINT, MEL_NORM_FILE, TOKENIZER_FILE, XTTS_CHECKPOINT, CONFIG_FILE]
for file_path in required_files:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Required file not found: {file_path} \
                                 MAKE SURE THE 'dvae.pth' and 'mel_stats.pth' FILES ARE IN THE SAME DIRECTORY AS THE XTTS CHECKPOINT")

with open(CONFIG_FILE, 'r') as f:
    pretrained_config = json.load(f)

SPEAKER_REFERENCE = [
    "dataset_coqui/wavs/chunk_004.wav"
]
LANGUAGE = config_dataset.language

def validate_audio_files(samples):
    valid_samples = []
    for sample in samples:
        try:
            audio_file = sample.get('audio_file', '')
            
            if not os.path.exists(audio_file):
                print(f"Warning: Audio file not found: {audio_file}")
                continue
            
            if 'copy' in os.path.basename(audio_file).lower():
                print(f"Warning: Skipping copy file (likely corrupted): {audio_file}")
                continue
            
            try:
                waveform, sr = torchaudio.load(audio_file)
            except Exception as e:
                print(f"Warning: Cannot load audio file {audio_file}: {e}")
                continue
            
            if torch.isnan(waveform).any() or torch.isinf(waveform).any():
                print(f"Warning: Audio contains NaN/Inf values: {audio_file}")
                continue
            
            duration = waveform.shape[1] / sr
            if duration < 1.0 or duration > 15.0:
                print(f"Warning: Audio duration {duration:.2f}s outside range: {audio_file}")
                continue
            
            if waveform.shape[1] < sr * 0.5:
                print(f"Warning: Audio too short ({waveform.shape[1]} samples): {audio_file}")
                continue
            
            text = sample.get('text', '').strip()
            if len(text) < 5 or len(text) > 500:
                print(f"Warning: Text length {len(text)} outside range: {text[:50]}...")
                continue
            
            valid_samples.append(sample)
            
        except Exception as e:
            print(f"Error processing {sample.get('audio_file', 'unknown')}: {e}")
            continue
    
    print(f"Validated {len(valid_samples)} out of {len(samples)} samples")
    return valid_samples

def main():
    torch.cuda.empty_cache()
    gc.collect()
    
    model_args = GPTArgs(
        max_conditioning_length=176400,
        min_conditioning_length=66150,
        max_wav_length=220500,
        max_text_length=150,
        
        mel_norm_file=MEL_NORM_FILE,
        dvae_checkpoint=DVAE_CHECKPOINT,
        xtts_checkpoint=XTTS_CHECKPOINT,
        tokenizer_file=TOKENIZER_FILE,
        
        gpt_num_audio_tokens=1026,
        gpt_start_audio_token=1024,
        gpt_stop_audio_token=1025,
        gpt_use_masking_gt_prompt_approach=True,
        gpt_use_perceiver_resampler=True,
        debug_loading_failures=True,
        
        gpt_loss_text_ce_weight=0.01,
        gpt_loss_mel_ce_weight=1.0,
    )
    
    if 'model_args' in pretrained_config:
        safe_keys = ['gpt_layers', 'gpt_n_model_channels', 'gpt_n_heads', 
                     'gpt_number_text_tokens', 'gpt_code_stride_len']
        for key in safe_keys:
            if key in pretrained_config['model_args']:
                setattr(model_args, key, pretrained_config['model_args'][key])
    
    audio_config = XttsAudioConfig(
        sample_rate=22050,
        dvae_sample_rate=22050,
        output_sample_rate=24000
    )
    
    config = GPTTrainerConfig(
        output_path=OUT_PATH,
        model_args=model_args,
        run_name=RUN_NAME,
        project_name=PROJECT_NAME,
        run_description="GPT XTTS fine-tuning for soccer commentary with NaN prevention",
        dashboard_logger=DASHBOARD_LOGGER,
        logger_uri=LOGGER_URI,
        audio=audio_config,
        
        batch_size=BATCH_SIZE,
        batch_group_size=1,
        eval_batch_size=1,
        num_loader_workers=4,
        
        eval_split_max_size=32,
        print_step=10,
        plot_step=100,
        log_model_step=150,
        save_step=1000,
        save_n_checkpoints=2,
        save_checkpoints=True,
        print_eval=True,
        
        optimizer="AdamW",
        optimizer_wd_only_on_weights=OPTIMIZER_WD_ONLY_ON_WEIGHTS,
        optimizer_params={
            "betas": [0.9, 0.999],
            "eps": 1e-6,
            "weight_decay": 1e-3
        },
        
        lr=1e-4,
        lr_scheduler="MultiStepLR",
        lr_scheduler_params={
            "milestones": [10000, 30000, 60000],
            "gamma": 0.5,
            "last_epoch": -1
        },
        
        grad_clip=1.0,
        mixed_precision=False,
        
        test_sentences=[
            {
                "text": "¡Gooool de Messi! ¡Qué jugada espectacular del diez!",
                "speaker_wav": SPEAKER_REFERENCE,
                "language": LANGUAGE,
            },
        ],
    )

    torch.cuda.empty_cache()
    gc.collect()

    model = GPTTrainer.init_from_config(config)
    
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Initial - Total: {total_params:,}, Trainable: {trainable_params:,}")
    
    for param in model.dvae.parameters():
        param.requires_grad = False
    
    if hasattr(model, 'torch_mel_spectrogram_style_encoder'):
        for param in model.torch_mel_spectrogram_style_encoder.parameters():
            param.requires_grad = False
    
    if hasattr(model, 'torch_mel_spectrogram_dvae'):
        for param in model.torch_mel_spectrogram_dvae.parameters():
            param.requires_grad = False
    
    gpt_model = model.xtts.gpt
    
    if hasattr(gpt_model, 'text_embedding'):
        gpt_model.text_embedding.requires_grad_(False)
    if hasattr(gpt_model, 'mel_embedding'):
        gpt_model.mel_embedding.requires_grad_(False)
    
    if hasattr(gpt_model, 'gpt') and hasattr(gpt_model.gpt, 'h'):
        total_layers = len(gpt_model.gpt.h)
        layers_to_freeze = max(0, total_layers - 1)
        print(f"Freezing bottom {layers_to_freeze} layers out of {total_layers}")
        
        for i in range(layers_to_freeze):
            for param in gpt_model.gpt.h[i].parameters():
                param.requires_grad = False
    
    trainable_params_final = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"After freezing - Trainable: {trainable_params_final:,} ({trainable_params_final/total_params:.2%})")
    
    nan_params = []
    for name, param in model.named_parameters():
        if param.requires_grad:
            if torch.isnan(param).any() or torch.isinf(param).any():
                nan_params.append(name)
    
    if nan_params:
        print(f"WARNING: Found NaN/Inf in parameters: {nan_params}")
        for name, param in model.named_parameters():
            if name in nan_params:
                torch.nn.init.xavier_uniform_(param)
    else:
        print("All parameters are finite - good!")
    
    train_samples, eval_samples = load_tts_samples(
        DATASETS_CONFIG_LIST,
        eval_split=True,
        eval_split_max_size=config.eval_split_max_size,
        eval_split_size=0.1,
    )
    
    print(f"Loaded {len(train_samples)} training samples, {len(eval_samples)} eval samples")
    
    train_samples = validate_audio_files(train_samples)
    eval_samples = validate_audio_files(eval_samples)
    
    if len(train_samples) == 0:
        raise ValueError("No valid training samples found!")
    
    print(f"Using {len(train_samples)} training samples, {len(eval_samples)} eval samples")
    
    torch.cuda.empty_cache()
    gc.collect()
    

    trainer = Trainer(
        TrainerArgs(
            grad_accum_steps=GRAD_ACUMM_STEPS,
            start_with_eval=START_WITH_EVAL,
        ),
        config,
        output_path=OUT_PATH,
        model=model,
        train_samples=train_samples,
        eval_samples=eval_samples,
    )
    
    original_get_train_dataloader = trainer.get_train_dataloader
    
    def patched_get_train_dataloader(*args, **kwargs):
        loader = original_get_train_dataloader(*args, **kwargs)
        
        class BatchFixerLoader:
            def __init__(self, original_loader):
                self.original_loader = original_loader
            
            def __iter__(self):
                for batch in self.original_loader:
                    if 'conditioning' in batch and 'cond_mels' not in batch:
                        batch['cond_mels'] = batch['conditioning']
                    
                    if 'text_inputs' not in batch and 'padded_text' in batch:
                        batch['text_inputs'] = batch['padded_text']
                    
                    if 'wav_lengths' not in batch and 'wav' in batch:
                        wav_tensor = batch['wav']
                        if len(wav_tensor.shape) == 3:
                            batch['wav_lengths'] = torch.tensor([wav_tensor.shape[2] for _ in range(wav_tensor.shape[0])], dtype=torch.long)
                        elif len(wav_tensor.shape) == 2:
                            batch['wav_lengths'] = torch.tensor([wav_tensor.shape[1] for _ in range(wav_tensor.shape[0])], dtype=torch.long)
                    
                    if 'text_lengths' not in batch and 'padded_text' in batch:
                        text_tensor = batch['padded_text']
                        batch['text_lengths'] = torch.sum(text_tensor != 0, dim=1)
                    
                    yield batch
            
            def __len__(self):
                return len(self.original_loader)
        
        return BatchFixerLoader(loader)
    
    trainer.get_train_dataloader = patched_get_train_dataloader
    
    if hasattr(trainer, 'get_eval_dataloader'):
        original_get_eval_dataloader = trainer.get_eval_dataloader
        
        def patched_get_eval_dataloader(*args, **kwargs):
            loader = original_get_eval_dataloader(*args, **kwargs)
            
            class BatchFixerLoader:
                def __init__(self, original_loader):
                    self.original_loader = original_loader
                
                def __iter__(self):
                    for batch in self.original_loader:
                        if 'conditioning' in batch and 'cond_mels' not in batch:
                            batch['cond_mels'] = batch['conditioning']
                        
                        if 'text_inputs' not in batch and 'padded_text' in batch:
                            batch['text_inputs'] = batch['padded_text']
                        
                        if 'wav_lengths' not in batch and 'wav' in batch:
                            wav_tensor = batch['wav']
                            if len(wav_tensor.shape) == 3:
                                batch['wav_lengths'] = torch.tensor([wav_tensor.shape[2] for _ in range(wav_tensor.shape[0])], dtype=torch.long)
                            elif len(wav_tensor.shape) == 2:
                                batch['wav_lengths'] = torch.tensor([wav_tensor.shape[1] for _ in range(wav_tensor.shape[0])], dtype=torch.long)
                        
                        if 'text_lengths' not in batch and 'padded_text' in batch:
                            text_tensor = batch['padded_text']
                            batch['text_lengths'] = torch.sum(text_tensor != 0, dim=1)
                        
                        yield batch
                
                def __len__(self):
                    return len(self.original_loader)
            
            return BatchFixerLoader(loader)
        
        trainer.get_eval_dataloader = patched_get_eval_dataloader
    
    trainer.fit()

if __name__ == "__main__":
    main()
