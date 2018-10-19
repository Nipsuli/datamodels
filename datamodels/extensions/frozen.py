import datamodels


@datamodels.dataclass_kwargs_extension
def make_datamodels_frozen_by_default(kwargs):
    return {**{'frozen': True}, **kwargs}
