from enum import Enum
import importlib
import os

from pathlib import Path
import re

from codetiming import Timer
from knockknock import slack_sender
import shortuuid
import typer
import xarray as xr

from losses import get_optimizer
from models.ema import ExponentialMovingAverage

# import torch.nn as nn
# import numpy as np
# import tensorflow as tf
# import tensorflow_datasets as tfds
# import tensorflow_gan as tfgan
import tqdm

# from ml_downscaling_emulator.training.dataset import XRDataset

from utils import restore_checkpoint

# from configs.subvp import xarray_cncsnpp_continuous
import models
from models import utils as mutils
# from models import ncsnv2
# from models import ncsnpp
from models import cncsnpp
from models import cunet
# from models import ddpm as ddpm_model
from models import layerspp
from models import layers
from models import normalization
import sampling
# from likelihood import get_likelihood_fn
from sde_lib import VESDE, VPSDE, subVPSDE
# from sampling import (ReverseDiffusionPredictor,
#                       LangevinCorrector,
#                       EulerMaruyamaPredictor,
#                       AncestralSamplingPredictor,
#                       NoneCorrector,
#                       NonePredictor,
#                       AnnealedLangevinDynamics)
import datasets

import logging
logger = logging.getLogger()
logger.setLevel('INFO')

app = typer.Typer()

class SDEOption(str, Enum):
    VESDE = "vesde"
    VPSDE = "vpsde"
    subVPSDE = "subvpsde"

def load_model(config, sde, ckpt_filename):
    if sde == SDEOption.VESDE:
        sde = VESDE(sigma_min=config.model.sigma_min, sigma_max=config.model.sigma_max, N=config.model.num_scales)
        sampling_eps = 1e-5
    elif sde == SDEOption.VPSDE:
        sde = VPSDE(beta_min=config.model.beta_min, beta_max=config.model.beta_max, N=config.model.num_scales)
        sampling_eps = 1e-3
    elif sde == SDEOption.subVPSDE:
        sde = subVPSDE(beta_min=config.model.beta_min, beta_max=config.model.beta_max, N=config.model.num_scales)
        sampling_eps = 1e-3

    random_seed = 0 #@param {"type": "integer"}

    sigmas = mutils.get_sigmas(config)
    score_model = mutils.create_model(config)

    optimizer = get_optimizer(config, score_model.parameters())
    ema = ExponentialMovingAverage(score_model.parameters(),
                                   decay=config.model.ema_rate)
    state = dict(step=0, optimizer=optimizer,
                 model=score_model, ema=ema)

    state = restore_checkpoint(ckpt_filename, state, config.device)
    ema.copy_to(score_model.parameters())

    # Sampling
    num_output_channels = len(datasets.get_variables(config)[1])
    sampling_shape = (config.eval.batch_size, num_output_channels,
                          config.data.image_size, config.data.image_size)
    sampling_fn = sampling.get_sampling_fn(config, sde, sampling_shape, sampling_eps)

    return score_model, sampling_fn

def generate_samples(sampling_fn, score_model, config, cond_batch):
    cond_batch = cond_batch.to(config.device)

    samples = sampling_fn(score_model, cond_batch)[0]
    # drop the feature channel dimension (only have target pr as output)
    samples = samples.squeeze(dim=1)
    # extract numpy array
    samples = samples.cpu().numpy()
    return samples

def generate_predictions(sampling_fn, score_model, config, cond_batch, target_transform, coords, cf_data_vars):
    print("making predictions", flush=True)
    samples = generate_samples(sampling_fn, score_model, config, cond_batch)

    coords = {**dict(coords)}

    pred_pr_dims=["time", "grid_latitude", "grid_longitude"]
    pred_pr_attrs = {"grid_mapping": "rotated_latitude_longitude", "standard_name": "pred_pr", "units": "kg m-2 s-1"}
    pred_pr_var = (pred_pr_dims, samples, pred_pr_attrs)

    data_vars = {**cf_data_vars, "target_pr": pred_pr_var}

    samples_ds = target_transform.invert(xr.Dataset(data_vars=data_vars, coords=coords, attrs={}))
    samples_ds = samples_ds.rename({"target_pr": "pred_pr"})
    return samples_ds

def load_config(config_path):
    # config_path = os.path.join(os.path.dirname(__file__), "configs", re.sub(r'sde$', '', sde.value.lower()), f"{config_name}.py")

    # spec = importlib.util.spec_from_file_location("config", config_path)
    # module = importlib.util.module_from_spec(spec)
    # spec.loader.exec_module(module)
    # return module.get_config()
    import yaml
    from ml_collections import config_dict

    with open(config_path) as f:
        config = config_dict.ConfigDict(yaml.unsafe_load(f))

    return config

@app.command()
@Timer(name="sample", text="{name}: {minutes:.1f} minutes", logger=logger.info)
@slack_sender(webhook_url=os.getenv("KK_SLACK_WH_URL"), channel="general")
def main(workdir: Path, dataset: str = typer.Option(...), dataset_split: str = "val", sde: SDEOption = SDEOption.subVPSDE, checkpoint_id: int = typer.Option(...), batch_size: int = None, num_samples: int = 3):
    config_path = os.path.join(workdir, "config.yml")
    config = load_config(config_path)
    if batch_size is not None:
        config.eval.batch_size = batch_size

    output_dirpath = workdir/"samples"/f"checkpoint-{checkpoint_id}"/dataset/dataset_split
    os.makedirs(output_dirpath, exist_ok=True)

    ckpt_filename = os.path.join(workdir, "checkpoints", f"checkpoint_{checkpoint_id}.pth")

    score_model, sampling_fn = load_model(config, sde, ckpt_filename)

    transform_dir = os.path.join(workdir, "transforms")

    # Data
    eval_dl, _, target_transform = datasets.get_dataset(config, dataset, config.data.dataset_name, transform_dir, batch_size=config.eval.batch_size,  split=dataset_split, evaluation=True)

    xr_data_eval = eval_dl.dataset.ds

    for sample_id in range(num_samples):
        typer.echo(f"Sample run {sample_id}...")
        cf_data_vars = {key: xr_data_eval.data_vars[key] for key in ["rotated_latitude_longitude", "time_bnds", "grid_latitude_bnds", "grid_longitude_bnds"]}
        preds = []
        for batch_num, (cond_batch, _) in enumerate(eval_dl):
            typer.echo(f"Working on batch {batch_num}")
            time_idx_start = batch_num*eval_dl.batch_size
            coords = xr_data_eval.isel(time=slice(time_idx_start, time_idx_start+len(cond_batch))).coords

            preds.append(generate_predictions(sampling_fn, score_model, config, cond_batch, target_transform, coords, cf_data_vars))

        ds = xr.combine_by_coords(preds, compat='no_conflicts', combine_attrs="drop_conflicts", coords="all", join="inner", data_vars="all")

        output_filepath = output_dirpath/f"predictions-{shortuuid.uuid()}.nc"
        typer.echo(f"Saving samples to {output_filepath}...")
        ds.to_netcdf(output_filepath)


if __name__ == "__main__":
    app()
