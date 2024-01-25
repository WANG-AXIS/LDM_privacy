import sys
sys.path.append("..")
import os
os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"
from pathlib import Path
from datetime import datetime

import torch 

from pytorch_lightning.trainer import Trainer
from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint


from medical_diffusion.data.datamodules import SimpleDataModule
from medical_diffusion.data.datasets import Mayo_Dataset
from medical_diffusion.models.embedders.latent_embedders import VAE

import torch.multiprocessing
torch.multiprocessing.set_sharing_strategy('file_system')

if __name__ == "__main__":

    # --------------- Settings --------------------
    current_time = datetime.now().strftime("VAE_%Y%m%d_%H%M%S")
    path_run_dir = Path.cwd() / 'runs' / 'VAE'
    path_run_dir.mkdir(parents=True, exist_ok=True)
    gpus = [0] if torch.cuda.is_available() else None


    # ------------ Load Mayo Clinic Data ----------------
    ds_2 = Mayo_Dataset( #  512x512   
        crawler_ext='npy',
        augment_horizontal_flip=False,
        augment_vertical_flip=False,
        
        path_root=os.path.join('..', '..', 'data', 'ori_dataset') #path of the original dataset
    )

    dm = SimpleDataModule(
        ds_train = ds_2,
        batch_size=4, 
        # num_workers=0,
        pin_memory=True
    ) 
    

    # ------------ Initialize Model ------------
    model = VAE(
        in_channels=1, 
        out_channels=1, 
        emb_channels=4,
        spatial_dims=2,
        hid_chs =    [ 64, 128, 256,  512], 
        kernel_sizes=[ 3,  3,   3,    3],
        strides =    [ 1,  2,   2,    2],
        deep_supervision=1,
        use_attention= 'none',
        loss = torch.nn.MSELoss,
        # optimizer_kwargs={'lr':1e-6},
        embedding_loss_weight=1e-6
    )

    # -------------- Training Initialization ---------------
    to_monitor = "train/L1"  # "val/loss" 
    min_max = "min"
    save_and_sample_every = 50

    early_stopping = EarlyStopping(
        monitor=to_monitor,
        min_delta=0.0, # minimum change in the monitored quantity to qualify as an improvement
        patience=10, # number of checks with no improvement
        mode=min_max
    )
    checkpointing = ModelCheckpoint(
        dirpath=str(path_run_dir), # dirpath
        monitor=to_monitor,
        every_n_train_steps=save_and_sample_every,
        save_last=True,
        save_top_k=5,
        mode=min_max,
    )
    trainer = Trainer(
        accelerator='gpu',
        devices=[0],
        # precision=16,
        # amp_backend='apex',
        # amp_level='O2',
        # gradient_clip_val=0.5,
        default_root_dir=str(path_run_dir),
        callbacks=[checkpointing],
        # callbacks=[checkpointing, early_stopping],
        enable_checkpointing=True,
        check_val_every_n_epoch=1,
        log_every_n_steps=save_and_sample_every, 
        auto_lr_find=False,
        # limit_train_batches=1000,
        limit_val_batches=0, # 0 = disable validation - Note: Early Stopping no longer available 
        min_epochs=200,
        max_epochs=1001,
        num_sanity_val_steps=2,
    )
    
    # ---------------- Execute Training ----------------
    trainer.fit(model, datamodule=dm)

    # ------------- Save path to best model -------------
    model.save_best_checkpoint(trainer.logger.log_dir, checkpointing.best_model_path)


