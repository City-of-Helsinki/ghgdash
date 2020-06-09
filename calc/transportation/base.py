from .cars import predict_cars_emissions
from calc.transportation.datasets import prepare_transportation_emissions_dataset
from calc import calcfunc


@calcfunc(
    funcs=[
        prepare_transportation_emissions_dataset
    ]
)
def predict_transportation_emissions():
    df = prepare_transportation_emissions_dataset()
    return df


if __name__ == '__main__':
    predict_transportation_emissions(skip_cache=True)
