from contextlib import contextmanager
import logging

def log_epoch(epoch, epoch_metrics, tb_writer):
    logging.info(
        " ".join(
            [f"epoch {epoch},"] + [f"{k}: {v:.5e}" for k, v in epoch_metrics.items()]
        )
    )

    for name, value in epoch_metrics.items():
        tb_writer.add_scalar(name, value, epoch)

@contextmanager
def track_run(experiment_name, run_name, config, tags, tb_dir):
    from torch.utils.tensorboard import SummaryWriter

    with SummaryWriter(tb_dir) as tb_writer:
        yield tb_writer